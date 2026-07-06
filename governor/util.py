"""Utilitários de base: IO atômico, subprocessos, hashing, formatação."""

import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone


def now_ts():
    return time.time()


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def utc_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def read_json(path, default=None):
    """Lê JSON; em caso de corrupção tenta o .bak antes de devolver default."""
    for candidate in (path, path + ".bak"):
        try:
            with open(candidate, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            continue
        except (json.JSONDecodeError, OSError):
            continue
    return default


def atomic_write_json(path, data):
    """Escrita atômica (tmp + rename) preservando a versão anterior em .bak."""
    ensure_dir(os.path.dirname(path) or ".")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    if os.path.exists(path):
        try:
            shutil.copy2(path, path + ".bak")
        except OSError:
            pass
    os.replace(tmp, path)


def append_jsonl(path, record):
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path, limit=None):
    """Lê registros de um JSONL, ignorando linhas corrompidas."""
    records = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []
    if limit:
        return records[-limit:]
    return records


def run_cmd(cmd, timeout=60, cwd=None):
    """Executa comando; devolve (rc, stdout, stderr). Nunca levanta exceção."""
    # Sem NOTIFY_SOCKET no filho: rodando sob systemd Type=notify, subprocessos
    # (ex.: systemctl is-active) mandariam sd_notify pro NOSSO socket e o
    # systemd logaria "Got notification message from PID..." a cada tick.
    env = dict(os.environ)
    env.pop("NOTIFY_SOCKET", None)
    try:
        proc = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout apos %ss" % timeout
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except OSError as exc:
        return 126, "", str(exc)


def which(binary):
    return shutil.which(binary)


def sha256_file(path, max_bytes=None):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            read = 0
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
                read += len(chunk)
                if max_bytes and read >= max_bytes:
                    break
        return h.hexdigest()
    except OSError:
        return None


def human_bytes(num):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024.0:
            return "%.1f %s" % (num, unit)
        num /= 1024.0
    return "%.1f PB" % num


def human_duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm%02ds" % (seconds // 60, seconds % 60)
    if seconds < 86400:
        return "%dh%02dm" % (seconds // 3600, (seconds % 3600) // 60)
    return "%dd%02dh" % (seconds // 86400, (seconds % 86400) // 3600)


def slugify(text):
    out = []
    for ch in text.strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_", ".", "/"):
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "sem-nome"


def tail_file(path, max_bytes=8192):
    """Últimos bytes de um arquivo como texto (para evidência de incidentes)."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, size - max_bytes))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def dir_size(path, max_entries=200000):
    """Tamanho total de um diretório (com limite de entradas por segurança)."""
    total = 0
    count = 0
    for root, dirs, files in os.walk(path, onerror=lambda e: None):
        for name in files:
            count += 1
            if count > max_entries:
                return total
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                continue
    return total
