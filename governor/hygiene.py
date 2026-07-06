"""Higiene — melhorias reais, não só erros.

Procura por:
  - arquivos-lixo: *.bak, *.old, *~, *.orig, "copia", "final_v2", .DS_Store...
  - duplicados exatos (mesmo hash) acima de um tamanho mínimo
  - logs gigantes ou sem rotação
  - caches recriáveis: __pycache__, .pytest_cache, node_modules órfão
  - symlinks mortos
  - código possivelmente órfão (fonte nunca referenciada no projeto) — vira
    sugestão de REVISÃO, nunca proposta de remoção automática
  - .env com permissões abertas demais (nota de segurança)

Segurança em camadas:
  1. Achado -> vira PROPOSTA pendente (nada acontece sem aprovação).
  2. Aprovada -> o arquivo vai para QUARENTENA (move, não deleta),
     restaurável por `governorctl restore <id>`.
  3. Só após `quarantine.retention_days` a quarentena é purgada de fato.
"""

import fnmatch
import os
import re
import shutil
import time
import uuid

from .util import (atomic_write_json, human_bytes, read_json, sha256_file,
                   dir_size, now_iso)

JUNK_PATTERNS = (
    "*.bak", "*.old", "*.orig", "*.rej", "*~", "*.swp", "*.swo",
    ".DS_Store", "Thumbs.db", "*.pyc", "core.[0-9]*", "npm-debug.log*",
    "*.tmp", "*.temp",
)
VERSIONED_RE = re.compile(
    r"^(?P<stem>.+?)[ _-](?:copy|copia|cópia|backup|old|final|v\d+|\(\d+\))"
    r"(?P<ext>\.[A-Za-z0-9]+)?$", re.IGNORECASE)
CACHE_DIRS = ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
              ".parcel-cache", ".turbo")
SOURCE_EXTS = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".php", ".rb")


def proposals_path(cfg):
    return cfg.state_file("proposals.json")


def load_proposals(cfg):
    return read_json(proposals_path(cfg), default={})


def save_proposals(cfg, proposals):
    atomic_write_json(proposals_path(cfg), proposals)


def scan_project(cfg, charter):
    """Varre um projeto e devolve (findings, review_notes).

    findings   -> candidatos a limpeza (viram propostas)
    review_notes -> observações que pedem olho humano (código órfão, .env...)
    """
    path = charter.get("path")
    if not path or not os.path.isdir(path):
        return [], []
    exclude = set(cfg.get("exclude_dirs", default=[]) or []) - {"__pycache__"}
    findings = []
    notes = []
    by_hash = {}
    log_limit = cfg.threshold("log_size_mb") * 1024 * 1024
    dup_min = cfg.threshold("dup_min_mb") * 1024 * 1024
    file_count = 0

    for root, dirs, files in os.walk(path, topdown=True, onerror=lambda e: None):
        dirs[:] = [d for d in dirs if d not in exclude and d != ".git"]
        for d in list(dirs):
            full = os.path.join(root, d)
            if d in CACHE_DIRS:
                findings.append(_finding(full, "cache recriável (%s)" % d,
                                         dir_size(full), "cache"))
                dirs.remove(d)
            elif d == "node_modules" and not os.path.exists(
                    os.path.join(root, "package.json")):
                findings.append(_finding(full, "node_modules órfão "
                                         "(sem package.json ao lado)",
                                         dir_size(full), "orphan-deps"))
                dirs.remove(d)
        for name in files:
            file_count += 1
            if file_count > 100000:
                notes.append("projeto com >100k arquivos; varredura parcial")
                return findings, notes
            full = os.path.join(root, name)
            try:
                st = os.lstat(full)
            except OSError:
                continue
            if os.path.islink(full) and not os.path.exists(full):
                findings.append(_finding(full, "symlink morto", 0, "dead-link"))
                continue
            if any(fnmatch.fnmatch(name, pat) for pat in JUNK_PATTERNS):
                findings.append(_finding(full, "arquivo-lixo (%s)" % name,
                                         st.st_size, "junk"))
                continue
            sibling = _dead_version_sibling(root, name)
            if sibling:
                findings.append(_finding(
                    full, "versão morta — original '%s' existe ao lado"
                    % sibling, st.st_size, "dead-version"))
                continue
            if name.endswith(".log") and st.st_size > log_limit:
                findings.append(_finding(
                    full, "log gigante (%s) sem rotação aparente"
                    % human_bytes(st.st_size), st.st_size, "big-log",
                    action="rotate"))
                continue
            if name.startswith(".env"):
                mode = st.st_mode & 0o777
                if mode & 0o044:
                    notes.append("⚠️ %s legível por outros usuários (chmod 600 "
                                 "recomendado)" % full)
            if st.st_size >= dup_min and st.st_size < 2 * 1024 ** 3:
                key = (st.st_size,)
                by_hash.setdefault(key, []).append(full)

    # duplicados: só calcula hash quando há colisão de tamanho
    for size_key, paths in by_hash.items():
        if len(paths) < 2:
            continue
        digests = {}
        for p in paths:
            digest = sha256_file(p)
            if digest:
                digests.setdefault(digest, []).append(p)
        for digest, dupes in digests.items():
            if len(dupes) > 1:
                keep = min(dupes, key=len)  # mantém o caminho mais curto
                for extra in dupes:
                    if extra != keep:
                        findings.append(_finding(
                            extra, "duplicado exato de %s" % keep,
                            size_key[0], "duplicate"))

    notes.extend(_orphan_sources(path, exclude))
    return findings, notes


