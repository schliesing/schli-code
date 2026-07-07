"""Checagens de saúde — sistema e por projeto.

Cada checagem devolve CheckResult(project, check, ok, severity, detail).
O daemon aplica debounce (N falhas consecutivas) antes de abrir incidente,
para não reagir a soluços momentâneos.

Checagens de sistema: disco, memória, load, e previsão de disco cheio.
Checagens por projeto (conforme charter):
  - systemd_unit    : unit ativa?
  - docker_container: container rodando? reiniciando em loop? OOM?
  - pm2_process     : processo online?
  - port            : porta em escuta?
  - http            : endpoint responde (< 500)?
  - log_errors      : erros novos nos logs desde a última leitura
  - mem_trend       : crescimento sustentado de memória (vazamento)
  - cert            : certificado TLS perto de expirar
  - git_drift       : mudanças não commitadas / não enviadas em produção
  - heartbeat/backup: arquivos de pulso e backups frescos (se declarados)
"""

import json
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.request

from .util import (atomic_write_json, human_bytes, read_json, run_cmd,
                   tail_file, which)

SEV_INFO = "info"
SEV_WARN = "warning"
SEV_CRIT = "critical"

ERROR_PATTERNS = re.compile(
    r"(ERROR|CRITICAL|FATAL|Traceback \(most recent call last\)|"
    r"UnhandledPromiseRejection|ECONNREFUSED|EADDRINUSE|OutOfMemory|"
    r"Segmentation fault|panic:|core dumped)", re.IGNORECASE)


class CheckResult:
    def __init__(self, project, check, ok, detail="", severity=SEV_WARN,
                 evidence="", fixable=True):
        self.project = project
        self.check = check
        self.ok = ok
        self.detail = detail
        self.severity = severity
        self.evidence = evidence
        self.fixable = fixable   # False = só reportar, não há playbook

    def key(self):
        return "%s:%s" % (self.project, self.check)

    def __repr__(self):
        return "<%s %s ok=%s %s>" % (self.project, self.check, self.ok, self.detail)


# --- sistema ---------------------------------------------------------------------

def system_checks(cfg):
    results = []
    results.extend(_disk_checks(cfg))
    results.append(_memory_check(cfg))
    results.append(_load_check(cfg))
    results.extend(_security_checks(cfg))
    return [r for r in results if r]


def _security_checks(cfg):
    """Detecção comportamental de atividade agêntica hostil (JADEPUFFER-style).
    OBSERVE-ONLY: fixable=False — suspeita de intrusão quer humano, nunca
    auto-correção. Liga por padrão; desliga com security_scan_enabled=false."""
    if cfg is not None and not cfg.get("security_scan_enabled", default=True):
        return []
    from . import security
    out = []
    for d in security.scan(cfg):
        out.append(CheckResult(
            "_system", d["check"], d.get("ok", True), d.get("detail", ""),
            severity=SEV_CRIT, evidence=d.get("evidence", ""), fixable=False))
    return out


def _disk_checks(cfg):
    import shutil as _sh
    results = []
    seen = set()
    mounts = ["/"]
    try:
        with open("/proc/mounts") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) > 2 and parts[2] in ("ext4", "xfs", "btrfs", "zfs"):
                    mounts.append(parts[1])
    except OSError:
        pass
    for mount in mounts:
        if mount in seen:
            continue
        seen.add(mount)
        try:
            usage = _sh.disk_usage(mount)
        except OSError:
            continue
        pct = usage.used * 100.0 / usage.total if usage.total else 0
        crit = cfg.threshold("disk_critical_pct")
        warn = cfg.threshold("disk_pct")
        ok = pct < warn
        severity = SEV_CRIT if pct >= crit else SEV_WARN
        results.append(CheckResult(
            "_system", "disk:%s" % mount, ok,
            "disco %s em %.0f%% (livre: %s)" % (mount, pct, human_bytes(usage.free)),
            severity=severity))
    return results


