"""Auto-descoberta de projetos no VPS.

Fontes cruzadas (a chave unificadora é o caminho no disco):
  - filesystem: diretórios com marcadores de projeto (.git, package.json,
    docker-compose.yml, pyproject.toml, go.mod, Cargo.toml, .governor.json...)
  - docker: containers e projetos docker-compose (via labels)
  - systemd: units instaladas pelo usuário (WorkingDirectory/ExecStart)
  - pm2: processos gerenciados (pm_cwd)
  - portas: sockets em escuta mapeados ao processo dono (/proc/<pid>/cwd)

O resultado é um catálogo {project_id: info} salvo em state/catalog.json.
Projetos novos ou removidos são detectados por diff com o catálogo anterior.
"""

import json
import os

from .util import atomic_write_json, read_json, run_cmd, slugify, which

PROJECT_MARKERS = (
    ".governor.json",       # auto-declaração do projeto (prioridade máxima)
    "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
    "package.json", "pyproject.toml", "requirements.txt", "Pipfile",
    "go.mod", "Cargo.toml", "composer.json", "Gemfile",
    "ecosystem.config.js", "Procfile", "Makefile", ".git",
)

STACK_HINTS = {
    "package.json": "node", "ecosystem.config.js": "node",
    "pyproject.toml": "python", "requirements.txt": "python", "Pipfile": "python",
    "go.mod": "go", "Cargo.toml": "rust", "composer.json": "php",
    "Gemfile": "ruby",
    "docker-compose.yml": "docker-compose", "docker-compose.yaml": "docker-compose",
    "compose.yml": "docker-compose", "compose.yaml": "docker-compose",
}


def discover(cfg, journal):
    """Roda todas as fontes e devolve o catálogo consolidado."""
    projects = {}
    fs_projects = scan_filesystem(cfg)
    for info in fs_projects:
        projects[info["id"]] = info

    _merge_docker(projects, journal)
    _merge_systemd(projects, journal)
    _merge_pm2(projects, journal)
    _merge_ports(projects)

    return projects


# --- filesystem ---------------------------------------------------------------

def scan_filesystem(cfg):
    roots = cfg.get("scan_roots", default=[]) or []
    exclude = set(cfg.get("exclude_dirs", default=[]) or [])
    max_depth = cfg.get("max_scan_depth", default=3)
    home = os.path.realpath(cfg.home)
    found = []
    seen_paths = set()

    for root in roots:
        root = os.path.realpath(root)
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip("/").count("/")
        for dirpath, dirnames, filenames in os.walk(root, topdown=True,
                                                    onerror=lambda e: None):
            real = os.path.realpath(dirpath)
            # nunca considerar o próprio estado do Governor como projeto
            if real == home or real.startswith(home + os.sep):
                dirnames[:] = []
                continue
            depth = dirpath.rstrip("/").count("/") - base_depth
            names = set(filenames) | set(dirnames)
            dirnames[:] = [d for d in dirnames
                           if (d not in exclude and not d.startswith("."))
                           or d == ".git"]
            if depth >= max_depth:
                dirnames[:] = []
            markers = [m for m in PROJECT_MARKERS if m in names]
            if not markers:
                continue
            if any(real.startswith(p + os.sep) for p in seen_paths):
                # subdiretório de um projeto já catalogado (monorepo): ignora
                dirnames[:] = []
                continue
            seen_paths.add(real)
            dirnames[:] = []  # não desce dentro de projetos
            found.append(_fs_project_info(real, markers))
    return found


def _fs_project_info(path, markers):
    name = os.path.basename(path)
    info = {
        "id": slugify(name),
        "name": name,
        "path": path,
        "markers": markers,
        "stacks": sorted({STACK_HINTS[m] for m in markers if m in STACK_HINTS}),
        "sources": ["filesystem"],
        "services": [],     # units systemd
        "containers": [],   # containers docker
        "pm2": [],
        "ports": [],
        "declared": None,   # conteúdo de .governor.json, se existir
    }
    decl_path = os.path.join(path, ".governor.json")
    if os.path.exists(decl_path):
        info["declared"] = read_json(decl_path, default=None)
        if isinstance(info["declared"], dict) and info["declared"].get("name"):
            info["id"] = slugify(info["declared"]["name"])
            info["name"] = info["declared"]["name"]
    return info


