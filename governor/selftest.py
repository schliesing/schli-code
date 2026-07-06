"""Autoteste do Governor.

Roda num GOVERNOR_HOME temporário com um projeto falso e exercita o ciclo
inteiro sem tocar no sistema real (dry_run). É o gate do auto-update:
se qualquer etapa falhar, a versão nova é rejeitada e revertida.
"""

import json
import os
import shutil
import tempfile


def run():
    failures = []
    tmp = tempfile.mkdtemp(prefix="governor-selftest-")
    old_home = os.environ.get("GOVERNOR_HOME")
    old_cfg = os.environ.get("GOVERNOR_CONFIG")
    os.environ["GOVERNOR_HOME"] = os.path.join(tmp, "home")
    os.environ["GOVERNOR_CONFIG"] = os.path.join(tmp, "config.json")
    try:
        _run_all(tmp, failures)
    finally:
        if old_home is None:
            os.environ.pop("GOVERNOR_HOME", None)
        else:
            os.environ["GOVERNOR_HOME"] = old_home
        if old_cfg is None:
            os.environ.pop("GOVERNOR_CONFIG", None)
        else:
            os.environ["GOVERNOR_CONFIG"] = old_cfg
        shutil.rmtree(tmp, ignore_errors=True)
    if failures:
        for f in failures:
            print("FALHOU: %s" % f)
        return 1
    print("selftest OK — todos os subsistemas responderam.")
    return 0


def _check(failures, condition, name):
    status = "ok" if condition else "FALHOU"
    print("  [%s] %s" % (status, name))
    if not condition:
        failures.append(name)


