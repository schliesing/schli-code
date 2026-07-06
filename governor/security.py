"""Detecção comportamental de atividade agêntica HOSTIL (observe-only).

Inspirado no JADEPUFFER (Sysdig, jul/2026 — primeiro ransomware 100% agêntico):
um agente LLM invadiu um host, varreu segredos, pivotou lateralmente e
criptografou um banco, tudo sozinho. O Governante já observa processos, cron,
portas e logs — então vira, de graça, um DETECTOR comportamental desse tipo de
ataque. Foco em COMPORTAMENTO (que um agente hostil não troca em segundos), não
em IOC (IP/hash/wallet, que envelhecem na hora).

Regras de ouro:
  - OBSERVE-ONLY: todo achado é `fixable=False` (o monitor marca assim). Suspeita
    de intrusão quer HUMANO na hora, nunca auto-correção destrutiva.
  - BAIXO FALSO-POSITIVO: cada detector é escopado pro padrão MALICIOSO real, não
    pro genérico (ex.: cron que faz `curl|sh`, não qualquer curl; banco que gera
    shell, não qualquer processo). Melhor calar do que gritar à toa.
  - STDLIB puro: nada de auditd/SIEM/dependência nova (filosofia do projeto).

Devolve lista de dicts {check, ok, detail, evidence}; o monitor os embrulha em
CheckResult(project="_system", severity=critical, fixable=False).
"""

import os
import re

# Processos que NUNCA deveriam gerar shell/downloader como filho — assinatura nº1
# do JADEPUFFER (banco executando python/sh pra varrer segredos e pivotar).
_DB_PARENTS = {"mysqld", "mariadbd", "postgres", "postmaster", "mongod",
               "redis-server", "memcached"}
# Filhos suspeitos p/ um pai que é banco/app: shell e ferramentas de download/rede.
_SUSPECT_CHILDREN = {"sh", "bash", "dash", "zsh", "curl", "wget", "nc", "ncat",
                     "netcat", "socat", "python", "python3", "perl", "ruby"}
# Portas clássicas de reverse-shell / C2 (falso-positivo baixíssimo).
_C2_PORTS = {4444, 5555, 6666, 1337, 31337, 12345, 9001, 8888}
# Padrões de nota de resgate (ransom note) — nomes inequívocos.
_RANSOM_RE = re.compile(
    r"(ransom|how[_\-\s]?to[_\-\s]?decrypt|recover[_\-\s]?files|read[_\-\s]?me"
    r"[_\-\s]?to[_\-\s]?decrypt|your[_\-\s]?files[_\-\s]?are|decrypt[_\-\s]?instruction)",
    re.I)
# Cron/entrada que baixa e joga direto no shell (curl|sh, wget|bash, base64 -d|sh).
_CRON_BEACON_RE = re.compile(
    r"(curl|wget)\b[^|]*\|\s*(sh|bash|zsh)\b"
    r"|base64\s+-d[^|]*\|\s*(sh|bash)\b"
    r"|python[0-9]?\s+-c\s+.{0,80}(urlopen|urlretrieve|socket).{0,80}(exec|system|popen)",
    re.I)


def _proc_table():
    """{pid: {comm, ppid, cmdline}} lido de /proc (stdlib, best-effort)."""
    table = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/comm") as fh:
                comm = fh.read().strip()
            with open(f"/proc/{pid}/stat") as fh:
                stat = fh.read()
            # ppid é o 4º campo, mas comm (2º) pode ter espaços/parênteses: corta após ')'
            after = stat[stat.rfind(")") + 2:].split()
            ppid = int(after[1]) if len(after) > 1 else 0
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as fh:
                    cmdline = fh.read().replace(b"\x00", b" ").decode("utf-8", "replace").strip()
            except OSError:
                cmdline = comm
            table[int(pid)] = {"comm": comm, "ppid": ppid, "cmdline": cmdline}
        except (OSError, ValueError):
            continue
    return table


def _detect_db_spawns_shell(table):
    """Banco (mysqld/postgres/...) com filho shell/downloader = pivô agêntico."""
    achados = []
    for pid, info in table.items():
        parent = table.get(info["ppid"])
        if not parent:
            continue
        pcomm = parent["comm"].lower()
        if pcomm not in _DB_PARENTS:
            continue
        child = info["comm"].lower()
        if child in _SUSPECT_CHILDREN:
            achados.append(
                "PID %d (%s) — filho de %s (PID %d): %s"
                % (pid, child, pcomm, info["ppid"], info["cmdline"][:160]))
    if not achados:
        return {"check": "security:db-spawn-shell", "ok": True,
                "detail": "nenhum banco gerando shell/downloader"}
    return {
        "check": "security:db-spawn-shell", "ok": False,
        "detail": "processo de BANCO gerou shell/ferramenta de rede — assinatura de "
                  "pivô agêntico (estilo JADEPUFFER). Investigar AGORA.",
        "evidence": "\n".join(achados[:6]),
    }