def _finding(path, reason, size, category, action="quarantine"):
    return {"path": path, "reason": reason, "size": size,
            "category": category, "action": action}


def _dead_version_sibling(root, name):
    """Se `name` parece versão morta (final_v2, copia, backup...), devolve o
    nome do original que existe ao lado. Remove sufixos iterativamente para
    lidar com compostos como 'dados final_v2.csv' -> 'dados.csv'."""
    current = name
    for _ in range(3):
        match = VERSIONED_RE.match(current)
        if not match:
            return None
        candidate = match.group("stem") + (match.group("ext") or "")
        if candidate != name and os.path.exists(os.path.join(root, candidate)):
            return candidate
        # tenta remover mais um sufixo mantendo a extensão
        current = candidate
    return None


def _orphan_sources(path, exclude):
    """Heurística conservadora de código órfão: arquivo-fonte cujo nome-base
    nunca aparece em nenhum outro fonte do projeto. Gera NOTA de revisão."""
    sources = []
    for root, dirs, files in os.walk(path, topdown=True, onerror=lambda e: None):
        dirs[:] = [d for d in dirs if d not in exclude and d != ".git"
                   and d not in CACHE_DIRS and d != "node_modules"]
        for name in files:
            if name.endswith(SOURCE_EXTS):
                sources.append(os.path.join(root, name))
        if len(sources) > 2000:
            return []  # projeto grande demais p/ esta heurística barata
    if len(sources) < 3:
        return []
    corpus = []
    for src in sources:
        try:
            with open(src, "r", encoding="utf-8", errors="replace") as fh:
                corpus.append(fh.read(200 * 1024))
        except OSError:
            corpus.append("")
    notes = []
    entry_names = {"index", "main", "app", "server", "manage", "wsgi", "asgi",
                   "setup", "conftest", "__init__", "__main__", "config",
                   "settings", "vite.config", "next.config", "ecosystem.config"}
    for i, src in enumerate(sources):
        stem = os.path.splitext(os.path.basename(src))[0]
        if stem.lower() in entry_names or stem.startswith("test"):
            continue
        referenced = any(stem in text for j, text in enumerate(corpus) if j != i)
        if not referenced:
            rel = os.path.relpath(src, path)
            notes.append("🧐 possível código órfão (nunca referenciado): %s" % rel)
        if len(notes) >= 15:
            break
    return notes


# --- propostas / aprovação / quarentena ------------------------------------------

def register_findings(cfg, journal, project_id, findings):
    """Converte achados em propostas pendentes (dedupe por caminho)."""
    proposals = load_proposals(cfg)
    existing_paths = {p["path"] for p in proposals.values()
                      if p["status"] in ("pending", "approved")}
    added = []
    for finding in findings:
        if finding["path"] in existing_paths:
            continue
        pid = "cl-" + uuid.uuid4().hex[:6]
        proposals[pid] = {
            "id": pid,
            "project": project_id,
            "path": finding["path"],
            "reason": finding["reason"],
            "size": finding["size"],
            "category": finding["category"],
            "action": finding.get("action", "quarantine"),
            "status": "pending",
            "created_at": now_iso(),
        }
        added.append(proposals[pid])
    if added:
        save_proposals(cfg, proposals)
        journal.log("proposal", "%d nova(s) proposta(s) de limpeza" % len(added),
                    project=project_id,
                    data={"ids": [p["id"] for p in added]})
    return added


