"""Motor de correção (self-healing dos projetos).

Regras de segurança:
  - Só age em projetos com charter CONFIRMADO e rules.auto_heal = true.
    Caso contrário, apenas reporta (observe-only).
  - Cooldown por incidente e limite de correções/hora: acima do limite é
    flapping -> para de reiniciar em loop e ESCALA para o operador.
  - Toda correção é seguida de VERIFICAÇÃO (a checagem que falhou roda de
    novo). Sucesso e falha alimentam o learning (taxa de acerto por ação).
  - dry_run global: registra o que faria sem executar.

Playbooks padrão por tipo de checagem + playbooks custom por projeto em
playbooks/<project_id>.json:
  {"systemd": [["systemctl", "restart", "{unit}"]], ...}
"""

import os
import time

from .util import atomic_write_json, read_json, run_cmd, which

# ações padrão por prefixo de checagem; {token}s vêm do contexto do incidente
DEFAULT_ACTIONS = {
    "systemd": [
        {"name": "restart-unit", "cmd": ["systemctl", "restart", "{unit}"]},
        {"name": "daemon-reload+restart",
         "cmd": ["bash", "-c", "systemctl daemon-reload && systemctl restart {unit}"]},
    ],
    "docker": [
        {"name": "docker-restart", "cmd": ["docker", "restart", "{container}"]},
        {"name": "compose-up",
         "cmd": ["bash", "-c",
                 "cd {path} && (docker compose up -d || docker-compose up -d)"],
         "needs_path": True},
    ],
    "pm2": [
        {"name": "pm2-restart", "cmd": ["pm2", "restart", "{pm2name}"]},
    ],
    "port": [],   # porta caída: resolvida reiniciando o serviço dono (ver abaixo)
    "http": [],   # idem
    "disk": [
        {"name": "vacuum-journald",
         "cmd": ["journalctl", "--vacuum-size=200M"], "system": True},
        {"name": "docker-prune",
         "cmd": ["docker", "system", "prune", "-f"], "system": True,
         "requires": "docker"},
        {"name": "apt-clean", "cmd": ["apt-get", "clean"], "system": True,
         "requires": "apt-get"},
    ],
    "mem_trend": [
        # só entra se rules.proactive_restart = true (ver _actions_for)
        {"name": "proactive-restart", "cmd": None, "special": "restart_project"},
    ],
}


