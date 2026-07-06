"""Cartas de missão (charters) — a lógica confirmada de cada projeto.

Fluxo:
  1. O discovery encontra um projeto novo -> o Governor gera um charter
     RASCUNHO inferindo missão, serviços, portas, endpoints e regras.
  2. O Governor avisa pelo Orion e aguarda confirmação (/confirmar <id>
     no Telegram, `governorctl confirm <id>` na CLI, ou edição manual do
     JSON em charters/<id>.json mudando "status" para "confirmed").
  3. Enquanto rascunho: o projeto é APENAS OBSERVADO (monitor-only).
     Depois de confirmado: as regras viram lei — desvio = incidente,
     e o healing atua conforme as regras.

Um projeto pode se auto-declarar criando .governor.json na raiz:
  {"name": "...", "mission": "...", "endpoints": ["http://..."],
   "services": ["x.service"], "rules": {"auto_heal": true}}
Campos declarados têm prioridade sobre os inferidos.
"""

import glob
import json
import os
import re

from .util import atomic_write_json, now_iso, read_json

STATUS_DRAFT = "draft"
STATUS_CONFIRMED = "confirmed"
STATUS_IGNORED = "ignored"

DEFAULT_RULES = {
    "auto_heal": True,          # pode reiniciar/reparar serviços sozinho
    "auto_update": False,       # updates só com aprovação, por padrão
    "proactive_restart": False, # reinício preventivo em vazamento de memória
    "max_restarts_per_hour": 3,
    "expected_always_on": True, # projeto deve estar sempre de pé
}


def charter_path(cfg, project_id):
    return os.path.join(cfg.charters_dir, "%s.json" % project_id)


def load_charter(cfg, project_id):
    return read_json(charter_path(cfg, project_id), default=None)


def save_charter(cfg, charter):
    charter["updated_at"] = now_iso()
    atomic_write_json(charter_path(cfg, charter["id"]), charter)
    return charter


def all_charters(cfg):
    charters = {}
    for path in glob.glob(os.path.join(cfg.charters_dir, "*.json")):
        if path.endswith(".bak.json"):
            continue
        data = read_json(path, default=None)
        if data and data.get("id"):
            charters[data["id"]] = data
    return charters


def generate_draft(cfg, info):
    """Gera charter rascunho a partir do que o discovery encontrou."""
    path = info.get("path") or ""
    declared = info.get("declared") if isinstance(info.get("declared"), dict) else {}
    mission = declared.get("mission") or _infer_mission(path) or \
        "(missão não identificada — descreva aqui o objetivo do projeto)"

    endpoints = list(declared.get("endpoints") or [])
    if not endpoints:
        for port in sorted(info.get("ports") or []):
            endpoints.append("http://127.0.0.1:%d/" % port)

    rules = dict(DEFAULT_RULES)
    rules.update(declared.get("rules") or {})

    charter = {
        "id": info["id"],
        "name": declared.get("name") or info.get("name") or info["id"],
        "path": path,
        "status": STATUS_DRAFT,
        "mission": mission,
        "stacks": info.get("stacks") or [],
        "sources": info.get("sources") or [],
        "services": sorted(set((declared.get("services") or []) +
                               (info.get("services") or []))),
        "containers": sorted({c["name"] for c in info.get("containers") or []}),
        "pm2": sorted({p["name"] for p in info.get("pm2") or []}),
        "ports": sorted(info.get("ports") or []),
        "endpoints": endpoints,
        "log_paths": declared.get("log_paths") or _guess_logs(path),
        "domains": declared.get("domains") or [],   # p/ checagem de certificado
        "update_cmd": declared.get("update_cmd") or "",
        "test_cmd": declared.get("test_cmd") or "",
        "backup_paths": declared.get("backup_paths") or [],
        "rules": rules,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "learned": {},   # preenchido pelo learning (baseline, padrões)
        "notes": [],     # anotações vindas de `governorctl note` / Claude
    }
    return charter