def _memory_check(cfg):
    meminfo = {}
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                key, _, rest = line.partition(":")
                meminfo[key.strip()] = int(rest.strip().split()[0])  # kB
    except (OSError, ValueError, IndexError):
        return None
    total = meminfo.get("MemTotal", 0)
    available = meminfo.get("MemAvailable", 0)
    if not total:
        return None
    used_pct = (total - available) * 100.0 / total
    limit = cfg.threshold("mem_pct")
    return CheckResult(
        "_system", "memory", used_pct < limit,
        "memória em %.0f%% (disponível: %s)" % (used_pct,
                                                human_bytes(available * 1024)),
        severity=SEV_CRIT if used_pct >= 97 else SEV_WARN)


def _load_check(cfg):
    try:
        load1, load5, _ = os.getloadavg()
        cores = os.cpu_count() or 1
    except OSError:
        return None
    per_core = load5 / cores
    limit = cfg.threshold("load_per_core")
    return CheckResult(
        "_system", "load", per_core < limit,
        "load5 %.2f em %d cores (%.2f/core)" % (load5, cores, per_core),
        severity=SEV_WARN, fixable=False)


def disk_forecast(cfg):
    """Previsão de dias até o disco encher, pela taxa de crescimento observada."""
    import shutil as _sh
    path = cfg.state_file("disk-samples.json")
    samples = read_json(path, default=[])
    try:
        usage = _sh.disk_usage("/")
    except OSError:
        return None
    samples.append({"ts": time.time(), "used": usage.used})
    samples = samples[-168:]  # ~1 semana em amostras horárias
    atomic_write_json(path, samples)
    if len(samples) < 12:
        return None
    span = samples[-1]["ts"] - samples[0]["ts"]
    growth = samples[-1]["used"] - samples[0]["used"]
    if span < 3600 or growth <= 0:
        return None
    rate = growth / span  # bytes/s
    days_left = usage.free / rate / 86400
    if days_left < 14:
        return CheckResult(
            "_system", "disk_forecast", False,
            "no ritmo atual (%s/dia), o disco enche em ~%.1f dias"
            % (human_bytes(rate * 86400), days_left),
            severity=SEV_CRIT if days_left < 5 else SEV_WARN, fixable=False)
    return None


# --- por projeto --------------------------------------------------------------------

def project_checks(cfg, charter, state):
    """Roda todas as checagens aplicáveis a um projeto. `state` é um dict
    persistente (offsets de log, amostras de memória) do monitor."""
    results = []
    pid = charter["id"]
    rules = charter.get("rules") or {}
    # Heartbeats/backups declarados valem SEMPRE — é o mecanismo de vigilância de
    # pipeline NÃO-always-on (cron de esteira de vídeo, postagem de Instagram):
    # sem isso, um projeto com expected_always_on=false ficava sem NENHUMA checagem
    # e o Governante nunca perceberia que a esteira parou de rodar.
    results.extend(_check_declared_freshness(pid, charter))
    if not rules.get("expected_always_on", True):
        return [r for r in results if r]

    for unit in charter.get("services") or []:
        results.append(_check_systemd(cfg, pid, unit))
    for name in charter.get("containers") or []:
        results.append(_check_container(pid, name))
    for name in charter.get("pm2") or []:
        results.append(_check_pm2(pid, name))
    for port in charter.get("ports") or []:
        results.append(_check_port(pid, port))
    for endpoint in charter.get("endpoints") or []:
        results.append(_check_http(cfg, pid, endpoint))
    results.extend(_check_logs(cfg, pid, charter, state))
    trend = _check_mem_trend(cfg, pid, charter, state)
    if trend:
        results.append(trend)
    for domain in charter.get("domains") or []:
        result = _check_cert(cfg, pid, domain)
        if result:
            results.append(result)
    drift = _check_git(pid, charter)
    if drift:
        results.append(drift)
    return [r for r in results if r]