class Healer:
    def __init__(self, cfg, journal, learning):
        self.cfg = cfg
        self.journal = journal
        self.learning = learning
        self.state_path = cfg.state_file("healing.json")

    # --- estado (cooldowns / tentativas) -------------------------------------
    def _state(self):
        return read_json(self.state_path, default={})

    def _save(self, state):
        atomic_write_json(self.state_path, state)

    def _recent_attempts(self, key, window=3600):
        state = self._state()
        attempts = [t for t in state.get(key, []) if time.time() - t < window]
        return attempts

    def _record_attempt(self, key):
        state = self._state()
        attempts = [t for t in state.get(key, []) if time.time() - t < 7200]
        attempts.append(time.time())
        state[key] = attempts
        self._save(state)

    # --- decisão -------------------------------------------------------------
    def can_heal(self, charter, result):
        """(bool, motivo). Decide se o Governor pode agir neste incidente."""
        if not self.cfg.get("healing_enabled", default=True):
            return False, "healing desativado na config"
        if not result.fixable:
            return False, "checagem apenas informativa"
        if result.project == "_system":
            return True, ""  # ações de sistema são sempre seguras/idempotentes
        if charter is None:
            return False, "projeto sem charter"
        if charter.get("status") != "confirmed":
            return False, "charter ainda não confirmado (modo observação)"
        if not (charter.get("rules") or {}).get("auto_heal", True):
            return False, "auto_heal desativado no charter"
        max_per_hour = (charter.get("rules") or {}).get(
            "max_restarts_per_hour", self.cfg.threshold("max_heals_per_hour"))
        if len(self._recent_attempts(result.key())) >= max_per_hour:
            return False, "flapping: %d tentativas na última hora" % max_per_hour
        return True, ""

    # --- execução -------------------------------------------------------------
    def heal(self, charter, result, recheck_fn):
        """Tenta corrigir `result`. Devolve dict com o desfecho.

        recheck_fn() reexecuta a checagem e devolve CheckResult — é o
        "teste" de que a correção funcionou de verdade.
        """
        context = self._context(charter, result)
        actions = self._actions_for(charter, result, context)
        outcome = {"healed": False, "action": None, "attempts": 0,
                   "log": [], "escalate": False}
        if not actions:
            outcome["escalate"] = True
            outcome["log"].append("nenhum playbook aplicável")
            return outcome

        # learning ordena as ações pela taxa de sucesso histórica
        actions = self.learning.rank_actions(result.check, actions)

        for action in actions:
            if self.learning.is_quarantined(result.check, action["name"]):
                outcome["log"].append("ação %s em quarentena (falhou demais)"
                                      % action["name"])
                continue
            outcome["attempts"] += 1
            self._record_attempt(result.key())
            ok = self._run_action(action, context, outcome)
            if not ok:
                self.learning.record_action(result.check, action["name"], False)
                continue
            time.sleep(min(10, 3 * outcome["attempts"]))
            check = recheck_fn()
            verified = bool(check and check.ok)
            self.learning.record_action(result.check, action["name"], verified)
            outcome["log"].append("verificação pós-ação: %s"
                                  % ("OK" if verified else "ainda falhando"))
            if verified:
                outcome["healed"] = True
                outcome["action"] = action["name"]
                return outcome
        outcome["escalate"] = True
        return outcome

    def _run_action(self, action, context, outcome):
        if action.get("special") == "restart_project":
            return self._restart_project(context, outcome)
        cmd = action.get("cmd")
        if not cmd:
            return False
        cmd = [part.format(**context) for part in cmd]
        if self.cfg.dry_run:
            outcome["log"].append("[dry-run] executaria: %s" % " ".join(cmd))
            return True
        rc, out, err = run_cmd(cmd, timeout=180, cwd=context.get("path") or None)
        outcome["log"].append("%s -> rc=%d %s" % (action["name"], rc,
                                                  (err or out)[:200]))
        self.journal.log("heal", "ação %s (rc=%d)" % (action["name"], rc),
                         project=context.get("project"),
                         data={"cmd": cmd, "rc": rc, "err": err[:500]})
        return rc == 0

    def _restart_project(self, context, outcome):
        """Reinício controlado do projeto inteiro (a unidade que existir)."""
        charter = context.get("charter") or {}
        done = False
        for unit in charter.get("services") or []:
            ctx = dict(context, unit=unit)
            done |= self._run_action(
                {"name": "restart-unit", "cmd": ["systemctl", "restart", "{unit}"]},
                ctx, outcome)
        for container in charter.get("containers") or []:
            ctx = dict(context, container=container)
            done |= self._run_action(
                {"name": "docker-restart",
                 "cmd": ["docker", "restart", "{container}"]}, ctx, outcome)
        for name in charter.get("pm2") or []:
            ctx = dict(context, pm2name=name)
            done |= self._run_action(
                {"name": "pm2-restart", "cmd": ["pm2", "restart", "{pm2name}"]},
                ctx, outcome)
        return done

    # --- seleção de ações -------------------------------------------------------
    def _context(self, charter, result):
        check = result.check
        target = check.split(":", 1)[1] if ":" in check else ""
        charter = charter or {}
        return {
            "project": result.project,
            "charter": charter,
            "path": charter.get("path", ""),
            "unit": target if check.startswith("systemd:") else
                    (charter.get("services") or [""])[0],
            "container": target if check.startswith("docker:") else
                         (charter.get("containers") or [""])[0],
            "pm2name": target if check.startswith("pm2:") else
                       (charter.get("pm2") or [""])[0],
        }

    def _actions_for(self, charter, result, context):
        prefix = result.check.split(":", 1)[0]
        custom = self._custom_playbook(result.project, prefix)
        if custom is not None:
            return custom
        actions = list(DEFAULT_ACTIONS.get(prefix, []))
        if prefix in ("port", "http"):
            # porta/endpoint caído: reinicia o que o projeto tiver de serviço
            charter = charter or {}
            if charter.get("services") or charter.get("containers") or \
                    charter.get("pm2"):
                actions = [{"name": "restart-project", "cmd": None,
                            "special": "restart_project"}]
        if prefix == "mem_trend":
            rules = (charter or {}).get("rules") or {}
            if not rules.get("proactive_restart"):
                return []
        out = []
        for action in actions:
            requires = action.get("requires")
            if requires and not which(requires):
                continue
            if action.get("needs_path") and not context.get("path"):
                continue
            out.append(action)
        return out

    def _custom_playbook(self, project_id, prefix):
        """Playbook custom: playbooks/<id>.json {"prefix": [[cmd...], ...]}"""
        path = os.path.join(self.cfg.playbooks_dir, "%s.json" % project_id)
        data = read_json(path, default=None)
        if not isinstance(data, dict) or prefix not in data:
            return None
        actions = []
        for i, cmd in enumerate(data[prefix]):
            if isinstance(cmd, list) and cmd:
                actions.append({"name": "custom-%s-%d" % (prefix, i), "cmd": cmd})
        return actions