def approve(cfg, journal, proposal_id):
    """Executa uma proposta aprovada: move p/ quarentena (ou rotaciona log)."""
    proposals = load_proposals(cfg)
    prop = proposals.get(proposal_id)
    if not prop:
        return None, "proposta %s não existe" % proposal_id
    if prop["status"] != "pending":
        return None, "proposta %s já está '%s'" % (proposal_id, prop["status"])
    path = prop["path"]
    if not os.path.exists(path) and not os.path.islink(path):
        prop["status"] = "gone"
        save_proposals(cfg, proposals)
        return prop, "o caminho já não existe"
    if cfg.dry_run:
        journal.log("hygiene", "[dry-run] aprovaria %s" % path)
        return prop, "[dry-run] nada executado"
    try:
        if prop["action"] == "rotate":
            _rotate_log(path)
            prop["status"] = "done"
            msg = "log rotacionado (truncado com cópia .1.gz)"
        else:
            dest = _quarantine_move(cfg, prop)
            prop["status"] = "quarantined"
            prop["quarantine_path"] = dest
            prop["quarantined_at"] = now_iso()
            msg = "movido para quarentena (restaure com: governorctl restore %s)" \
                % proposal_id
    except OSError as exc:
        prop["status"] = "error"
        prop["error"] = str(exc)
        msg = "falhou: %s" % exc
    save_proposals(cfg, proposals)
    journal.log("hygiene", "proposta %s: %s" % (proposal_id, msg),
                project=prop["project"], data={"path": path})
    return prop, msg


def reject(cfg, journal, proposal_id):
    proposals = load_proposals(cfg)
    prop = proposals.get(proposal_id)
    if not prop:
        return None
    prop["status"] = "rejected"
    save_proposals(cfg, proposals)
    journal.log("hygiene", "proposta %s rejeitada pelo operador" % proposal_id,
                project=prop["project"])
    return prop


def restore(cfg, journal, proposal_id):
    proposals = load_proposals(cfg)
    prop = proposals.get(proposal_id)
    if not prop or prop.get("status") != "quarantined":
        return None, "proposta não está em quarentena"
    src = prop.get("quarantine_path")
    if not src or not os.path.exists(src):
        return None, "conteúdo da quarentena não encontrado"
    shutil.move(src, prop["path"])
    prop["status"] = "restored"
    save_proposals(cfg, proposals)
    journal.log("hygiene", "proposta %s restaurada para %s"
                % (proposal_id, prop["path"]), project=prop["project"])
    return prop, "restaurado para %s" % prop["path"]


def purge_quarantine(cfg, journal):
    """Remove da quarentena o que passou da retenção. Devolve nº purgado."""
    retention = cfg.get("quarantine", "retention_days", default=14) * 86400
    proposals = load_proposals(cfg)
    purged = 0
    for prop in proposals.values():
        if prop.get("status") != "quarantined":
            continue
        qpath = prop.get("quarantine_path")
        if not qpath or not os.path.exists(qpath):
            continue
        try:
            age = time.time() - os.stat(qpath).st_mtime
        except OSError:
            continue
        if age > retention:
            try:
                if os.path.isdir(qpath):
                    shutil.rmtree(qpath)
                else:
                    os.remove(qpath)
                prop["status"] = "purged"
                purged += 1
            except OSError:
                continue
    if purged:
        save_proposals(cfg, proposals)
        journal.log("hygiene", "quarentena purgada: %d item(ns) definitivamente "
                    "removido(s) após retenção" % purged)
    return purged


def _quarantine_move(cfg, prop):
    stamp = time.strftime("%Y%m%d")
    dest_dir = os.path.join(cfg.quarantine_dir, stamp)
    os.makedirs(dest_dir, exist_ok=True)
    base = "%s__%s" % (prop["id"], os.path.basename(prop["path"].rstrip("/")))
    dest = os.path.join(dest_dir, base)
    shutil.move(prop["path"], dest)
    return dest


def _rotate_log(path):
    import gzip
    rotated = path + ".1.gz"
    with open(path, "rb") as src, gzip.open(rotated, "wb") as dst:
        shutil.copyfileobj(src, dst)
    with open(path, "w"):
        pass  # trunca mantendo o descritor dos processos válido


def pending_summary(cfg, limit=15):
    proposals = load_proposals(cfg)
    pending = [p for p in proposals.values() if p["status"] == "pending"]
    pending.sort(key=lambda p: -p.get("size", 0))
    if not pending:
        return None
    total = sum(p.get("size", 0) for p in pending)
    lines = ["🧹 Propostas de limpeza pendentes: %d (total %s)"
             % (len(pending), human_bytes(total)),
             "Aprove com /aprovar <id> ou rejeite com /rejeitar <id>:"]
    for p in pending[:limit]:
        lines.append("  %s — %s (%s) [%s]" % (p["id"], p["path"],
                                              human_bytes(p.get("size", 0)),
                                              p["reason"]))
    if len(pending) > limit:
        lines.append("  ... e mais %d (veja: governorctl proposals)"
                     % (len(pending) - limit))
    return "\n".join(lines)