# --- docker --------------------------------------------------------------------

def _merge_docker(projects, journal):
    if not which("docker"):
        return
    rc, out, _ = run_cmd(["docker", "ps", "-a", "--no-trunc",
                          "--format", "{{json .}}"], timeout=30)
    if rc != 0:
        return
    by_path = {p["path"]: p for p in projects.values() if p.get("path")}
    for line in out.splitlines():
        try:
            c = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = c.get("Names", "")
        entry = {"name": name, "image": c.get("Image", ""),
                 "state": c.get("State", ""), "status": c.get("Status", "")}
        workdir = _compose_workdir(name)
        target = None
        if workdir:
            for path, proj in by_path.items():
                if workdir == path or workdir.startswith(path + os.sep):
                    target = proj
                    break
        if target is None:
            # container sem projeto no filesystem: vira projeto próprio
            pid = slugify(name) or "container"
            target = projects.setdefault(pid, {
                "id": pid, "name": name, "path": workdir or "",
                "markers": [], "stacks": ["docker"], "sources": [],
                "services": [], "containers": [], "pm2": [], "ports": [],
                "declared": None,
            })
        if "docker" not in target["sources"]:
            target["sources"].append("docker")
        target["containers"].append(entry)


def _compose_workdir(container_name):
    rc, out, _ = run_cmd([
        "docker", "inspect", "--format",
        '{{index .Config.Labels "com.docker.compose.project.working_dir"}}',
        container_name,
    ], timeout=15)
    if rc == 0 and out and out != "<no value>":
        return os.path.realpath(out)
    return None


# --- systemd --------------------------------------------------------------------

USER_UNIT_DIRS = ("/etc/systemd/system", "/usr/local/lib/systemd")

def _merge_systemd(projects, journal):
    if not which("systemctl"):
        return
    rc, out, _ = run_cmd(["systemctl", "list-unit-files", "--type=service",
                          "--no-legend", "--plain", "--no-pager"], timeout=30)
    if rc != 0:
        return
    by_path = {p["path"]: p for p in projects.values() if p.get("path")}
    for line in out.splitlines():
        parts = line.split()
        if not parts:
            continue
        unit = parts[0]
        state = parts[1] if len(parts) > 1 else ""
        if state not in ("enabled", "enabled-runtime", "linked", "static"):
            if state != "disabled":
                continue
        rc2, out2, _ = run_cmd(
            ["systemctl", "show", unit, "-p",
             "FragmentPath,WorkingDirectory,ExecStart", "--no-pager"],
            timeout=15)
        if rc2 != 0:
            continue
        props = dict(kv.split("=", 1) for kv in out2.splitlines() if "=" in kv)
        fragment = props.get("FragmentPath", "")
        if not any(fragment.startswith(d) for d in USER_UNIT_DIRS):
            continue  # unit do sistema operacional, não é projeto do usuário
        if unit.startswith("governor"):
            continue  # o próprio Governor
        workdir = props.get("WorkingDirectory", "").strip("\"'")
        execstart = props.get("ExecStart", "")
        target = _match_by_path(by_path, workdir) or \
            _match_by_path(by_path, _path_from_exec(execstart)) or \
            _match_by_name(projects, unit)
        if target is None:
            pid = slugify(unit.replace(".service", ""))
            target = projects.setdefault(pid, {
                "id": pid, "name": unit, "path": workdir or "",
                "markers": [], "stacks": ["systemd"], "sources": [],
                "services": [], "containers": [], "pm2": [], "ports": [],
                "declared": None,
            })
        if "systemd" not in target["sources"]:
            target["sources"].append("systemd")
        if unit not in target["services"]:
            target["services"].append(unit)


