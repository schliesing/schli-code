"""Idle guard para recursos pesados.

O objetivo e julgar recursos caros que podem dormir: browsers CDP do
browser-harness e o TTS local. Por padrao roda em observe-only; desligamento
real exige configuracao explicita.
"""

import json
import os
import time
import urllib.error
import urllib.request

from .util import atomic_write_json, human_bytes, read_json, run_cmd, which

BLANK_URLS = ("about:blank", "chrome://newtab/", "devtools://")


def run(cfg, journal):
    if not cfg.get("idle_guard", "enabled", default=True):
        return []
    state_path = cfg.state_file("idle-guard.json")
    state = read_json(state_path, default={})
    messages = []
    messages.extend(_browser_guard(cfg, state, journal))
    messages.extend(_tts_guard(cfg, state, journal))
    atomic_write_json(state_path, state)
    return messages


def _browser_guard(cfg, state, journal):
    bcfg = cfg.get("idle_guard", "browser", default={}) or {}
    if not bcfg.get("enabled", True):
        return []
    profiles_dir = bcfg.get("profiles_dir", "/root/browser-harness/profiles")
    if not os.path.isdir(profiles_dir):
        return []
    out = []
    for name, port in _browser_profiles(profiles_dir):
        key = "browser:%s" % name
        rec = state.setdefault(key, {})
        pages = _cdp_pages(port)
        now = time.time()
        if pages is None:
            rec["last_seen_down"] = now
            continue
        active = _active_pages(pages)
        connected = _port_has_active_client(
            port, bcfg.get("ignore_client_patterns") or [])
        if connected or _profile_locked(bcfg.get("lock_dir"), name):
            rec["last_active"] = now
            rec.pop("notified_idle", None)
            continue
        last_active = rec.setdefault("last_active", now)
        idle_s = int(bcfg.get("idle_s", 300))
        if now - last_active < idle_s:
            continue
        cooldown = int(bcfg.get("cooldown_s", 1800))
        if now - rec.get("last_action", 0) < cooldown:
            continue
        rec["last_action"] = now
        service = (bcfg.get("service_template") or
                   "browser-harness-chrome@%s.service") % name
        observe_only = _observe_only(cfg) or not bcfg.get("allow_stop", False)
        detail = "Chrome %s sem sessao CDP/lock ha %ds" % (
            name, now - last_active)
        if active:
            detail += " (%d pagina(s) aberta(s))" % len(active)
        if observe_only:
            journal.log("idle_guard", "[observe-only] desligaria %s" % service,
                        project="browser-harness-chrome",
                        data={"profile": name, "port": port})
            out.append("🛌 [observe-only] %s. Eu desligaria `%s`." %
                       (detail, service))
            continue
        ok, log = _stop_systemd(service)
        journal.log("idle_guard", "stop %s ok=%s" % (service, ok),
                    project="browser-harness-chrome",
                    data={"profile": name, "port": port, "log": log[-500:]})
        out.append(("✅" if ok else "⚠️") + " %s; stop %s" %
                   (detail, "OK" if ok else "falhou"))
    return out


def _browser_profiles(profiles_dir):
    profiles = []
    for filename in sorted(os.listdir(profiles_dir)):
        if not filename.endswith(".env"):
            continue
        path = os.path.join(profiles_dir, filename)
        name = filename[:-4]
        port = None
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.strip().startswith("PORT="):
                        port = line.split("=", 1)[1].strip().strip("\"'")
                        break
        except OSError:
            continue
        if port and port.isdigit():
            profiles.append((name, int(port)))
    return profiles


def _cdp_pages(port):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port,
                                    timeout=2) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return None


def _active_pages(pages):
    active = []
    for page in pages or []:
        if page.get("type") != "page":
            continue
        url = page.get("url") or ""
        if not url or any(url.startswith(prefix) for prefix in BLANK_URLS):
            continue
        active.append(url)
    return active


def _profile_locked(lock_dir, name):
    if not lock_dir:
        return False
    candidates = [
        os.path.join(lock_dir, "%s.busy" % name),
        os.path.join(lock_dir, "%s.lock" % name),
    ]
    return any(os.path.exists(path) for path in candidates)


