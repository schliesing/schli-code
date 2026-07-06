"""Aprendizado e adaptação de padrões.

O que ele aprende:
  - Taxa de sucesso de cada ação de playbook por tipo de checagem ->
    ações boas sobem na fila; ações que falham 3x seguidas entram em
    quarentena (o Governor para de insistir e escala para o humano).
  - Frequência de incidentes por projeto/checagem -> incidente recorrente
    (>= 3 em 24h) é marcado como CRÔNICO: reiniciar não resolve; o Governor
    reporta pedindo investigação de causa-raiz em vez de mascarar.
  - Baseline ("estado bom conhecido") por projeto: depois de 7 dias sem
    incidente, o conjunto de serviços/portas/containers vira o padrão-ouro;
    qualquer desvio estrutural futuro é apontado como drift.
  - Janelas de padrão temporal: se incidentes se concentram num horário
    (ex.: 3h da manhã), isso aparece no relatório para investigação.
"""

import time
from collections import Counter

from .util import atomic_write_json, read_json, now_iso

STABLE_DAYS_FOR_BASELINE = 7
CHRONIC_THRESHOLD = 3        # incidentes iguais em 24h
QUARANTINE_AFTER_FAILS = 3   # falhas consecutivas de uma ação


class Learning:
    def __init__(self, cfg, journal):
        self.cfg = cfg
        self.journal = journal
        self.path = cfg.state_file("learning.json")

    def _load(self):
        return read_json(self.path, default={
            "actions": {},     # check_prefix -> action -> {ok, fail, streak_fail}
            "incidents": {},   # key -> [epochs]
            "baselines": {},   # project -> {snapshot, since}
        })

    def _save(self, data):
        atomic_write_json(self.path, data)

    # --- ações de playbook ------------------------------------------------------
    def _prefix(self, check):
        return check.split(":", 1)[0]

    def record_action(self, check, action_name, success):
        data = self._load()
        node = data["actions"].setdefault(self._prefix(check), {}).setdefault(
            action_name, {"ok": 0, "fail": 0, "streak_fail": 0})
        if success:
            node["ok"] += 1
            node["streak_fail"] = 0
        else:
            node["fail"] += 1
            node["streak_fail"] += 1
            if node["streak_fail"] == QUARANTINE_AFTER_FAILS:
                self.journal.log(
                    "learning", "ação '%s' para '%s' entrou em quarentena "
                    "(%d falhas seguidas)" % (action_name, self._prefix(check),
                                              QUARANTINE_AFTER_FAILS))
        self._save(data)

    def is_quarantined(self, check, action_name):
        data = self._load()
        node = data["actions"].get(self._prefix(check), {}).get(action_name)
        return bool(node and node.get("streak_fail", 0) >= QUARANTINE_AFTER_FAILS)

    def rank_actions(self, check, actions):
        """Ordena as ações pela taxa de sucesso histórica (melhor primeiro)."""
        data = self._load()
        stats = data["actions"].get(self._prefix(check), {})

        def score(action):
            node = stats.get(action["name"])
            if not node:
                return 0.5  # desconhecida: fica no meio
            total = node["ok"] + node["fail"]
            return (node["ok"] + 1.0) / (total + 2.0)  # suavização de Laplace

        return sorted(actions, key=score, reverse=True)

    # --- incidentes e padrões ------------------------------------------------------
    def record_incident(self, key):
        data = self._load()
        epochs = [e for e in data["incidents"].get(key, [])
                  if time.time() - e < 7 * 86400]
        epochs.append(time.time())
        data["incidents"][key] = epochs
        self._save(data)
        return len([e for e in epochs if time.time() - e < 86400])

    def is_chronic(self, key):
        data = self._load()
        recent = [e for e in data["incidents"].get(key, [])
                  if time.time() - e < 86400]
        return len(recent) >= CHRONIC_THRESHOLD

    def hour_pattern(self, key):
        """Se >=60% dos incidentes caem na mesma janela de 2h, devolve a hora."""
        data = self._load()
        epochs = data["incidents"].get(key, [])
        if len(epochs) < 3:
            return None
        hours = Counter(time.localtime(e).tm_hour // 2 * 2 for e in epochs)
        hour, count = hours.most_common(1)[0]
        if count / len(epochs) >= 0.6:
            return "%02dh-%02dh" % (hour, hour + 2)
        return None

    # --- baseline (estado bom conhecido) ---------------------------------------------
    def maybe_snapshot_baseline(self, charter, had_recent_incident):
        """Consolida baseline quando o projeto está estável há tempo suficiente."""
        data = self._load()
        pid = charter["id"]
        node = data["baselines"].setdefault(pid, {"stable_since": time.time(),
                                                  "snapshot": None})
        if had_recent_incident:
            node["stable_since"] = time.time()
            self._save(data)
            return None
        stable_for = time.time() - node["stable_since"]
        snapshot = {
            "services": sorted(charter.get("services") or []),
            "containers": sorted(charter.get("containers") or []),
            "ports": sorted(charter.get("ports") or []),
        }
        if stable_for >= STABLE_DAYS_FOR_BASELINE * 86400 and \
                node.get("snapshot") != snapshot:
            node["snapshot"] = snapshot
            node["snapshot_at"] = now_iso()
            self._save(data)
            self.journal.log("learning", "baseline consolidado (estado bom "
                             "conhecido após %d dias estável)"
                             % STABLE_DAYS_FOR_BASELINE, project=pid,
                             data=snapshot)
            return snapshot
        self._save(data)
        return None

    def baseline_drift(self, charter, observed):
        """Compara o observado agora com o baseline. Devolve lista de desvios."""
        data = self._load()
        snapshot = (data["baselines"].get(charter["id"]) or {}).get("snapshot")
        if not snapshot or not observed:
            return []
        drifts = []
        for field in ("services", "containers", "ports"):
            expected = set(str(x) for x in snapshot.get(field) or [])
            current = set(str(x) for x in observed.get(field) or [])
            missing = expected - current
            extra = current - expected
            if missing:
                drifts.append("%s sumiram do padrão: %s"
                              % (field, ", ".join(sorted(missing))))
            if extra:
                drifts.append("%s novos fora do padrão: %s"
                              % (field, ", ".join(sorted(extra))))
        return drifts

    # --- resumo p/ relatórios ------------------------------------------------------
    def insights(self):
        data = self._load()
        lines = []
        for key, epochs in sorted(data["incidents"].items()):
            recent = [e for e in epochs if time.time() - e < 7 * 86400]
            if len(recent) >= CHRONIC_THRESHOLD:
                pattern = self.hour_pattern(key)
                line = "🔁 %s: %d incidentes na semana" % (key, len(recent))
                if pattern:
                    line += " (concentrados em %s)" % pattern
                lines.append(line)
        for prefix, actions in data["actions"].items():
            for name, node in actions.items():
                if node.get("streak_fail", 0) >= QUARANTINE_AFTER_FAILS:
                    lines.append("🚫 playbook '%s' (%s) em quarentena — precisa "
                                 "de revisão humana" % (name, prefix))
        return lines