def _path_from_exec(execstart):
    # ExecStart={ path=/usr/bin/python3 ; argv[]=... } — pega caminhos de argv
    for token in execstart.replace(";", " ").split():
        if token.startswith("/") and "/bin/" not in token and os.path.exists(token):
            return os.path.dirname(os.path.realpath(token))
    return ""


def _match_by_path(by_path, candidate):
    if not candidate:
        return None
    candidate = os.path.realpath(candidate)
    for path, proj in by_path.items():
        if candidate == path or candidate.startswith(path + os.sep):
            return proj
    return None


def _match_by_name(projects, unit):
    stem = slugify(unit.replace(".service", ""))
    for pid, proj in projects.items():
        if pid and (pid in stem or stem in pid):
            return proj
    return None


# --- pm2 -------------------------------------------------------------------------

def _merge_pm2(projects, journal):
    if not which("pm2"):
        return
    rc, out, _ = run_cmd(["pm2", "jlist"], timeout=30)
    if rc != 0 or not out:
        return
    try:
        # pm2 às vezes imprime logs antes do JSON; pega do primeiro '[' em diante
        payload = out[out.index("["):]
        apps = json.loads(payload)
    except (ValueError, json.JSONDecodeError):
        return
    by_path = {p["path"]: p for p in projects.values() if p.get("path")}
    for app in apps:
        name = app.get("name", "")
        env = app.get("pm2_env", {}) or {}
        cwd = os.path.realpath(env.get("pm_cwd", "") or "")
        entry = {"name": name, "status": env.get("status", ""),
                 "restarts": env.get("restart_time", 0)}
        target = _match_by_path(by_path, cwd) or _match_by_name(projects, name)
        if target is None:
            pid = slugify(name) or "pm2-app"
            target = projects.setdefault(pid, {
                "id": pid, "name": name, "path": cwd,
                "markers": [], "stacks": ["node"], "sources": [],
                "services": [], "containers": [], "pm2": [], "ports": [],
                "declared": None,
            })
        if "pm2" not in target["sources"]:
            target["sources"].append("pm2")
        target["pm2"].append(entry)


# --- portas ------------------------------------------------------------------------

def _merge_ports(projects):
    rc, out, _ = run_cmd(["ss", "-tlnp"], timeout=15)
    if rc != 0:
        return
    by_path = {p["path"]: p for p in projects.values() if p.get("path")}
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        local = parts[3]
        port = local.rsplit(":", 1)[-1]
        if not port.isdigit():
            continue
        pids = _pids_from_ss(line)
        for pid in pids:
            cwd = _proc_cwd(pid)
            proj = _match_by_path(by_path, cwd)
            if proj is not None:
                entry = int(port)
                if entry not in proj["ports"]:
                    proj["ports"].append(entry)


def _pids_from_ss(line):
    pids = []
    marker = "pid="
    idx = 0
    while True:
        idx = line.find(marker, idx)
        if idx < 0:
            break
        end = idx + len(marker)
        num = ""
        while end < len(line) and line[end].isdigit():
            num += line[end]
            end += 1
        if num:
            pids.append(int(num))
        idx = end
    return pids


def _proc_cwd(pid):
    try:
        return os.path.realpath("/proc/%d/cwd" % pid)
    except OSError:
        return ""


# --- catálogo e diff ----------------------------------------------------------------

def load_catalog(cfg):
    return read_json(cfg.state_file("catalog.json"), default={})


def save_catalog(cfg, catalog):
    atomic_write_json(cfg.state_file("catalog.json"), catalog)


def diff_catalog(old, new):
    """Devolve (novos, removidos, alterados) entre dois catálogos."""
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = []
    for pid in set(new) & set(old):
        o, n = old[pid], new[pid]
        delta = {}
        for field in ("services", "containers", "ports", "stacks"):
            before = _fingerprint(o.get(field))
            after = _fingerprint(n.get(field))
            if before != after:
                delta[field] = {"antes": before, "depois": after}
        if delta:
            changed.append({"id": pid, "delta": delta})
    return added, removed, changed


def _fingerprint(value):
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict):
                out.append(item.get("name", str(item)))
            else:
                out.append(item)
        return sorted(str(x) for x in out)
    return value
