"""Daemon principal — o loop do Governante.

Agenda (intervalos na config):
  health     : checagens de saúde + healing + fechamento de incidentes
  discovery  : projetos novos/removidos + sync de charters + drift de baseline
  hygiene    : varredura de melhorias + purga de quarentena + poda do journal
  updates    : atualizações de projetos e do sistema
  learning   : consolidação de baselines
  selfcare   : memória própria, integridade de estado, watchdog
  digests    : resumo diário e relatório semanal

Cada tarefa roda dentro de um Bulkhead: se uma quebrar, as outras seguem.
"""

import datetime
import signal
import time

from . import charter as charter_mod
from . import discovery, hygiene, monitor, reporting, updates
from .config import load as load_config
from .healing import Healer
from .journal import Journal
from .learning import Learning
from .selfcare import (Bulkhead, check_self_memory, notify_ready,
                       notify_watchdog, verify_state)
from .telegram import Orion
from .util import atomic_write_json, read_json


class Daemon:
    def __init__(self, cfg=None):
        self.cfg = cfg or load_config()
        self.journal = Journal(self.cfg)
        self.orion = Orion(self.cfg, self.journal)
        self.learning = Learning(self.cfg, self.journal)
        self.healer = Healer(self.cfg, self.journal, self.learning)
        self.bulkhead = Bulkhead(self.journal, self.orion)
        self.monitor_state = monitor.load_monitor_state(self.cfg)
        self.flags_path = self.cfg.state_file("flags.json")
        self.weekly_cache = {"hygiene_notes": [], "updates": []}
        self._stop = False
        self._last_run = {}
        self._register_commands()

    # --- flags (pausa) ---------------------------------------------------------
    def _flags(self):
        return read_json(self.flags_path, default={"paused": False})

    def _set_flag(self, key, value):
        flags = self._flags()
        flags[key] = value
        atomic_write_json(self.flags_path, flags)

    @property
    def paused(self):
        return bool(self._flags().get("paused"))

    # --- loop -------------------------------------------------------------------
    def run(self):
        self.journal.log("selfcare", "Governor iniciado (versão %s)"
                         % _version())
        signal.signal(signal.SIGTERM, self._on_sigterm)
        signal.signal(signal.SIGINT, self._on_sigterm)
        self.orion.start_polling()
        notify_ready()
        self.orion.send("🏛 Governor de pé e observando o servidor. "
                        "Use /ajuda para os comandos.", silent=True)
        # primeira descoberta imediata
        self.bulkhead.run("discovery", self.task_discovery)
        while not self._stop:
            notify_watchdog()
            self._run_due("health", self.cfg.interval("health"),
                          self.task_health)
            self._run_due("discovery", self.cfg.interval("discovery"),
                          self.task_discovery)
            self._run_due("hygiene", self.cfg.interval("hygiene"),
                          self.task_hygiene)
            self._run_due("updates", self.cfg.interval("updates"),
                          self.task_updates)
            self._run_due("learning", self.cfg.interval("learning"),
                          self.task_learning)
            self._run_due("selfcare", self.cfg.interval("selfcare"),
                          self.task_selfcare)
            self._run_due("flush_queue", self.cfg.interval("flush_queue"),
                          self.orion.flush_queue)
            self._run_due("forecast", 3600, self.task_forecast)
            self._run_due("digests", 300, self.task_digests)
            time.sleep(5)
        self.orion.send("🏛 Governor encerrando (sinal recebido). Até já.",
                        silent=True)
        self.orion.stop()

    def _on_sigterm(self, signum, frame):
        self._stop = True

    def _run_due(self, name, interval, fn):
        now = time.time()
        if now - self._last_run.get(name, 0) < interval:
            return
        self._last_run[name] = now
        self.bulkhead.run(name, fn)

    # --- tarefas -------------------------------------------------------------------
    def task_health(self):
        if self.paused:
            return
        catalog = discovery.load_catalog(self.cfg)
        charters = charter_mod.all_charters(self.cfg)
        results = monitor.system_checks(self.cfg)
        for pid, c in charters.items():
            if c.get("status") == charter_mod.STATUS_IGNORED:
                continue
            if pid not in catalog and not c.get("services") \
                    and not c.get("containers"):
                continue
            results.extend(monitor.project_checks(self.cfg, c, self.monitor_state))
        for result in results:
            self._handle_result(result, charters.get(result.project))
        monitor.save_monitor_state(self.cfg, self.monitor_state)

    def _handle_result(self, result, charter):
        debounce = self.monitor_state.setdefault("debounce", {})
        key = result.key()
        incidents = self.journal.open_incidents()

        if result.ok:
            debounce.pop(key, None)
            if key in incidents:
                inc = incidents[key]
                self.journal.close_incident(result.project, result.check,
                                            "normalizado")
                reporting.incident_healed(
                    self.orion, result.project, result.check,
                    inc.get("last_action") or "normalizou sem intervenção",
                    time.time() - inc.get("opened_epoch", time.time()),
                    inc.get("attempts", 0))
            return

        # falhou: debounce antes de abrir incidente
        needed = self.cfg.threshold("fails_before_incident")
        count = debounce.get(key, 0) + 1
        debounce[key] = count
        if count < needed and result.severity != monitor.SEV_CRIT:
            return

        is_new = key not in incidents
        incident = self.journal.open_incident(result.project, result.check,
                                              result.detail, result.severity)
        if is_new:
            daily = self.learning.record_incident(key)
            reporting.incident_opened(self.orion, incident, result.evidence)
            if self.learning.is_chronic(key):
                reporting.incident_chronic(self.orion, result.project,
                                           result.check, daily,
                                           self.learning.hour_pattern(key))

        # healing
        can, reason = self.healer.can_heal(charter, result)
        if not can:
            if is_new and result.fixable and not incident.get("escalated"):
                self.journal.update_incident(result.project, result.check,
                                             escalated=True)
                if "observação" not in reason and "informativa" not in reason:
                    reporting.incident_escalated(
                        self.orion, result.project, result.check,
                        result.detail, reason, [])
            return

        outcome = self.healer.heal(charter, result,
                                   lambda: self._recheck(result, charter))
        self.journal.update_incident(
            result.project, result.check,
            attempts=incident.get("attempts", 0) + outcome["attempts"],
            last_action=outcome.get("action"))
        if outcome["healed"]:
            inc = self.journal.close_incident(result.project, result.check,
                                              "corrigido: %s" % outcome["action"])
            debounce.pop(key, None)
            reporting.incident_healed(
                self.orion, result.project, result.check, outcome["action"],
                time.time() - (inc or {}).get("opened_epoch", time.time()),
                outcome["attempts"])
        elif outcome["escalate"] and not incident.get("escalated"):
            self.journal.update_incident(result.project, result.check,
                                         escalated=True)
            reporting.incident_escalated(self.orion, result.project,
                                         result.check, result.detail,
                                         "ações esgotadas", outcome["log"])

    def _recheck(self, result, charter):
        if result.project == "_system":
            for again in monitor.system_checks(self.cfg):
                if again.key() == result.key():
                    return again
            return None
        if charter is None:
            return None
        for again in monitor.project_checks(self.cfg, charter,
                                            self.monitor_state):
            if again.key() == result.key():
                return again
        # checagem não reproduzida (ex.: log_errors) — considera resolvida
        return None

    def task_discovery(self):
        old = discovery.load_catalog(self.cfg)
        new = discovery.discover(self.cfg, self.journal)
        discovery.save_catalog(self.cfg, new)
        added, removed, changed = discovery.diff_catalog(old, new)
        drafts = charter_mod.sync_with_catalog(self.cfg, self.journal, new)
        for draft in drafts:
            reporting.new_project(self.orion, draft)
        for pid in removed:
            c = charter_mod.load_charter(self.cfg, pid)
            if c and c.get("status") != charter_mod.STATUS_IGNORED:
                reporting.project_removed(self.orion, pid)
        # drift estrutural vs baseline aprendido
        charters = charter_mod.all_charters(self.cfg)
        for pid, c in charters.items():
            if c.get("status") != charter_mod.STATUS_CONFIRMED:
                continue
            drifts = self.learning.baseline_drift(c, c.get("observed"))
            if drifts:
                last = self.monitor_state.setdefault("drift_notified", {})
                stamp = ";".join(drifts)
                if last.get(pid) != stamp:
                    last[pid] = stamp
                    self.orion.send(
                        "📐 [%s] desvio do padrão aprendido:\n%s\n"
                        "Se a mudança é intencional, atualize o charter ou "
                        "aguarde novo baseline após 7 dias estáveis."
                        % (pid, "\n".join("  • " + d for d in drifts)))
        if added or removed or changed:
            self.journal.log("discovery", "catálogo atualizado",
                             data={"novos": added, "removidos": removed,
                                   "alterados": [c["id"] for c in changed]})

    def task_hygiene(self):
        charters = charter_mod.all_charters(self.cfg)
        all_notes = []
        for pid, c in charters.items():
            if c.get("status") == charter_mod.STATUS_IGNORED:
                continue
            findings, notes = hygiene.scan_project(self.cfg, c)
            hygiene.register_findings(self.cfg, self.journal, pid, findings)
            all_notes.extend("[%s] %s" % (pid, n) for n in notes)
        self.weekly_cache["hygiene_notes"] = all_notes
        hygiene.purge_quarantine(self.cfg, self.journal)
        self.journal.prune()
        pending = hygiene.pending_summary(self.cfg)
        if pending:
            self.orion.send(pending, silent=True)

    def task_updates(self):
        charters = charter_mod.all_charters(self.cfg)
        findings = []
        for pid, c in charters.items():
            if c.get("status") == charter_mod.STATUS_IGNORED:
                continue
            result = updates.check_project_updates(self.cfg, self.journal, c)
            if result["available"] or result["applied"]:
                findings.append(result)
                if result.get("applied") and result.get("test_ok") is False:
                    self.orion.send("🆘 [%s] atualização aplicada mas o teste "
                                    "FALHOU: %s" % (pid, result["detail"]))
        apt = updates.check_apt_security(self.cfg)
        if apt:
            findings.append({"project": "_system",
                             "detail": "%d pacote(s) do sistema com "
                                       "atualização pendente" % apt})
        self.weekly_cache["updates"] = findings

    def task_learning(self):
        charters = charter_mod.all_charters(self.cfg)
        incidents = self.journal.open_incidents()
        recent = self.journal.recent(limit=500, kind="incident",
                                     since_epoch=time.time() - 86400)
        for pid, c in charters.items():
            if c.get("status") != charter_mod.STATUS_CONFIRMED:
                continue
            had_incident = any(i["project"] == pid for i in incidents.values()) \
                or any(r.get("project") == pid for r in recent)
            self.learning.maybe_snapshot_baseline(c, had_incident)

    def task_selfcare(self):
        check_self_memory(self.cfg, self.journal, self.orion)
        verify_state(self.cfg, self.journal)

    def task_forecast(self):
        result = monitor.disk_forecast(self.cfg)
        if result and not result.ok:
            key = result.key()
            last = self.monitor_state.setdefault("forecast_notified", 0)
            if time.time() - last > 86400:
                self.monitor_state["forecast_notified"] = time.time()
                self.orion.send("📈 " + result.detail)

    def task_digests(self):
        now = datetime.datetime.now()
        state = read_json(self.cfg.state_file("digests.json"),
                          default={"daily": "", "weekly": ""})
        today = now.strftime("%Y-%m-%d")
        if now.hour >= self.cfg.get("digest_hour", default=8) and \
                state.get("daily") != today:
            state["daily"] = today
            catalog = discovery.load_catalog(self.cfg)
            charters = charter_mod.all_charters(self.cfg)
            reporting.daily_digest(self.cfg, self.journal, self.learning,
                                   self.orion, catalog, charters)
            if now.weekday() == self.cfg.get("weekly_digest_day", default=0) \
                    and state.get("weekly") != today:
                state["weekly"] = today
                reporting.weekly_report(
                    self.cfg, self.journal, self.learning, self.orion,
                    charters, self.weekly_cache.get("hygiene_notes", []),
                    self.weekly_cache.get("updates", []))
            atomic_write_json(self.cfg.state_file("digests.json"), state)

    # --- comandos Telegram -------------------------------------------------------------
    def _register_commands(self):
        o = self.orion
        aliases = {
            "status": self.cmd_status, "saude": self.cmd_status,
            "projetos": self.cmd_projects, "projects": self.cmd_projects,
            "confirmar": self.cmd_confirm, "confirm": self.cmd_confirm,
            "ignorar": self.cmd_ignore, "ignore": self.cmd_ignore,
            "aprovar": self.cmd_approve, "approve": self.cmd_approve,
            "rejeitar": self.cmd_reject, "reject": self.cmd_reject,
            "restaurar": self.cmd_restore, "restore": self.cmd_restore,
            "propostas": self.cmd_proposals, "proposals": self.cmd_proposals,
            "relatorio": self.cmd_report, "report": self.cmd_report,
            "missao": self.cmd_mission, "mission": self.cmd_mission,
            "pausar": self.cmd_pause, "pause": self.cmd_pause,
            "retomar": self.cmd_resume, "resume": self.cmd_resume,
            "ajuda": self.cmd_help, "help": self.cmd_help,
        }
        for name, fn in aliases.items():
            o.register(name, fn)

    def cmd_status(self, args, chat):
        catalog = discovery.load_catalog(self.cfg)
        charters = charter_mod.all_charters(self.cfg)
        text = reporting.status_text(self.cfg, self.journal, catalog, charters)
        if self.paused:
            text = "⏸ PAUSADO (healing suspenso; /retomar para voltar)\n" + text
        return text

    def cmd_projects(self, args, chat):
        charters = charter_mod.all_charters(self.cfg)
        if not charters:
            return "Nenhum projeto catalogado ainda."
        return "\n\n".join(charter_mod.summarize(c)
                           for c in sorted(charters.values(),
                                           key=lambda c: c["id"]))

    def cmd_confirm(self, args, chat):
        if not args:
            return "Uso: /confirmar <id-do-projeto>"
        c = charter_mod.confirm(self.cfg, self.journal, args[0])
        if not c:
            return "Não conheço o projeto '%s'." % args[0]
        return ("✅ Charter de '%s' confirmado. As regras agora são lei: "
                "desvio vira incidente e eu corrijo dentro dos limites."
                % args[0])

    def cmd_ignore(self, args, chat):
        if not args:
            return "Uso: /ignorar <id-do-projeto>"
        c = charter_mod.ignore(self.cfg, self.journal, args[0])
        return ("🚫 '%s' marcado como ignorado." % args[0]) if c else \
            "Não conheço o projeto '%s'." % args[0]

    def cmd_approve(self, args, chat):
        if not args:
            return "Uso: /aprovar <id-da-proposta> (veja /propostas)"
        prop, msg = hygiene.approve(self.cfg, self.journal, args[0])
        return "🧹 %s: %s" % (args[0], msg)

    def cmd_reject(self, args, chat):
        if not args:
            return "Uso: /rejeitar <id-da-proposta>"
        prop = hygiene.reject(self.cfg, self.journal, args[0])
        return ("Ok, proposta %s rejeitada — não mexo nesse caminho."
                % args[0]) if prop else "Proposta '%s' não existe." % args[0]

    def cmd_restore(self, args, chat):
        if not args:
            return "Uso: /restaurar <id-da-proposta>"
        result = hygiene.restore(self.cfg, self.journal, args[0])
        prop, msg = result if isinstance(result, tuple) else (None, "falhou")
        return "♻️ %s" % msg

    def cmd_proposals(self, args, chat):
        return hygiene.pending_summary(self.cfg, limit=25) or \
            "Nenhuma proposta pendente. 🧼"

    def cmd_report(self, args, chat):
        catalog = discovery.load_catalog(self.cfg)
        charters = charter_mod.all_charters(self.cfg)
        reporting.daily_digest(self.cfg, self.journal, self.learning,
                               self.orion, catalog, charters)
        return None  # o digest já foi enviado

    def cmd_mission(self, args, chat):
        if not args:
            return "Uso: /missao <id-do-projeto>"
        c = charter_mod.load_charter(self.cfg, args[0])
        if not c:
            return "Não conheço o projeto '%s'." % args[0]
        notes = c.get("notes") or []
        text = charter_mod.summarize(c)
        if notes:
            text += "\nÚltimas anotações:\n" + "\n".join(
                "  • %s %s" % (n["ts"][:10], n["note"]) for n in notes[-5:])
        return text

    def cmd_pause(self, args, chat):
        self._set_flag("paused", True)
        return "⏸ Pausado: continuo observando e registrando, mas não " \
               "executo correções até /retomar."

    def cmd_resume(self, args, chat):
        self._set_flag("paused", False)
        return "▶️ Retomado: healing ativo novamente."

    def cmd_help(self, args, chat):
        return ("🏛 Comandos do Governor:\n"
                "/status — visão geral e incidentes abertos\n"
                "/projetos — cartas de missão de todos os projetos\n"
                "/missao <id> — missão e anotações de um projeto\n"
                "/confirmar <id> — confirma a carta (ativa correções)\n"
                "/ignorar <id> — deixa de acompanhar o projeto\n"
                "/propostas — limpezas aguardando aprovação\n"
                "/aprovar <id> | /rejeitar <id> | /restaurar <id>\n"
                "/relatorio — resumo diário sob demanda\n"
                "/pausar | /retomar — suspende/reativa correções")


def _version():
    from . import __version__
    return __version__


def main():
    Daemon().run()
