"""CLI do Governor (`governorctl` ou `python3 -m governor`)."""

import argparse
import json
import sys

from . import __version__
from . import charter as charter_mod
from . import discovery, hygiene, monitor, reporting
from .config import load as load_config, write_example
from .journal import Journal
from .learning import Learning


def build_parser():
    parser = argparse.ArgumentParser(
        prog="governorctl",
        description="Governor — agente governante do VPS (v%s)" % __version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("start", help="inicia o daemon (uso normal: via systemd)")
    sub.add_parser("status", help="visão geral: projetos, incidentes")
    sub.add_parser("scan", help="roda a descoberta de projetos agora")
    sub.add_parser("health", help="roda as checagens de saúde agora (sem healing)")
    sub.add_parser("hygiene", help="roda a varredura de higiene agora")
    sub.add_parser("charters", help="lista as cartas de missão")
    p = sub.add_parser("confirm", help="confirma o charter de um projeto")
    p.add_argument("project_id")
    p = sub.add_parser("ignore", help="ignora um projeto")
    p.add_argument("project_id")
    sub.add_parser("proposals", help="lista propostas de limpeza pendentes")
    p = sub.add_parser("approve", help="aprova uma proposta (vai p/ quarentena)")
    p.add_argument("proposal_id")
    p = sub.add_parser("reject", help="rejeita uma proposta")
    p.add_argument("proposal_id")
    p = sub.add_parser("restore", help="restaura item da quarentena")
    p.add_argument("proposal_id")
    p = sub.add_parser("note", help="registra anotação num projeto (p/ o "
                                    "Governor aprender mudanças intencionais)")
    p.add_argument("project_id")
    p.add_argument("text", nargs="+")
    p = sub.add_parser("journal", help="últimas entradas do diário")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--project")
    sub.add_parser("insights", help="padrões aprendidos até agora")
    sub.add_parser("selftest", help="autoteste completo (usado no auto-update)")
    sub.add_parser("self-update", help="atualiza o próprio Governor (com rollback)")
    p = sub.add_parser("init-config", help="gera config de exemplo")
    p.add_argument("path", nargs="?", default="config.json")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "selftest":
        from .selftest import run as selftest_run
        sys.exit(selftest_run())
    if args.command == "init-config":
        path = write_example(args.path)
        print("Config de exemplo escrita em %s" % path)
        return

    cfg = load_config()
    journal = Journal(cfg)

    if args.command == "start":
        from .daemon import Daemon
        Daemon(cfg).run()
    elif args.command == "status":
        catalog = discovery.load_catalog(cfg)
        charters = charter_mod.all_charters(cfg)
        print(reporting.status_text(cfg, journal, catalog, charters))
    elif args.command == "scan":
        catalog = discovery.discover(cfg, journal)
        discovery.save_catalog(cfg, catalog)
        drafts = charter_mod.sync_with_catalog(cfg, journal, catalog)
        print("Projetos encontrados: %d" % len(catalog))
        for pid, info in sorted(catalog.items()):
            print("  %-30s %s" % (pid, info.get("path", "")))
        if drafts:
            print("Novos charters rascunho: %s (confirme com "
                  "`governorctl confirm <id>`)"
                  % ", ".join(d["id"] for d in drafts))
    elif args.command == "health":
        state = monitor.load_monitor_state(cfg)
        results = monitor.system_checks(cfg)
        for c in charter_mod.all_charters(cfg).values():
            if c.get("status") != charter_mod.STATUS_IGNORED:
                results.extend(monitor.project_checks(cfg, c, state))
        monitor.save_monitor_state(cfg, state)
        for r in results:
            print("%s %-12s %-28s %s" % ("✅" if r.ok else "❌",
                                         r.project, r.check, r.detail))
        sys.exit(0 if all(r.ok for r in results) else 1)
    elif args.command == "hygiene":
        for pid, c in charter_mod.all_charters(cfg).items():
            if c.get("status") == charter_mod.STATUS_IGNORED:
                continue
            findings, notes = hygiene.scan_project(cfg, c)
            added = hygiene.register_findings(cfg, journal, pid, findings)
            print("[%s] %d achado(s), %d novo(s) proposto(s)"
                  % (pid, len(findings), len(added)))
            for note in notes:
                print("   " + note)
        print(hygiene.pending_summary(cfg) or "Nada pendente.")
    elif args.command == "charters":
        for c in sorted(charter_mod.all_charters(cfg).values(),
                        key=lambda c: c["id"]):
            print(charter_mod.summarize(c))
            print()
    elif args.command == "confirm":
        c = charter_mod.confirm(cfg, journal, args.project_id)
        print("confirmado" if c else "projeto não encontrado")
    elif args.command == "ignore":
        c = charter_mod.ignore(cfg, journal, args.project_id)
        print("ignorado" if c else "projeto não encontrado")
    elif args.command == "proposals":
        print(hygiene.pending_summary(cfg, limit=100) or "Nada pendente.")
    elif args.command == "approve":
        prop, msg = hygiene.approve(cfg, journal, args.proposal_id)
        print(msg)
    elif args.command == "reject":
        prop = hygiene.reject(cfg, journal, args.proposal_id)
        print("rejeitada" if prop else "proposta não encontrada")
    elif args.command == "restore":
        result = hygiene.restore(cfg, journal, args.proposal_id)
        print(result[1] if isinstance(result, tuple) else "falhou")
    elif args.command == "note":
        text = " ".join(args.text)
        c = charter_mod.add_note(cfg, journal, args.project_id, text)
        print("anotado" if c else "projeto não encontrado")
    elif args.command == "journal":
        for rec in journal.recent(limit=args.limit, project=args.project):
            print("%s [%s] %s%s" % (rec["ts"], rec["kind"],
                                    ("(%s) " % rec["project"])
                                    if rec.get("project") else "",
                                    rec["msg"]))
    elif args.command == "insights":
        learning = Learning(cfg, journal)
        lines = learning.insights()
        print("\n".join(lines) if lines else "Nenhum padrão relevante ainda.")
    elif args.command == "self-update":
        from .selfcare import self_update
        ok, msg = self_update(cfg, journal)
        print(msg)
        sys.exit(0 if ok else 1)
    else:
        build_parser().print_help()
