"""Atualizações — projetos que não se atualizam sozinhos.

Política prudente para produção:
  - Detecta atualização disponível (git behind do remoto; updates de
    segurança do apt) e REPORTA sempre.
  - Só aplica sozinho quando o charter permite (rules.auto_update = true
    E update_cmd definido). Depois de aplicar, roda test_cmd (se houver);
    se o teste falhar, reporta imediatamente como incidente.
"""

import os

from .util import run_cmd, which


def check_project_updates(cfg, journal, charter):
    """Devolve dict {available, applied, detail} para um projeto git."""
    path = charter.get("path")
    result = {"project": charter["id"], "available": False, "applied": False,
              "detail": ""}
    if not path or not os.path.isdir(os.path.join(path, ".git")):
        return result
    rc, _, err = run_cmd(["git", "-C", path, "fetch", "--quiet"], timeout=120)
    if rc != 0:
        result["detail"] = "git fetch falhou: %s" % err[:150]
        return result
    rc, behind, _ = run_cmd(["git", "-C", path, "rev-list", "--count",
                             "HEAD..@{u}"], timeout=30)
    if rc != 0 or not behind.isdigit() or int(behind) == 0:
        return result
    result["available"] = True
    result["detail"] = "%s commit(s) atrás do remoto" % behind

    rules = charter.get("rules") or {}
    update_cmd = charter.get("update_cmd")
    if not (rules.get("auto_update") and update_cmd
            and charter.get("status") == "confirmed"):
        return result  # só reporta

    if cfg.dry_run:
        result["detail"] += " | [dry-run] aplicaria: %s" % update_cmd
        return result
    rc, out, err = run_cmd(update_cmd, timeout=600, cwd=path)
    journal.log("update", "update_cmd executado (rc=%d)" % rc,
                project=charter["id"], data={"cmd": update_cmd,
                                             "err": err[:300]})
    if rc != 0:
        result["detail"] += " | update_cmd FALHOU (rc=%d)" % rc
        return result
    result["applied"] = True
    test_cmd = charter.get("test_cmd")
    if test_cmd:
        rc, out, err = run_cmd(test_cmd, timeout=600, cwd=path)
        journal.log("update", "test_cmd pós-update (rc=%d)" % rc,
                    project=charter["id"])
        result["detail"] += " | atualizado; teste %s" % \
            ("OK" if rc == 0 else "FALHOU (rc=%d)" % rc)
        result["test_ok"] = rc == 0
    else:
        result["detail"] += " | atualizado (sem test_cmd definido)"
    return result


def check_apt_security(cfg):
    """Conta atualizações pendentes do sistema (report-only)."""
    if not which("apt-get"):
        return None
    rc, out, _ = run_cmd(
        ["bash", "-c",
         "apt-get -s upgrade 2>/dev/null | grep -c '^Inst' || true"],
        timeout=120)
    if rc == 0 and out.strip().isdigit() and int(out.strip()) > 0:
        return int(out.strip())
    return None