def _check_systemd(cfg, pid, unit):
    if not which("systemctl"):
        return None
    rc, out, _ = run_cmd(["systemctl", "show", unit, "--no-pager",
                          "-p", "ActiveState",
                          "-p", "SubState",
                          "-p", "StateChangeTimestampMonotonic"],
                         timeout=10)
    if rc != 0:
        rc, out, _ = run_cmd(["systemctl", "is-active", unit], timeout=10)
        state = out.strip() or "desconhecida"
        return CheckResult(pid, "systemd:%s" % unit, state == "active",
                           "unit %s está '%s'" % (unit, state),
                           severity=SEV_CRIT)
    props = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    state = props.get("ActiveState") or "desconhecida"
    sub = props.get("SubState") or ""
    ok = state == "active"
    if state == "activating":
        grace = cfg.get("systemd_activating_grace_s", default=900) \
            if cfg is not None else 900
        age = _systemd_state_age_s(props.get("StateChangeTimestampMonotonic"))
        if age is not None and age < grace:
            return CheckResult(
                pid, "systemd:%s" % unit, True,
                "unit %s ainda ativando há %s (janela %s)" %
                (unit, _fmt_age(age), _fmt_age(grace)), severity=SEV_INFO)
    detail = "unit %s está '%s%s'" % (unit, state, ("/" + sub) if sub else "")
    return CheckResult(pid, "systemd:%s" % unit, ok, detail, severity=SEV_CRIT)


def _systemd_state_age_s(monotonic_usec):
    try:
        changed = int(monotonic_usec or 0) / 1000000.0
        if changed <= 0:
            return None
        with open("/proc/uptime") as fh:
            uptime = float(fh.read().split()[0])
        return max(0, uptime - changed)
    except (OSError, ValueError, IndexError):
        return None


def _check_container(pid, name):
    if not which("docker"):
        return None
    rc, out, _ = run_cmd(["docker", "inspect", "--format", "{{json .State}}", name],
                         timeout=15)
    if rc != 0:
        return CheckResult(pid, "docker:%s" % name, False,
                           "container %s não existe mais" % name, severity=SEV_CRIT)
    try:
        state = json.loads(out)
    except json.JSONDecodeError:
        return None
    running = state.get("Running", False)
    restarting = state.get("Restarting", False)
    oom = state.get("OOMKilled", False)
    if running and not restarting:
        return CheckResult(pid, "docker:%s" % name, True,
                           "container %s rodando" % name)
    detail = "container %s: running=%s restarting=%s oom=%s exit=%s" % (
        name, running, restarting, oom, state.get("ExitCode"))
    return CheckResult(pid, "docker:%s" % name, False, detail, severity=SEV_CRIT)


# Cache do `pm2 jlist` por janela curta: este VPS tem dezenas de apps pm2 e a
# checagem roda por PROCESSO a cada tick de health — sem cache seriam dezenas
# de execuções do pm2 a cada 60s (CPU à toa numa máquina com histórico de
# afogamento). TTL de 30s mantém o dado fresco dentro do mesmo tick.
_PM2_CACHE = {"ts": 0.0, "apps": None}


def _pm2_apps(ttl=30):
    now = time.time()
    if _PM2_CACHE["apps"] is not None and now - _PM2_CACHE["ts"] < ttl:
        return _PM2_CACHE["apps"]
    rc, out, _ = run_cmd(["pm2", "jlist"], timeout=20)
    apps = None
    if rc == 0:
        try:
            apps = json.loads(out[out.index("["):])
        except (ValueError, json.JSONDecodeError):
            apps = None
    _PM2_CACHE["ts"] = now
    _PM2_CACHE["apps"] = apps
    return apps


def _check_pm2(pid, name):
    if not which("pm2"):
        return None
    apps = _pm2_apps()
    if apps is None:
        return None
    for app in apps:
        if app.get("name") == name:
            status = (app.get("pm2_env") or {}).get("status", "")
            ok = status == "online"
            return CheckResult(pid, "pm2:%s" % name, ok,
                               "pm2 %s está '%s'" % (name, status),
                               severity=SEV_CRIT)
    return CheckResult(pid, "pm2:%s" % name, False,
                       "pm2 %s desapareceu da lista" % name, severity=SEV_CRIT)