def _infer_mission(path):
    """Extrai a missão do projeto de MISSION.md, README, CLAUDE.md ou package.json."""
    if not path or not os.path.isdir(path):
        return None
    for name in ("MISSION.md", "MISSAO.md"):
        text = _read_head(os.path.join(path, name))
        if text:
            return _first_paragraph(text)
    pkg = read_json(os.path.join(path, "package.json"), default=None)
    if isinstance(pkg, dict) and pkg.get("description"):
        return pkg["description"].strip()
    pyproject = os.path.join(path, "pyproject.toml")
    desc = _toml_description(pyproject)
    if desc:
        return desc
    for name in ("CLAUDE.md", "README.md", "readme.md", "README"):
        text = _read_head(os.path.join(path, name))
        if text:
            return _first_paragraph(text)
    return None


def _read_head(path, max_bytes=16384):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(max_bytes)
    except OSError:
        return None


def _first_paragraph(text):
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("!["):
            continue
        if stripped.startswith("[") and "](" in stripped:
            continue
        if not stripped:
            if lines:
                break
            continue
        lines.append(stripped)
        if sum(len(l) for l in lines) > 300:
            break
    summary = " ".join(lines).strip()
    return summary[:400] if summary else None


def _toml_description(path):
    text = _read_head(path)
    if not text:
        return None
    match = re.search(r'^description\s*=\s*"(.+?)"', text, re.MULTILINE)
    return match.group(1) if match else None


def _guess_logs(path):
    if not path or not os.path.isdir(path):
        return []
    logs = []
    for candidate in ("logs", "log"):
        full = os.path.join(path, candidate)
        if os.path.isdir(full):
            logs.append(full)
    for pattern in ("*.log",):
        logs.extend(sorted(glob.glob(os.path.join(path, pattern)))[:5])
    return logs[:10]


def sync_with_catalog(cfg, journal, catalog):
    """Garante charter para todo projeto do catálogo; devolve rascunhos novos.

    Também atualiza nos charters os fatos observados (portas/serviços novos
    aparecem em `observed_*` para o humano decidir se promove à regra).
    """
    new_drafts = []
    for pid, info in catalog.items():
        charter = load_charter(cfg, pid)
        if charter is None:
            charter = generate_draft(cfg, info)
            save_charter(cfg, charter)
            journal.log("charter", "rascunho criado — aguardando confirmação",
                        project=pid)
            new_drafts.append(charter)
            continue
        # anota drift estrutural sem alterar as regras confirmadas
        observed = {
            "services": sorted(set(info.get("services") or [])),
            "containers": sorted({c["name"] for c in info.get("containers") or []}),
            "ports": sorted(info.get("ports") or []),
        }
        if charter.get("observed") != observed:
            charter["observed"] = observed
            save_charter(cfg, charter)
        # .governor.json declarado re-sincroniza campos declarativos — MAS em
        # charter CONFIRMADO os campos SENSÍVEIS (update_cmd/test_cmd/rules,
        # que viram execução como root ou soltam a rédea do healing) NUNCA
        # entram direto: qualquer conta com escrita no diretório do projeto
        # poderia escalar privilégio por esse caminho. Eles ficam em
        # 'pending_declared' e o daemon PERGUNTA no Telegram (botões ✅/❌).
        declared = info.get("declared")
        if isinstance(declared, dict):
            changed = False
            confirmado = charter.get("status") == STATUS_CONFIRMED
            campos_livres = ["mission", "endpoints", "log_paths", "domains",
                             "backup_paths"]
            campos_sensiveis = ["update_cmd", "test_cmd"]
            if not confirmado:
                campos_livres = campos_livres + campos_sensiveis
            for field in campos_livres:
                if declared.get(field) and charter.get(field) != declared[field]:
                    charter[field] = declared[field]
                    changed = True
            if declared.get("rules") and not confirmado:
                merged = dict(charter.get("rules") or {})
                merged.update(declared["rules"])
                if merged != charter.get("rules"):
                    charter["rules"] = merged
                    changed = True
            if confirmado:
                pend = {}
                for field in campos_sensiveis:
                    if declared.get(field) and charter.get(field) != declared[field]:
                        pend[field] = declared[field]
                if declared.get("rules"):
                    merged = dict(charter.get("rules") or {})
                    merged.update(declared["rules"])
                    if merged != charter.get("rules"):
                        pend["rules"] = declared["rules"]
                # anti-loop: proposta idêntica à última RECUSADA não re-pergunta
                # (só volta a perguntar se o .governor.json mudar de novo)
                if pend and pend != charter.get("declared_rejected_last") and \
                        charter.get("pending_declared") != pend:
                    charter["pending_declared"] = pend
                    changed = True
                    journal.log("charter", "mudança SENSÍVEL no .governor.json "
                                "aguarda aprovação do operador", project=pid,
                                data={"campos": sorted(pend)})
                elif not pend and charter.get("pending_declared"):
                    charter.pop("pending_declared", None)
                    changed = True
            if changed:
                save_charter(cfg, charter)
                journal.log("charter", "atualizado a partir de .governor.json",
                            project=pid)
    return new_drafts