def _detect_c2_ports():
    """Alguém escutando numa porta clássica de reverse-shell/C2."""
    hits = []
    for proto in ("tcp", "tcp6"):
        try:
            with open(f"/proc/net/{proto}") as fh:
                next(fh, None)
                for line in fh:
                    parts = line.split()
                    if len(parts) < 4:
                        continue
                    # 0x0A = LISTEN
                    if parts[3] != "0A":
                        continue
                    local = parts[1]
                    try:
                        port = int(local.rsplit(":", 1)[1], 16)
                    except (ValueError, IndexError):
                        continue
                    if port in _C2_PORTS:
                        hits.append("porta %d em LISTEN (%s)" % (port, proto))
        except OSError:
            continue
    if not hits:
        return {"check": "security:c2-port", "ok": True,
                "detail": "nenhuma porta de C2/reverse-shell conhecida escutando"}
    return {
        "check": "security:c2-port", "ok": False,
        "detail": "porta clássica de reverse-shell/C2 em escuta — possível backdoor.",
        "evidence": "\n".join(sorted(set(hits))),
    }


def _detect_ransom_artifacts():
    """Notas de resgate (nomes inequívocos) nos diretórios quentes."""
    hot = ["/root", "/home", "/tmp", "/var/www", "/srv", "/opt"]
    found = []
    for base in hot:
        if not os.path.isdir(base):
            continue
        try:
            for name in os.listdir(base):
                if _RANSOM_RE.search(name):
                    found.append(os.path.join(base, name))
            # 1 nível abaixo em /home e /var/www (contas/sites)
            if base in ("/home", "/var/www", "/srv", "/opt"):
                for sub in os.listdir(base):
                    d = os.path.join(base, sub)
                    if not os.path.isdir(d):
                        continue
                    try:
                        for name in os.listdir(d):
                            if _RANSOM_RE.search(name):
                                found.append(os.path.join(d, name))
                    except OSError:
                        continue
        except OSError:
            continue
        if len(found) >= 12:
            break
    if not found:
        return {"check": "security:ransom-note", "ok": True,
                "detail": "nenhuma nota de resgate encontrada"}
    return {
        "check": "security:ransom-note", "ok": False,
        "detail": "arquivo com nome de NOTA DE RESGATE encontrado — possível ransomware.",
        "evidence": "\n".join(found[:12]),
    }


def _detect_cron_beacon():
    """Cron/entrada que baixa e executa direto no shell (persistência agêntica)."""
    files = ["/etc/crontab"]
    for base in ("/etc/cron.d", "/var/spool/cron/crontabs", "/var/spool/cron"):
        if os.path.isdir(base):
            for fn in os.listdir(base):
                if fn.startswith(".") or fn.endswith((".bak", ".disabled")):
                    continue
                files.append(os.path.join(base, fn))
    hits = []
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    if _CRON_BEACON_RE.search(s):
                        hits.append("%s:%d  %s" % (os.path.basename(path), i, s[:140]))
        except OSError:
            continue
    if not hits:
        return {"check": "security:cron-beacon", "ok": True,
                "detail": "nenhum cron baixando-e-executando (curl|sh) detectado"}
    return {
        "check": "security:cron-beacon", "ok": False,
        "detail": "cron baixa e executa direto no shell (curl|sh / base64|sh) — "
                  "persistência típica de malware/agente hostil.",
        "evidence": "\n".join(hits[:8]),
    }


def scan(cfg=None):
    """Roda todos os detectores comportamentais. Cada um isolado (um erro não
    derruba os outros). Devolve lista de dicts p/ o monitor embrulhar."""
    out = []
    try:
        table = _proc_table()
    except Exception:  # noqa: BLE001
        table = {}
    for detector in (
        lambda: _detect_db_spawns_shell(table),
        _detect_c2_ports,
        _detect_ransom_artifacts,
        _detect_cron_beacon,
    ):
        try:
            out.append(detector())
        except Exception as exc:  # noqa: BLE001 — detector nunca derruba o scan
            out.append({"check": "security:scan-error", "ok": True,
                        "detail": "detector falhou: %s" % str(exc)[:120]})
    return out