def _run_all(tmp, failures):
    from .config import Config
    from .journal import Journal
    from .learning import Learning
    from .healing import Healer
    from .telegram import Orion
    from . import charter as charter_mod
    from . import discovery, hygiene, monitor
    from .util import atomic_write_json, read_json

    # --- config e projeto falso ------------------------------------------------
    project_dir = os.path.join(tmp, "apps", "projeto-teste")
    os.makedirs(project_dir)
    with open(os.path.join(project_dir, "package.json"), "w") as fh:
        json.dump({"name": "projeto-teste",
                   "description": "API de teste do selftest"}, fh)
    with open(os.path.join(project_dir, "README.md"), "w") as fh:
        fh.write("# Projeto Teste\n\nServe pedidos de exemplo em produção.\n")
    with open(os.path.join(project_dir, "app.js"), "w") as fh:
        fh.write("require('./lib')\n")
    with open(os.path.join(project_dir, "lib.js"), "w") as fh:
        fh.write("module.exports = 1\n")
    with open(os.path.join(project_dir, "orfao.js"), "w") as fh:
        fh.write("// nunca referenciado\n")
    with open(os.path.join(project_dir, "app.js.bak"), "w") as fh:
        fh.write("x" * 2048)
    with open(os.path.join(project_dir, "dados final_v2.csv"), "w") as fh:
        fh.write("a,b\n")
    with open(os.path.join(project_dir, "dados.csv"), "w") as fh:
        fh.write("a,b\n")
    big = "y" * (1024 * 1024 + 10)
    with open(os.path.join(project_dir, "video1.dat"), "w") as fh:
        fh.write(big)
    with open(os.path.join(project_dir, "video2.dat"), "w") as fh:
        fh.write(big)

    cfg = Config(data={
        "scan_roots": [os.path.join(tmp, "apps")],
        "dry_run": False,
        "telegram": {"token": "", "chat_id": ""},
        "thresholds": {"dup_min_mb": 1},
    })
    journal = Journal(cfg)
    _check(failures, cfg.home.startswith(tmp), "config usa GOVERNOR_HOME")

    # --- util: escrita atômica + recuperação de corrupção -------------------------
    state_path = cfg.state_file("teste.json")
    atomic_write_json(state_path, {"v": 1})
    atomic_write_json(state_path, {"v": 2})
    with open(state_path, "w") as fh:
        fh.write("{corrompido")
    _check(failures, read_json(state_path, default={}).get("v") == 1,
           "read_json recupera do .bak após corrupção")

    # --- journal e incidentes ------------------------------------------------------
    journal.log("selfcare", "selftest iniciando")
    inc = journal.open_incident("projeto-teste", "port:9999", "porta caída")
    _check(failures, inc["count"] == 1, "incidente abre")
    closed = journal.close_incident("projeto-teste", "port:9999", "teste")
    _check(failures, closed is not None, "incidente fecha")
    _check(failures, len(journal.recent(limit=10)) >= 2, "journal grava e lê")

    # --- discovery -------------------------------------------------------------------
    catalog = discovery.discover(cfg, journal)
    _check(failures, "projeto-teste" in catalog, "discovery encontra projeto")
    info = catalog.get("projeto-teste", {})
    _check(failures, "node" in (info.get("stacks") or []),
           "discovery identifica stack")
    discovery.save_catalog(cfg, catalog)
    added, removed, _ = discovery.diff_catalog({}, catalog)
    _check(failures, "projeto-teste" in added, "diff detecta projeto novo")

    # --- charter ---------------------------------------------------------------------
    drafts = charter_mod.sync_with_catalog(cfg, journal, catalog)
    _check(failures, any(d["id"] == "projeto-teste" for d in drafts),
           "charter rascunho criado")
    draft = charter_mod.load_charter(cfg, "projeto-teste")
    _check(failures, "teste" in (draft.get("mission") or "").lower()
           or "exemplo" in (draft.get("mission") or "").lower(),
           "missão inferida do package.json/README")
    _check(failures, draft["status"] == "draft", "novo projeto começa draft")
    charter_mod.confirm(cfg, journal, "projeto-teste")
    confirmed = charter_mod.load_charter(cfg, "projeto-teste")
    _check(failures, confirmed["status"] == "confirmed", "confirmação funciona")

    # --- monitor ----------------------------------------------------------------------
    sys_results = monitor.system_checks(cfg)
    _check(failures, any(r.check.startswith("disk:") for r in sys_results),
           "checagem de disco roda")
    state = {}
    confirmed["ports"] = [1]  # porta certamente fechada
    results = monitor.project_checks(cfg, confirmed, state)
    port_fail = [r for r in results if r.check == "port:1" and not r.ok]
    _check(failures, bool(port_fail), "checagem de porta detecta queda")

    # --- healing (decisões de segurança) --------------------------------------------------
    learning = Learning(cfg, journal)
    healer = Healer(cfg, journal, learning)
    draft_charter = dict(confirmed, status="draft")
    can, reason = healer.can_heal(draft_charter, port_fail[0])
    _check(failures, not can and "observa" in reason,
           "healing bloqueado sem confirmação (observe-only)")
    can, _ = healer.can_heal(confirmed, port_fail[0])
    _check(failures, can, "healing liberado com charter confirmado")
    healer_dry = Healer(Config(data={"dry_run": True,
                                     "scan_roots": []}), journal, learning)
    outcome = healer_dry.heal(confirmed, port_fail[0], lambda: None)
    _check(failures, outcome["attempts"] >= 0 and isinstance(outcome["log"], list),
           "playbook executa em dry-run sem explodir")

    # --- learning ---------------------------------------------------------------------------
    learning.record_action("port:1", "restart-project", False)
    learning.record_action("port:1", "restart-project", False)
    learning.record_action("port:1", "restart-project", False)
    _check(failures, learning.is_quarantined("port:1", "restart-project"),
           "ação ruim entra em quarentena após 3 falhas")
    for _ in range(3):
        learning.record_incident("projeto-teste:port:1")
    _check(failures, learning.is_chronic("projeto-teste:port:1"),
           "incidente crônico detectado")

    # --- hygiene ----------------------------------------------------------------------------
    findings, notes = hygiene.scan_project(cfg, confirmed)
    cats = {f["category"] for f in findings}
    _check(failures, "junk" in cats, "hygiene acha arquivo-lixo (.bak)")
    _check(failures, "dead-version" in cats,
           "hygiene acha versão morta (final_v2)")
    _check(failures, "duplicate" in cats, "hygiene acha duplicados")
    _check(failures, any("orfao" in n for n in notes),
           "hygiene sugere revisão de código órfão")
    props = hygiene.register_findings(cfg, journal, "projeto-teste", findings)
    _check(failures, len(props) == len(findings), "achados viram propostas")
    junk = next(p for p in props if p["category"] == "junk")
    prop, msg = hygiene.approve(cfg, journal, junk["id"])
    _check(failures, prop["status"] == "quarantined"
           and not os.path.exists(junk["path"]),
           "aprovação move para quarentena (não deleta)")
    restored = hygiene.restore(cfg, journal, junk["id"])
    _check(failures, restored[0] is not None and os.path.exists(junk["path"]),
           "restauração da quarentena funciona")

    # --- telegram (sem rede: enfileira) ----------------------------------------------------
    orion = Orion(cfg, journal)
    orion.send("mensagem de teste")
    _check(failures, not orion.configured, "sem token: não configurado")
    orion2 = Orion(Config(data={"telegram": {"token": "x", "chat_id": "1"},
                                "scan_roots": []}), journal)
    orion2._send_once = lambda *a, **k: False  # simula rede fora
    orion2.send("offline")
    from .util import read_jsonl
    _check(failures, len(read_jsonl(orion2.queue_path)) == 1,
           "mensagem enfileirada quando Telegram cai")

    # --- daemon monta e comandos respondem -------------------------------------------------
    from .daemon import Daemon
    daemon = Daemon(cfg)
    _check(failures, "🏛" in daemon.cmd_status([], "1"), "comando /status responde")
    _check(failures, "projeto-teste" in daemon.cmd_projects([], "1"),
           "comando /projetos responde")
    _check(failures, daemon.cmd_help([], "1").startswith("🏛"),
           "comando /ajuda responde")
    daemon.cmd_pause([], "1")
    _check(failures, daemon.paused, "pausa funciona")
    daemon.cmd_resume([], "1")
    _check(failures, not daemon.paused, "retomada funciona")
    daemon.task_health()
    _check(failures, True, "task_health roda sem exceção")
    daemon.task_learning()
    _check(failures, True, "task_learning roda sem exceção")

    # --- 24/7: watchdog condicionado ao progresso + tarefas de fundo ------------------
    import time as _time
    _check(failures, daemon._loop_alive(), "watchdog: loop fresco alimenta")
    daemon._last_tick = _time.time() - 10 * 3600
    _check(failures, not daemon._loop_alive(),
           "watchdog: loop travado deixa de alimentar (systemd reinicia)")
    daemon._last_tick = _time.time()
    ran = []
    import threading as _threading
    gate = _threading.Event()

    def slow_task():
        ran.append(1)
        gate.wait(5)

    daemon._run_due_bg("teste-bg", 0, slow_task, first_run_now=True)
    _time.sleep(0.1)
    daemon._run_due_bg("teste-bg", 0, slow_task, first_run_now=True)
    _time.sleep(0.1)
    _check(failures, len(ran) == 1,
           "tarefa de fundo não roda em duplicata enquanto a anterior vive")
    _check(failures, daemon._bg_threads["teste-bg"].is_alive(),
           "tarefa lenta roda em thread de fundo (loop principal livre)")
    gate.set()
    daemon._bg_threads["teste-bg"].join(5)
    daemon._run_due_bg("teste-bg", 0, slow_task, first_run_now=True)
    gate.set()
    _time.sleep(0.1)
    _check(failures, len(ran) == 2, "tarefa de fundo reexecuta após terminar")

    # --- bulkhead ----------------------------------------------------------------------------
    from .selfcare import Bulkhead
    bh = Bulkhead(journal)

    def explode():
        raise RuntimeError("boom")

    bh.run("teste", explode)
    _check(failures, "teste" in bh.failures, "bulkhead captura exceção")
    _check(failures, bh.run("teste", explode) is None,
           "bulkhead suspende subsistema em backoff")
    _check(failures, len(journal.self_errors_recent()) >= 1,
           "erro próprio registrado no self-journal")

    # --- botões inline, aprovações e conversa (2026-07-06) -----------------------------------
    # callback inline roteia pelo prefixo (sem rede: _call simulado)
    hits = []
    orion.allowed.add("1")
    orion._call = lambda *a, **k: {"ok": True}
    orion.register_callback("tst", lambda data, chat: hits.append(data) and None)
    orion._handle_callback({"id": "x", "data": "tst:abc",
                            "message": {"chat": {"id": 1}}})
    _check(failures, hits == ["tst:abc"], "callback inline roteia pelo prefixo")

    # docker-prune NUNCA automático: exige aprovação e o heal devolve a pendência
    from .healing import DEFAULT_ACTIONS
    prune = [a for a in DEFAULT_ACTIONS["disk"] if a["name"] == "docker-prune"]
    _check(failures, bool(prune) and prune[0].get("approval") is True,
           "docker-prune marcado como 'requer aprovação'")
    disk_fail = monitor.CheckResult("_system", "disk:/", False, "disco 99%",
                                    severity=monitor.SEV_CRIT)
    out_disk = healer_dry.heal(None, disk_fail, lambda: None)
    _check(failures,
           any(a.get("name") == "docker-prune"
               for a in out_disk.get("needs_approval") or []),
           "prune vira pergunta (needs_approval) em vez de executar")

    # .governor.json malicioso NÃO muda update_cmd de charter confirmado
    with open(os.path.join(project_dir, ".governor.json"), "w") as fh:
        json.dump({"update_cmd": "echo hacked",
                   "rules": {"auto_update": True}}, fh)
    catalog2 = discovery.discover(cfg, journal)
    charter_mod.sync_with_catalog(cfg, journal, catalog2)
    c2 = charter_mod.load_charter(cfg, "projeto-teste")
    _check(failures,
           c2.get("update_cmd") != "echo hacked"
           and (c2.get("pending_declared") or {}).get("update_cmd") == "echo hacked"
           and not (c2.get("rules") or {}).get("auto_update"),
           "update_cmd/rules do .governor.json em charter CONFIRMADO só entram "
           "como pendência (anti-escalada)")
    charter_mod.apply_pending_declared(cfg, journal, "projeto-teste")
    c3 = charter_mod.load_charter(cfg, "projeto-teste")
    _check(failures, c3.get("update_cmd") == "echo hacked"
           and (c3.get("rules") or {}).get("auto_update") is True,
           "aprovação pelo botão aplica a pendência do .governor.json")

    # recusa não re-pergunta enquanto o .governor.json não mudar (anti-loop)
    with open(os.path.join(project_dir, ".governor.json"), "w") as fh:
        json.dump({"update_cmd": "echo hacked2"}, fh)
    catalog3 = discovery.discover(cfg, journal)
    charter_mod.sync_with_catalog(cfg, journal, catalog3)
    charter_mod.discard_pending_declared(cfg, journal, "projeto-teste")
    charter_mod.sync_with_catalog(cfg, journal, catalog3)
    c4 = charter_mod.load_charter(cfg, "projeto-teste")
    _check(failures, not c4.get("pending_declared")
           and c4.get("update_cmd") == "echo hacked",
           "pendência recusada não volta a perguntar (anti-loop)")

    # conversa: sem api_key cai no fallback determinístico com o contexto
    from . import chat as chat_mod
    resp = chat_mod.answer(cfg, journal, "quem é você?", "CTX-DO-VPS")
    _check(failures, "Governante" in resp and "CTX-DO-VPS" in resp,
           "chat sem api_key responde com identidade + status")

    # heartbeat de cron DIÁRIO: dict {path, max_age_h} tolera 26h (não os 15min
    # do heartbeat always-on) — sem isso o Governante acha que toda esteira parou.
    hb_fresh = os.path.join(project_dir, "hb-fresh.txt")
    open(hb_fresh, "w").close()  # recém-criado = fresco
    # expected_always_on=false (cron, não serviço) NÃO pode desligar o heartbeat
    hb_charter = dict(confirmed, heartbeats=[{"path": hb_fresh, "max_age_h": 26}],
                      ports=[], endpoints=[],
                      rules={**(confirmed.get("rules") or {}), "expected_always_on": False})
    hb_results = monitor.project_checks(cfg, hb_charter, {})
    hb = [r for r in hb_results if r.check.startswith("heartbeat:")]
    _check(failures, bool(hb) and hb[0].ok,
           "heartbeat de cron diário (max_age_h=26) aceita arquivo fresco")
    old_mtime = _time.time() - 30 * 3600
    os.utime(hb_fresh, (old_mtime, old_mtime))
    hb_results2 = monitor.project_checks(cfg, hb_charter, {})
    hb2 = [r for r in hb_results2 if r.check.startswith("heartbeat:")]
    _check(failures, bool(hb2) and not hb2[0].ok,
           "heartbeat de 30h estourado (>26h) vira alerta")

    # daemon: aprovação de sistema ponta a ponta (pergunta -> botão -> executa)
    daemon.orion._call = lambda *a, **k: {"ok": True}
    daemon._request_sys_approval(disk_fail, dict(prune[0], cmd=["true"]), None)
    approvals = daemon._approvals()
    _check(failures, len(approvals) == 1, "aprovação de sistema registrada")
    aid = list(approvals)[0]
    reply = daemon._handle_sys_approval(aid, True)
    _check(failures, "✅" in reply and not daemon._approvals(),
           "botão Autorizar executa a ação aprovada e fecha a pendência")
    reply2 = daemon._handle_sys_approval(aid, True)
    _check(failures, "não existe" in reply2,
           "aprovação respondida não executa duas vezes")

    # roteamento de botão do daemon + conversa via chat_handler
    resp_btn = daemon.on_callback("gov:decl:projeto-inexistente:ok", "1")
    _check(failures, "Nada pendente" in resp_btn,
           "botão de .governor.json responde educado para pendência inexistente")
    resp_chat = daemon.on_chat("como estão as coisas?", "1")
    _check(failures, isinstance(resp_chat, str) and len(resp_chat) > 20,
           "conversa livre devolve resposta (fallback sem api_key)")
