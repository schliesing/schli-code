"""Autocuidado — o Governor cuida de si mesmo (self-healing/self-improve).

Camadas:
  1. Bulkhead: cada subsistema roda dentro de um circuit breaker. Exceção
     não derruba o daemon; o subsistema é suspenso com backoff exponencial
     e o erro vai para o self-journal (que alimenta o aprendizado).
  2. Watchdog systemd: sd_notify(WATCHDOG=1) a cada tick; se o loop travar,
     o systemd reinicia o processo (Restart=always).
  3. Memória própria: se o RSS do Governor passar do limite, ele reinicia
     a si mesmo de forma limpa (exit; systemd o traz de volta).
  4. Integridade de estado: JSONs corrompidos são restaurados do .bak
     automaticamente pelo read_json; aqui validamos e reportamos.
  5. Auto-update com rollback: `governorctl self-update` puxa o git do
     próprio Governor, roda o selftest e SÓ aplica se passar; senão volta
     para a revisão anterior e reporta.
"""

import os
import socket
import sys
import time

from .util import read_json, run_cmd

MAX_BACKOFF = 3600


class Bulkhead:
    """Circuit breaker por subsistema: suspende após erros repetidos."""

    def __init__(self, journal, orion=None):
        self.journal = journal
        self.orion = orion
        self.failures = {}   # name -> {count, until}

    def run(self, name, fn, *args, **kwargs):
        node = self.failures.get(name)
        if node and time.time() < node["until"]:
            return None  # suspenso, aguardando backoff
        try:
            result = fn(*args, **kwargs)
            if node:
                self.journal.log("selfcare", "subsistema %s se recuperou" % name)
                self.failures.pop(name, None)
            return result
        except Exception as exc:
            record = self.journal.self_error(name, exc)
            count = (node["count"] + 1) if node else 1
            backoff = min(MAX_BACKOFF, 60 * (2 ** (count - 1)))
            self.failures[name] = {"count": count,
                                   "until": time.time() + backoff}
            self.journal.log(
                "selfcare", "subsistema %s falhou (%dx); suspenso por %ds"
                % (name, count, backoff), data={"error": record["error"]})
            if self.orion and count == 3:
                self.orion.send(
                    "🩺 Governor: meu subsistema '%s' falhou %d vezes seguidas "
                    "e está suspenso (backoff %ds). Erro: %s\n"
                    "Estou me mantendo de pé; detalhes no self-journal."
                    % (name, count, backoff, record["error"][:200]))
            return None


# --- watchdog systemd ------------------------------------------------------------

def sd_notify(payload):
    """Envia notificação ao systemd (READY=1, WATCHDOG=1...). Silencioso se
    não estivermos rodando sob systemd."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return False
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(addr)
            sock.send(payload.encode())
        return True
    except OSError:
        return False


def notify_ready():
    return sd_notify("READY=1")


def notify_watchdog():
    return sd_notify("WATCHDOG=1")


# --- memória do próprio processo ----------------------------------------------------

def self_rss_mb():
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def check_self_memory(cfg, journal, orion):
    """Se o próprio Governor vazar memória, reinicia de forma limpa."""
    limit = cfg.threshold("self_mem_limit_mb")
    rss = self_rss_mb()
    if rss > limit:
        journal.log("selfcare", "meu RSS chegou a %.0f MB (limite %d); "
                    "reiniciando a mim mesmo" % (rss, limit))
        if orion:
            orion.send("🩺 Governor: minha memória chegou a %.0f MB; vou "
                       "reiniciar a mim mesmo por precaução. Volto em segundos."
                       % rss)
        sys.exit(0)  # systemd Restart=always nos traz de volta
    return rss


# --- integridade de estado -----------------------------------------------------------

CRITICAL_STATE = ("catalog.json", "incidents.json", "proposals.json",
                  "learning.json", "monitor.json")


def verify_state(cfg, journal):
    """Confere se os JSONs de estado carregam; read_json já cai no .bak."""
    issues = []
    for name in CRITICAL_STATE:
        path = cfg.state_file(name)
        if not os.path.exists(path):
            continue
        data = read_json(path, default="__corrupt__")
        if data == "__corrupt__":
            issues.append(name)
            journal.log("selfcare", "estado %s corrompido e sem .bak legível; "
                        "será reconstruído do zero" % name)
            try:
                os.rename(path, path + ".corrupt")
            except OSError:
                pass
    return issues


# --- auto-update com rollback -----------------------------------------------------------

def self_update(cfg, journal, orion=None, repo_dir=None):
    """git pull no próprio código; roda selftest; reverte se falhar."""
    repo = repo_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isdir(os.path.join(repo, ".git")):
        return False, "instalação não é um clone git; auto-update indisponível"
    rc, before, _ = run_cmd(["git", "-C", repo, "rev-parse", "HEAD"], timeout=20)
    if rc != 0:
        return False, "não consegui ler a revisão atual"
    rc, out, err = run_cmd(["git", "-C", repo, "pull", "--ff-only"], timeout=120)
    if rc != 0:
        return False, "git pull falhou: %s" % (err or out)[:200]
    rc, after, _ = run_cmd(["git", "-C", repo, "rev-parse", "HEAD"], timeout=20)
    if before == after:
        return True, "já estou na versão mais recente (%s)" % before[:8]

    # valida a versão nova ANTES de adotá-la
    rc, out, err = run_cmd([sys.executable, "-m", "governor", "selftest"],
                           timeout=300, cwd=repo)
    if rc != 0:
        run_cmd(["git", "-C", repo, "reset", "--hard", before], timeout=60)
        journal.log("selfcare", "auto-update revertido: selftest da versão "
                    "nova falhou", data={"err": (err or out)[:500]})
        if orion:
            orion.send("🩺 Governor: tentei me atualizar (%s -> %s) mas o "
                       "selftest da versão nova FALHOU. Reverti para a versão "
                       "anterior e sigo operando." % (before[:8], after[:8]))
        return False, "selftest falhou; rollback executado"

    journal.log("selfcare", "auto-update aplicado: %s -> %s"
                % (before[:8], after[:8]))
    if orion:
        orion.send("🩺 Governor: me atualizei de %s para %s (selftest OK). "
                   "Reiniciando para adotar a versão nova."
                   % (before[:8], after[:8]))
    return True, "atualizado %s -> %s; reinicie o serviço (ou aguarde o "\
        "watchdog)" % (before[:8], after[:8])