def _check_port(pid, port):
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=3):
            return CheckResult(pid, "port:%s" % port, True,
                               "porta %s em escuta" % port)
    except OSError:
        return CheckResult(pid, "port:%s" % port, False,
                           "porta %s não responde" % port, severity=SEV_CRIT)


def _check_http(cfg, pid, endpoint):
    timeout = cfg.get("http_timeout", default=6)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # interno; validade de cert tem checagem própria
    req = urllib.request.Request(endpoint, headers={"User-Agent": "governor-health"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            code = resp.status
    except urllib.error.HTTPError as exc:
        code = exc.code
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return CheckResult(pid, "http:%s" % endpoint, False,
                           "endpoint %s inacessível (%s)" % (endpoint, exc),
                           severity=SEV_CRIT)
    ok = code < 500
    return CheckResult(pid, "http:%s" % endpoint, ok,
                       "endpoint %s respondeu %d" % (endpoint, code),
                       severity=SEV_CRIT if not ok else SEV_INFO)


def _check_logs(cfg, pid, charter, state):
    """Procura erros NOVOS nos logs (lê só o delta desde a última passada)."""
    results = []
    offsets = state.setdefault("log_offsets", {})
    paths = []
    for entry in charter.get("log_paths") or []:
        if os.path.isdir(entry):
            try:
                for name in sorted(os.listdir(entry)):
                    if name.endswith(".log"):
                        paths.append(os.path.join(entry, name))
            except OSError:
                continue
        elif os.path.isfile(entry):
            paths.append(entry)
    for path in paths[:20]:
        try:
            stat = os.stat(path)
        except OSError:
            continue
        rec = offsets.get(path, {})
        offset = rec.get("offset", 0)
        if rec.get("inode") != stat.st_ino or offset > stat.st_size:
            offset = 0  # log rotacionou
        new_bytes = stat.st_size - offset
        if new_bytes <= 0:
            offsets[path] = {"offset": stat.st_size, "inode": stat.st_ino}
            continue
        try:
            with open(path, "rb") as fh:
                fh.seek(offset)
                chunk = fh.read(min(new_bytes, 512 * 1024)).decode(
                    "utf-8", errors="replace")
        except OSError:
            continue
        offsets[path] = {"offset": stat.st_size, "inode": stat.st_ino}
        errors = ERROR_PATTERNS.findall(chunk)
        if errors:
            sample_lines = [l for l in chunk.splitlines()
                            if ERROR_PATTERNS.search(l)][:5]
            results.append(CheckResult(
                pid, "log_errors:%s" % os.path.basename(path), False,
                "%d erro(s) novo(s) em %s" % (len(errors), path),
                severity=SEV_WARN, evidence="\n".join(sample_lines)[:1500],
                fixable=False))
    return results


def _project_rss_kb(charter):
    """Soma o RSS (kB) dos processos cujo cwd está dentro do projeto."""
    path = charter.get("path")
    if not path:
        return None
    total = 0
    found = False
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return None
    for spid in pids:
        try:
            cwd = os.path.realpath("/proc/%s/cwd" % spid)
            if cwd != path and not cwd.startswith(path + os.sep):
                continue
            with open("/proc/%s/status" % spid) as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        total += int(line.split()[1])
                        found = True
                        break
        except (OSError, ValueError, IndexError):
            continue
    return total if found else None


def _check_mem_trend(cfg, pid, charter, state):
    rss = _project_rss_kb(charter)
    if rss is None:
        return None
    samples = state.setdefault("mem_samples", {}).setdefault(pid, [])
    samples.append({"ts": time.time(), "rss_kb": rss})
    del samples[:-120]
    if len(samples) < 30:
        return None
    old = samples[0]
    span_h = (samples[-1]["ts"] - old["ts"]) / 3600.0
    if span_h < 1.0 or old["rss_kb"] <= 0:
        return None
    growth_pct_h = ((rss - old["rss_kb"]) / old["rss_kb"] * 100.0) / span_h
    limit = cfg.threshold("mem_growth_pct_per_hour")
    if growth_pct_h >= limit and rss > 200 * 1024:
        return CheckResult(
            pid, "mem_trend", False,
            "memória crescendo %.1f%%/h há %.1fh (agora %s) — possível vazamento"
            % (growth_pct_h, span_h, human_bytes(rss * 1024)),
            severity=SEV_WARN)
    return None


def _check_cert(cfg, pid, domain):
    warn_days = cfg.threshold("cert_warn_days")
    host = domain.replace("https://", "").replace("http://", "").split("/")[0]
    port = 443
    if ":" in host:
        host, sport = host.rsplit(":", 1)
        port = int(sport)
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
        expires = ssl.cert_time_to_seconds(cert["notAfter"])
        days = (expires - time.time()) / 86400
        if days < warn_days:
            return CheckResult(
                pid, "cert:%s" % host, False,
                "certificado de %s expira em %.0f dias" % (host, days),
                severity=SEV_CRIT if days < 3 else SEV_WARN)
        return CheckResult(pid, "cert:%s" % host, True,
                           "certificado de %s ok (%.0f dias)" % (host, days))
    except (OSError, ssl.SSLError, KeyError, ValueError) as exc:
        return CheckResult(pid, "cert:%s" % host, False,
                           "falha ao verificar certificado de %s: %s" % (host, exc),
                           severity=SEV_WARN, fixable=False)


def _check_git(pid, charter):
    path = charter.get("path")
    if not path or not os.path.isdir(os.path.join(path, ".git")):
        return None
    rc, out, _ = run_cmd(["git", "-C", path, "status", "--porcelain"], timeout=20)
    if rc != 0:
        return None
    dirty = len([l for l in out.splitlines() if l.strip()])
    rc2, ahead, _ = run_cmd(
        ["git", "-C", path, "rev-list", "--count", "@{u}..HEAD"], timeout=20)
    unpushed = int(ahead) if rc2 == 0 and ahead.isdigit() else 0
    if dirty or unpushed:
        return CheckResult(
            pid, "git_drift", False,
            "git: %d arquivo(s) sem commit, %d commit(s) sem push" % (dirty, unpushed),
            severity=SEV_INFO, fixable=False)
    return None


def _check_declared_freshness(pid, charter):
    """Heartbeats e backups declarados: arquivo precisa ser recente.

    heartbeats aceita string (frescor padrão 15min, p/ serviço always-on) OU
    dict {"path": ..., "max_age_h": N} — assim um cron DIÁRIO (esteira de vídeo,
    postagem de Instagram) declara a tolerância certa (ex.: 26h) e o Governante
    alerta se o pipeline parar de rodar, em vez de a falha passar silenciosa."""
    results = []
    declared = []
    for item in charter.get("backup_paths") or []:
        declared.append(("backup", item, 26 * 3600))
    for item in (charter.get("heartbeats") or []):
        if isinstance(item, dict):
            path = item.get("path")
            max_age = int(float(item.get("max_age_h", 0.25)) * 3600)
            if path:
                declared.append(("heartbeat", path, max_age))
        else:
            declared.append(("heartbeat", item, 15 * 60))
    for kind, path, max_age in declared:
        try:
            age = time.time() - os.stat(path).st_mtime
            ok = age <= max_age
            results.append(CheckResult(
                pid, "%s:%s" % (kind, os.path.basename(path)), ok,
                "%s %s tem %s de idade" % (kind, path,
                                           _fmt_age(age)),
                severity=SEV_WARN, fixable=False))
        except OSError:
            results.append(CheckResult(
                pid, "%s:%s" % (kind, os.path.basename(path)), False,
                "%s %s não existe" % (kind, path), severity=SEV_WARN,
                fixable=False))
    return results


def _fmt_age(seconds):
    from .util import human_duration
    return human_duration(seconds)


def load_monitor_state(cfg):
    return read_json(cfg.state_file("monitor.json"), default={})


def save_monitor_state(cfg, state):
    atomic_write_json(cfg.state_file("monitor.json"), state)