def apply_pending_declared(cfg, journal, project_id):
    """Operador APROVOU (botão): aplica as mudanças sensíveis pendentes."""
    charter = load_charter(cfg, project_id)
    if not charter or not charter.get("pending_declared"):
        return None
    pend = charter.pop("pending_declared")
    for field, value in pend.items():
        if field == "rules":
            merged = dict(charter.get("rules") or {})
            merged.update(value)
            charter["rules"] = merged
        else:
            charter[field] = value
    save_charter(cfg, charter)
    journal.log("charter", "mudanças sensíveis do .governor.json APROVADAS "
                "e aplicadas", project=project_id, data={"campos": sorted(pend)})
    return charter


def discard_pending_declared(cfg, journal, project_id):
    """Operador RECUSOU (botão): descarta as mudanças sensíveis pendentes."""
    charter = load_charter(cfg, project_id)
    if not charter or not charter.get("pending_declared"):
        return None
    pend = charter.pop("pending_declared")
    charter["declared_rejected_last"] = pend  # anti-loop no próximo sync
    charter.setdefault("declared_rejected", []).append(
        {"ts": now_iso(), "campos": sorted(pend)})
    charter["declared_rejected"] = charter["declared_rejected"][-10:]
    save_charter(cfg, charter)
    journal.log("charter", "mudanças sensíveis do .governor.json RECUSADAS",
                project=project_id, data={"campos": sorted(pend)})
    return charter


def confirm(cfg, journal, project_id):
    charter = load_charter(cfg, project_id)
    if charter is None:
        return None
    charter["status"] = STATUS_CONFIRMED
    charter["confirmed_at"] = now_iso()
    save_charter(cfg, charter)
    journal.log("charter", "confirmado pelo operador — regras ativas",
                project=project_id)
    return charter


def ignore(cfg, journal, project_id):
    charter = load_charter(cfg, project_id)
    if charter is None:
        return None
    charter["status"] = STATUS_IGNORED
    save_charter(cfg, charter)
    journal.log("charter", "marcado como ignorado pelo operador",
                project=project_id)
    return charter


def add_note(cfg, journal, project_id, note):
    charter = load_charter(cfg, project_id)
    if charter is None:
        return None
    charter.setdefault("notes", []).append({"ts": now_iso(), "note": note})
    charter["notes"] = charter["notes"][-50:]
    save_charter(cfg, charter)
    journal.log("note", note, project=project_id)
    return charter


def summarize(charter):
    """Resumo curto de um charter para mensagens do Orion."""
    lines = [
        "📁 %s (%s)" % (charter.get("name", charter["id"]), charter["id"]),
        "   Missão: %s" % charter.get("mission", "?"),
        "   Status: %s" % charter.get("status"),
    ]
    if charter.get("services"):
        lines.append("   Serviços: %s" % ", ".join(charter["services"]))
    if charter.get("containers"):
        lines.append("   Containers: %s" % ", ".join(charter["containers"]))
    if charter.get("ports"):
        lines.append("   Portas: %s" % ", ".join(str(p) for p in charter["ports"]))
    if charter.get("endpoints"):
        lines.append("   Endpoints: %s" % ", ".join(charter["endpoints"][:3]))
    return "\n".join(lines)
