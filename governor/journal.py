"""Diário de atividades e incidentes.

Tudo que o Governor faz, vê e conclui é registrado aqui — inclusive os
próprios erros (self-incidents), que alimentam o self-healing/learning.

Arquivos:
  journal/activity-AAAAMM.jsonl   — trilha de auditoria de tudo
  journal/self-AAAAMM.jsonl       — erros do próprio Governor
  state/incidents.json            — incidentes abertos no momento
"""

import glob
import os
import time
import traceback
from datetime import datetime

from .util import append_jsonl, atomic_write_json, now_iso, read_json, read_jsonl

# kinds usados em activity: discovery, charter, health, incident, heal,
# hygiene, proposal, learning, report, telegram, selfcare, note, update


class Journal:
    def __init__(self, cfg):
        self.cfg = cfg

    def _month_file(self, prefix):
        stamp = datetime.now().strftime("%Y%m")
        return os.path.join(self.cfg.journal_dir, "%s-%s.jsonl" % (prefix, stamp))

    # --- atividade geral ----------------------------------------------------
    def log(self, kind, message, project=None, data=None):
        record = {
            "ts": now_iso(),
            "epoch": time.time(),
            "kind": kind,
            "project": project,
            "msg": message,
        }
        if data:
            record["data"] = data
        append_jsonl(self._month_file("activity"), record)
        return record

    def recent(self, limit=50, kind=None, project=None, since_epoch=None):
        files = sorted(glob.glob(os.path.join(self.cfg.journal_dir, "activity-*.jsonl")))
        records = []
        for path in files[-2:]:  # mês atual + anterior é suficiente
            records.extend(read_jsonl(path))
        if kind:
            records = [r for r in records if r.get("kind") == kind]
        if project:
            records = [r for r in records if r.get("project") == project]
        if since_epoch:
            records = [r for r in records if r.get("epoch", 0) >= since_epoch]
        return records[-limit:]

    # --- erros do próprio Governor -------------------------------------------
    def self_error(self, subsystem, exc):
        record = {
            "ts": now_iso(),
            "epoch": time.time(),
            "subsystem": subsystem,
            "error": repr(exc),
            "traceback": traceback.format_exc(limit=8),
        }
        append_jsonl(self._month_file("self"), record)
        return record

    def self_errors_recent(self, hours=24):
        cutoff = time.time() - hours * 3600
        files = sorted(glob.glob(os.path.join(self.cfg.journal_dir, "self-*.jsonl")))
        records = []
        for path in files[-2:]:
            records.extend(r for r in read_jsonl(path) if r.get("epoch", 0) >= cutoff)
        return records

    # --- incidentes ----------------------------------------------------------
    def _incidents_path(self):
        return self.cfg.state_file("incidents.json")

    def open_incidents(self):
        return read_json(self._incidents_path(), default={})

    def open_incident(self, project, check, detail, severity="warning"):
        incidents = self.open_incidents()
        key = "%s:%s" % (project, check)
        if key in incidents:
            incidents[key]["last_seen"] = now_iso()
            incidents[key]["detail"] = detail
            incidents[key]["count"] = incidents[key].get("count", 1) + 1
        else:
            incidents[key] = {
                "project": project,
                "check": check,
                "detail": detail,
                "severity": severity,
                "opened_at": now_iso(),
                "opened_epoch": time.time(),
                "last_seen": now_iso(),
                "count": 1,
                "attempts": 0,
                "escalated": False,
            }
            self.log("incident", "aberto: %s" % detail, project=project,
                     data={"check": check, "severity": severity})
        atomic_write_json(self._incidents_path(), incidents)
        return incidents[key]

    def update_incident(self, project, check, **fields):
        incidents = self.open_incidents()
        key = "%s:%s" % (project, check)
        if key in incidents:
            incidents[key].update(fields)
            atomic_write_json(self._incidents_path(), incidents)
            return incidents[key]
        return None

    def close_incident(self, project, check, resolution):
        incidents = self.open_incidents()
        key = "%s:%s" % (project, check)
        incident = incidents.pop(key, None)
        if incident:
            duration = time.time() - incident.get("opened_epoch", time.time())
            self.log("incident", "resolvido: %s (%s)" % (resolution, check),
                     project=project,
                     data={"check": check, "duration_s": int(duration),
                           "attempts": incident.get("attempts", 0),
                           "resolution": resolution})
            atomic_write_json(self._incidents_path(), incidents)
        return incident

    # --- manutenção ----------------------------------------------------------
    def prune(self):
        """Remove meses de journal além da retenção configurada."""
        keep = self.cfg.get("journal", "retention_months", default=6)
        removed = []
        for prefix in ("activity", "self"):
            files = sorted(glob.glob(os.path.join(self.cfg.journal_dir, prefix + "-*.jsonl")))
            for path in files[:-keep]:
                try:
                    os.remove(path)
                    removed.append(os.path.basename(path))
                except OSError:
                    pass
        return removed
