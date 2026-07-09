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

Desenho 24/7 ("nunca ficar travado"):
  - Tarefas LENTAS (discovery, hygiene, updates) rodam em threads de fundo;
    o loop principal (health/healing) nunca espera por elas.
  - O watchdog do systemd é alimentado por uma thread própria, mas SÓ
    enquanto o loop principal progride (watchdog_stall_limit). Loop travado
    -> pings param -> systemd mata e reinicia o processo (Restart=always).
  - Thread de fundo presa demais gera alerta e, persistindo, reinício limpo
    do processo inteiro — threads não são "matáveis" em Python; o processo é.
"""

import datetime
import hashlib
import signal
import sys
import threading
import time

from . import charter as charter_mod
from . import chat as chat_mod
from . import discovery, hygiene, idle, monitor, reporting, updates
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
        self._last_tick = time.time()
        self._bg_threads = {}    # nome -> Thread de tarefa lenta
        self._bg_started = {}    # nome -> epoch de início
        self._bg_warned = set()
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
        self._start_watchdog_thread()
        notify_ready()
        self.orion.send("🏛 Governor de pé e observando o servidor. "
                        "Use /ajuda para os comandos.", silent=True)
        while not self._stop:
            self._last_tick = time.time()
            # rápidas: rodam no loop principal
            self._run_due("health", self.cfg.interval("health"),
                          self.task_health)
            self._run_due("learning", self.cfg.interval("learning"),
                          self.task_learning)
            self._run_due("selfcare", self.cfg.interval("selfcare"),
                          self.task_selfcare)
            self._run_due("idle_guard", self.cfg.interval("idle_guard"),
                          self.task_idle_guard)
            self._run_due("flush_queue", self.cfg.interval("flush_queue"),
                          self.orion.flush_queue)
            self._run_due("forecast", 3600, self.task_forecast)
            self._run_due("digests", 300, self.task_digests)
            # lentas: threads de fundo, nunca bloqueiam o health
            self._run_due_bg("discovery", self.cfg.interval("discovery"),
                             self.task_discovery, first_run_now=True)
            self._run_due_bg("hygiene", self.cfg.interval("hygiene"),
                             self.task_hygiene)
            self._run_due_bg("updates", self.cfg.interval("updates"),
                             self.task_updates)
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

    def _run_due_bg(self, name, interval, fn, first_run_now=False):
        """Agenda tarefa lenta numa thread de fundo. Nunca roda duas
        instâncias da mesma tarefa ao mesmo tempo."""
        now = time.time()
        if name not in self._last_run and not first_run_now:
            self._last_run[name] = now  # primeira execução só após 1 intervalo
            return
        if now - self._last_run.get(name, 0) < interval and \
                name in self._last_run:
            return
        previous = self._bg_threads.get(name)
        if previous and previous.is_alive():
            return  # ainda rodando; tenta de novo no próximo tick
        self._last_run[name] = now
        self._bg_started[name] = now
        self._bg_warned.discard(name)
        thread = threading.Thread(
            target=lambda: self.bulkhead.run(name, fn),
            name="gov-" + name, daemon=True)
        self._bg_threads[name] = thread
        thread.start()

    # --- watchdog gated pelo progresso do loop -----------------------------------
    def _loop_alive(self):
        limit = self.cfg.get("watchdog_stall_limit", default=600)
        return (time.time() - self._last_tick) < limit

    def _watchdog_loop(self):
        starving = False
        while not self._stop:
            if self._loop_alive():
                notify_watchdog()
                starving = False
            elif not starving:
                starving = True
                try:
                    self.journal.log(
                        "selfcare", "loop principal sem progresso além do "
                        "limite; parei de alimentar o watchdog para o "
                        "systemd me reiniciar")
                except Exception:
                    pass
            time.sleep(30)

    def _start_watchdog_thread(self):
        thread = threading.Thread(target=self._watchdog_loop,
                                  name="gov-watchdog", daemon=True)
        thread.start()

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
                if self._notifica_tempo_real(result, charter):
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
            # Tempo real SÓ para projeto CONFIRMADO (ou sistema): o 1º scan
            # acha dezenas de projetos antigos com serviço parado DE PROPÓSITO
            # — alertar cada um na hora é rajada de ruído no Telegram. Draft
            # fica no journal e aparece no digest diário; confirmou, vira alerta.
            if self._notifica_tempo_real(result, charter):
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
                if "observação" not in reason and "informativa" not in reason \
                        and self._notifica_tempo_real(result, charter):
                    reporting.incident_escalated(
                        self.orion, result.project, result.check,
                        result.detail, reason, [])
            return

        outcome = self.healer.heal(charter, result,
                                   lambda: self._recheck(result, charter))
        # ações sensíveis (ex.: docker prune) não executam sozinhas — viram
        # pergunta com botões ✅/❌ pro operador (decisão do Rafa, 2026-07-06)
        for action in outcome.get("needs_approval") or []:
            self._request_sys_approval(result, action, charter)
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

    @staticmethod
    def _notifica_tempo_real(result, charter):
        """Alerta na hora só de sistema e de projeto CONFIRMADO — draft é
        observe-only também no Telegram (journal + digest diário cobrem).

        CORTE DE RUÍDO (Rafa 2026-07-09: "fica me mandando notificação e não
        conserta nada"): observação NÃO-ACIONÁVEL e NÃO-crítica (fixable=False +
        severity != critical — ex.: cert em 14d, erro de log, load alto, git
        drift, heartbeat velho) NÃO pinga em tempo real; vai só pro journal +
        DIGEST DIÁRIO. Em tempo real só o que é ACIONÁVEL (fixable, tem conserto)
        ou CRÍTICO. Escalonamento de conserto que falhou continua alertando à
        parte (não passa por aqui)."""
        if result.project != "_system" and \
                (charter or {}).get("status") != charter_mod.STATUS_CONFIRMED:
            return False
        if not result.fixable and result.severity != monitor.SEV_CRIT:
            return False
        return True

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
        # 1º scan do servidor acha DEZENAS de projetos — mensagem agrupada;
        # no dia-a-dia (1-3 novos), mensagem individual com botões ✅/🚫.
        if len(drafts) > 3:
            reporting.new_projects_batch(self.orion, drafts)
        else:
            for draft in drafts:
                reporting.new_project(self.orion, draft)
        self._notify_pending_declared()
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
            self.orion.send(pending, silent=True,
                            buttons=self._hygiene_buttons())

    def _hygiene_buttons(self, limit=3):
        """Botões ✅/❌ pras maiores propostas pendentes (o resto via /aprovar)."""
        props = [p for p in hygiene.load_proposals(self.cfg).values()
                 if p.get("status") == "pending"]
        props.sort(key=lambda p: -p.get("size", 0))
        rows = []
        for p in props[:limit]:
            rows.append([("✅ %s" % p["id"], "gov:approve:%s" % p["id"]),
                         ("❌ %s" % p["id"], "gov:reject:%s" % p["id"])])
        return rows or None

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

    BG_WARN_AFTER = 2 * 3600      # thread de fundo presa: avisa
    BG_RESTART_AFTER = 6 * 3600   # persistindo: reinicia o processo inteiro

    def task_selfcare(self):
        check_self_memory(self.cfg, self.journal, self.orion)
        verify_state(self.cfg, self.journal)
        for name, thread in list(self._bg_threads.items()):
            if not thread.is_alive():
                continue
            age = time.time() - self._bg_started.get(name, time.time())
            if age > self.BG_RESTART_AFTER:
                self.journal.log("selfcare", "tarefa '%s' presa há %.1fh; "
                                 "reiniciando o processo para me libertar"
                                 % (name, age / 3600))
                self.orion.send("🩺 Governor: minha tarefa '%s' está presa há "
                                "%.1fh (provável comando/FS pendurado). Vou "
                                "reiniciar a mim mesmo; o systemd me traz de "
                                "volta em 5s." % (name, age / 3600))
                sys.exit(1)
            if age > self.BG_WARN_AFTER and name not in self._bg_warned:
                self._bg_warned.add(name)
                self.journal.log("selfcare", "tarefa '%s' rodando há %.1fh — "
                                 "possível travamento" % (name, age / 3600))
                self.orion.send("🩺 Governor: minha tarefa '%s' roda há %.1fh "
                                "sem terminar. Se passar de %dh, reinicio a "
                                "mim mesmo por segurança."
                                % (name, age / 3600,
                                   self.BG_RESTART_AFTER // 3600), silent=True)

    def task_idle_guard(self):
        messages = idle.run(self.cfg, self.journal)
        if not self.cfg.get("idle_guard", "notify", default=True):
            return
        for message in messages[:5]:
            self.orion.send(message, silent=True)

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

    # --- aprovações com botões (ações sensíveis + .governor.json) ----------------------
    APPROVAL_TTL_S = 6 * 3600   # pendência de aprovação expira em 6h

    def _approvals(self):
        return read_json(self.cfg.state_file("approvals.json"), default={})

    def _save_approvals(self, data):
        atomic_write_json(self.cfg.state_file("approvals.json"), data)

    def _request_sys_approval(self, result, action, charter):
        """Pergunta (com botões) se pode executar uma ação sensível de healing.
        Dedup: a mesma ação pro mesmo incidente só pergunta 1x até expirar."""
        aid = hashlib.sha1(("%s|%s" % (result.key(), action["name"]))
                           .encode()).hexdigest()[:10]
        approvals = self._approvals()
        now = time.time()
        # limpa expiradas
        approvals = {k: v for k, v in approvals.items()
                     if now - v.get("created", 0) < self.APPROVAL_TTL_S}
        if aid in approvals:
            self._save_approvals(approvals)
            return  # já perguntei; aguardando o botão
        context = self.healer._context(charter, result)
        approvals[aid] = {
            "action": {k: v for k, v in action.items() if k != "charter"},
            "context": {k: v for k, v in context.items()
                        if isinstance(v, (str, int, float))},
            "check": result.check, "project": result.project,
            "detail": result.detail, "created": now,
        }
        self._save_approvals(approvals)
        cmd_txt = " ".join(action.get("cmd") or []) or action["name"]
        self.orion.send(
            "🛑 Preciso da sua autorização.\n"
            "Incidente: [%s] %s\n"
            "Ação proposta: %s\n(`%s`)\n\n"
            "⚠️ Essa ação remove dados de forma irreversível (ex.: containers "
            "parados e imagens sem uso). Autorizo?"
            % (result.project, result.detail, action["name"], cmd_txt),
            buttons=[[("✅ Autorizar", "gov:sys:%s:ok" % aid),
                      ("❌ Negar", "gov:sys:%s:no" % aid)]])

    def _handle_sys_approval(self, aid, ok):
        approvals = self._approvals()
        item = approvals.pop(aid, None)
        self._save_approvals(approvals)
        if not item:
            return ("Essa autorização não existe mais (expirou ou já foi "
                    "respondida).")
        if not ok:
            self.journal.log("heal", "operador NEGOU ação sensível %s"
                             % item["action"].get("name"),
                             project=item.get("project"))
            return "❌ Negado. Não executo '%s' — sigo só observando." \
                % item["action"].get("name")
        exec_ok, log_lines = self.healer.run_approved(item["action"],
                                                      dict(item.get("context") or {}))
        self.journal.log("heal", "operador AUTORIZOU ação sensível %s (ok=%s)"
                         % (item["action"].get("name"), exec_ok),
                         project=item.get("project"))
        status = "✅ Executado com sucesso" if exec_ok else \
            "⚠️ Executei mas o comando retornou erro"
        return "%s: %s\n%s" % (status, item["action"].get("name"),
                               "\n".join("  " + l for l in log_lines[-4:]))

    def _notify_pending_declared(self):
        """Charters confirmados com mudanças sensíveis vindas do .governor.json
        aguardando decisão — pergunta com botões (1x por versão da mudança)."""
        state = self.monitor_state.setdefault("declared_notified", {})
        for pid, c in charter_mod.all_charters(self.cfg).items():
            pend = c.get("pending_declared")
            if not pend:
                state.pop(pid, None)
                continue
            stamp = hashlib.sha1(repr(sorted(pend.items()))
                                 .encode()).hexdigest()[:10]
            if state.get(pid) == stamp:
                continue
            state[pid] = stamp
            campos = "\n".join("  • %s → %s" % (k, str(v)[:120])
                               for k, v in sorted(pend.items()))
            self.orion.send(
                "🛑 [%s] O .governor.json do projeto pede mudanças SENSÍVEIS "
                "(rodam como root / mudam minha autonomia):\n%s\n\n"
                "Aplico ao charter confirmado?" % (pid, campos),
                buttons=[[("✅ Aplicar", "gov:decl:%s:ok" % pid),
                          ("❌ Recusar", "gov:decl:%s:no" % pid)]])

    # --- comandos Telegram -------------------------------------------------------------
    def _register_commands(self):
        o = self.orion
        o.register_callback("gov", self.on_callback)
        o.chat_handler = self.on_chat
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
        return ("🏛 Sou o GOVERNANTE — descubro, vigio e corrijo os projetos "
                "deste VPS, e te pergunto (com botões) antes de qualquer ação "
                "sensível.\n\n"
                "💬 Fala comigo em texto normal (sem /) que eu respondo sobre "
                "o servidor: \"como estão os projetos?\", \"o que você fez "
                "hoje?\", \"por que o disco alertou?\".\n\n"
                "Comandos:\n"
                "/status — visão geral e incidentes abertos\n"
                "/projetos — cartas de missão de todos os projetos\n"
                "/missao <id> — missão e anotações de um projeto\n"
                "/confirmar <id> — confirma a carta (ativa correções)\n"
                "/ignorar <id> — deixa de acompanhar o projeto\n"
                "/propostas — limpezas aguardando aprovação\n"
                "/aprovar <id> | /rejeitar <id> | /restaurar <id>\n"
                "/relatorio — resumo diário sob demanda\n"
                "/pausar | /retomar — suspende/reativa correções")

    # --- botões inline -----------------------------------------------------------------
    def on_callback(self, data, chat):
        """Roteia cliques de botão: 'gov:<verbo>:<args...>'."""
        parts = data.split(":")
        verb = parts[1] if len(parts) > 1 else ""
        if verb == "confirm" and len(parts) > 2:
            return self.cmd_confirm([parts[2]], chat)
        if verb == "ignore" and len(parts) > 2:
            return self.cmd_ignore([parts[2]], chat)
        if verb == "approve" and len(parts) > 2:
            return self.cmd_approve([parts[2]], chat)
        if verb == "reject" and len(parts) > 2:
            return self.cmd_reject([parts[2]], chat)
        if verb == "sys" and len(parts) > 3:
            return self._handle_sys_approval(parts[2], parts[3] == "ok")
        if verb == "decl" and len(parts) > 3:
            pid, ok = parts[2], parts[3] == "ok"
            if ok:
                c = charter_mod.apply_pending_declared(self.cfg, self.journal, pid)
                return ("✅ Mudanças do .governor.json aplicadas ao charter "
                        "de '%s'." % pid) if c else \
                    "Nada pendente em '%s' (expirou ou já foi decidido)." % pid
            c = charter_mod.discard_pending_declared(self.cfg, self.journal, pid)
            return ("❌ Mudanças recusadas — o charter de '%s' segue como "
                    "estava." % pid) if c else \
                "Nada pendente em '%s' (expirou ou já foi decidido)." % pid
        return "Botão desconhecido (%s) — talvez de uma versão antiga." % data[:40]

    # --- conversa em linguagem natural ---------------------------------------------------
    def _chat_context(self):
        """Retrato compacto e REAL do VPS agora — o chão da conversa."""
        catalog = discovery.load_catalog(self.cfg)
        charters = charter_mod.all_charters(self.cfg)
        parts = []
        if self.paused:
            parts.append("⏸ HEALING PAUSADO pelo operador (/retomar religa).")
        parts.append(reporting.status_text(self.cfg, self.journal, catalog,
                                           charters))
        # Missões dos projetos CONFIRMADOS: dá ao cérebro de conversa o "o que é
        # cada projeto que eu guardo" (senão ele só sabe o id/status, não o quê).
        confirmados = [c for c in charters.values()
                       if c.get("status") == charter_mod.STATUS_CONFIRMED]
        if confirmados:
            parts.append("Projetos que eu guardo (confirmados) e o que fazem:")
            for c in sorted(confirmados, key=lambda c: c["id"])[:20]:
                parts.append("  • %s: %s" % (c["id"], (c.get("mission") or "?")[:180]))
        pend = hygiene.pending_summary(self.cfg, limit=6)
        if pend:
            parts.append(pend)
        approvals = self._approvals()
        if approvals:
            parts.append("Autorizações aguardando seu botão: %d"
                         % len(approvals))
        acts = self.journal.recent(limit=15, since_epoch=time.time() - 86400)
        if acts:
            parts.append("Minhas últimas ações/registros (24h):")
            for a in acts[-15:]:
                parts.append("  [%s]%s %s" % (
                    a.get("kind", "?"),
                    (" [" + a["project"] + "]") if a.get("project") else "",
                    (a.get("msg") or "")[:110]))
        return "\n".join(parts)

    def on_chat(self, text, chat):
        return chat_mod.answer(self.cfg, self.journal, text,
                               self._chat_context())


def _version():
    from . import __version__
    return __version__


def main():
    Daemon().run()