def _tts_guard(cfg, state, journal):
    tcfg = cfg.get("idle_guard", "tts", default={}) or {}
    if not tcfg.get("enabled", True):
        return []
    name = tcfg.get("pm2_name", "tts-local")
    app = _pm2_app(name)
    if not app:
        return []
    env = app.get("pm2_env") or {}
    if env.get("status") != "online":
        return []
    port = int(tcfg.get("port", 8791))
    key = "tts:%s" % name
    rec = state.setdefault(key, {})
    now = time.time()
    if _port_has_established_connection(port):
        rec["last_active"] = now
        return []
    last_active = rec.setdefault("last_active", now)
    idle_s = int(tcfg.get("idle_s", 300))
    if now - last_active < idle_s:
        return []
    cooldown = int(tcfg.get("cooldown_s", 1800))
    if now - rec.get("last_action", 0) < cooldown:
        return []
    rec["last_action"] = now
    rss = ((app.get("monit") or {}).get("memory") or 0)
    detail = "TTS local sem conexao ativa ha %ds (RSS %s)" % (
        now - last_active, human_bytes(rss))
    observe_only = _observe_only(cfg) or not tcfg.get("allow_stop", False)
    if observe_only:
        journal.log("idle_guard", "[observe-only] desligaria pm2 %s" % name,
                    project="tts-local", data={"rss": rss})
        return ["🛌 [observe-only] %s. Eu desligaria `pm2 stop %s`." %
                (detail, name)]
    rc, out, err = run_cmd(["pm2", "stop", name], timeout=30)
    ok = rc == 0
    journal.log("idle_guard", "pm2 stop %s ok=%s" % (name, ok),
                project="tts-local", data={"rc": rc, "out": out[-500:],
                                           "err": err[-500:]})
    return [("✅" if ok else "⚠️") + " %s; stop %s" %
            (detail, "OK" if ok else "falhou")]


def _pm2_app(name):
    if not which("pm2"):
        return None
    rc, out, _ = run_cmd(["pm2", "jlist"], timeout=20)
    if rc != 0:
        return None
    try:
        apps = json.loads(out[out.index("["):])
    except (ValueError, json.JSONDecodeError):
        return None
    for app in apps:
        if app.get("name") == name:
            return app
    return None


def _port_has_established_connection(port):
    rc, out, _ = run_cmd(["ss", "-tn", "state", "established",
                          "sport", "=", ":%d" % port], timeout=10)
    if rc != 0:
        return False
    return any(":%d" % port in line for line in out.splitlines()[1:])


def _port_has_active_client(port, ignore_patterns):
    rc, out, _ = run_cmd(["ss", "-tnp", "state", "established"], timeout=10)
    if rc != 0:
        return False
    marker = ":%d" % port
    for line in out.splitlines()[1:]:
        if marker not in line:
            continue
        for pid in _pids_from_ss_line(line):
            cmd = _cmdline(pid)
            if not cmd:
                continue
            if any(pattern and pattern in cmd for pattern in ignore_patterns):
                continue
            return True
    return False


def _pids_from_ss_line(line):
    pids = []
    marker = "pid="
    idx = 0
    while True:
        idx = line.find(marker, idx)
        if idx < 0:
            break
        idx += len(marker)
        end = idx
        while end < len(line) and line[end].isdigit():
            end += 1
        if end > idx:
            try:
                pids.append(int(line[idx:end]))
            except ValueError:
                pass
        idx = end
    return pids


def _cmdline(pid):
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as fh:
            return fh.read().replace(b"\0", b" ").decode(
                "utf-8", errors="replace")
    except OSError:
        return ""


def _stop_systemd(service):
    if not which("systemctl"):
        return False, "systemctl indisponivel"
    rc, out, err = run_cmd(["systemctl", "stop", service], timeout=30)
    return rc == 0, err or out


def _observe_only(cfg):
    return bool(cfg.get("idle_guard", "observe_only", default=True))
