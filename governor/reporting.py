"""Relatórios enviados ao Orion (Telegram) e à CLI.

Filosofia: independência operacional. O Governor só fala quando:
  - abre/resolve/escala um incidente (na hora);
  - descobre projeto novo pedindo confirmação de charter (na hora);
  - tem propostas de limpeza aguardando aprovação (no resumo diário);
  - resumo diário (o que aconteceu, o que foi corrigido sozinho);
  - relatório semanal (higiene, padrões aprendidos, melhorias sugeridas).
"""

import time

from . import charter as charter_mod
from . import hygiene
from .util import human_duration


def incident_opened(orion, incident, evidence=""):
    icon = "🔴" if incident.get("severity") == "critical" else "🟡"
    text = "%s [%s] %s\nChecagem: %s | aberto às %s" % (
        icon, incident["project"], incident["detail"],
        incident["check"], incident["opened_at"])
    if evidence:
        text += "\nEvidência:\n%s" % evidence[:800]
    orion.send(text)


def incident_healed(orion, project, check, action, duration_s, attempts):
    orion.send(
        "✅ [%s] corrigido sozinho: %s\nAção que funcionou: %s "
        "(tentativas: %d, fora do ar por %s)"
        % (project, check, action, attempts, human_duration(duration_s)))


def incident_escalated(orion, project, check, detail, reason, log_lines):
    text = ("🆘 [%s] NÃO consegui corrigir: %s\nMotivo: %s\n"
            "O que eu tentei:\n%s\n"
            "Preciso de intervenção humana." %
            (project, detail, reason,
             "\n".join("  • " + l for l in log_lines[-6:]) or "  (nada aplicável)"))
    orion.send(text)


def incident_chronic(orion, project, check, count, pattern):
    text = ("🔁 [%s] incidente CRÔNICO: %s já ocorreu %d vezes em 24h. "
            "Reiniciar está mascarando um problema de causa-raiz."
            % (project, check, count))
    if pattern:
        text += " Padrão temporal: concentrado em %s." % pattern
    text += "\nSugiro investigar logs/recursos nesse horário. Vou reduzir a "\
            "frequência de reinícios para não esconder o sintoma."
    orion.send(text)


def new_project(orion, charter):
    pid = charter["id"]
    orion.send(
        "🆕 Projeto novo descoberto!\n%s\n\n"
        "Está em MODO OBSERVAÇÃO (não vou mexer nele) até você confirmar a "
        "carta de missão." % charter_mod.summarize(charter),
        buttons=[[("✅ Confirmar", "gov:confirm:%s" % pid),
                  ("🚫 Ignorar", "gov:ignore:%s" % pid)]])


def new_projects_batch(orion, drafts):
    """Muitos projetos de uma vez (ex.: primeiro scan do servidor): UMA
    mensagem agrupada em vez de dezenas — e botões só na lista compacta."""
    lines = ["🆕 Descobri %d projeto(s) novos — todos em MODO OBSERVAÇÃO "
             "até você confirmar:" % len(drafts)]
    for c in drafts[:30]:
        lines.append("  • %s — %s" % (c["id"], (c.get("mission") or "?")[:70]))
    if len(drafts) > 30:
        lines.append("  … e mais %d (veja /projetos)." % (len(drafts) - 30))
    lines.append("\nConfirme um a um com os botões abaixo de cada /missao <id>, "
                 "ou em lote: /confirmar <id> pra cada um que for produção.")
    orion.send("\n".join(lines), silent=True)


def project_removed(orion, project_id):
    orion.send("📤 Projeto '%s' sumiu do servidor (diretório/serviços não "
               "encontrados). Se foi proposital, use /ignorar %s; senão, "
               "investigue." % (project_id, project_id))


def daily_digest(cfg, journal, learning, orion, catalog, charters):
    since = time.time() - 86400
    activity = journal.recent(limit=2000, since_epoch=since)
    incidents_open = journal.open_incidents()
    healed = [a for a in activity if a["kind"] == "incident"
              and "resolvido" in a.get("msg", "")]
    opened = [a for a in activity if a["kind"] == "incident"
              and "aberto" in a.get("msg", "")]
    heals = [a for a in activity if a["kind"] == "heal"]
    self_errors = journal.self_errors_recent(hours=24)

    confirmed = [c for c in charters.values() if c.get("status") == "confirmed"]
    drafts = [c for c in charters.values() if c.get("status") == "draft"]

    lines = ["🏛 Resumo diário do Governor",
             "Projetos: %d monitorados (%d confirmados, %d aguardando "
             "confirmação)" % (len(catalog), len(confirmed), len(drafts)),
             "Últimas 24h: %d incidente(s) aberto(s), %d resolvido(s), "
             "%d ação(ões) de correção" % (len(opened), len(healed), len(heals))]
    if incidents_open:
        lines.append("\n⚠️ Ainda abertos:")
        for inc in list(incidents_open.values())[:8]:
            lines.append("  • [%s] %s (desde %s)" %
                         (inc["project"], inc["detail"], inc["opened_at"]))
    if drafts:
        lines.append("\n📋 Aguardando sua confirmação (/confirmar <id>):")
        for c in drafts[:8]:
            lines.append("  • %s — %s" % (c["id"], c.get("mission", "")[:80]))
    pending = hygiene.pending_summary(cfg, limit=8)
    if pending:
        lines.append("\n" + pending)
    if self_errors:
        lines.append("\n🩺 Meus próprios tropeços (auto-registrados): %d — "
                     "estou me monitorando e me adaptando." % len(self_errors))
    if not opened and not incidents_open and not self_errors:
        lines.append("\nTudo estável. Nenhuma intervenção necessária. ✨")
    orion.send("\n".join(lines), silent=True)


def weekly_report(cfg, journal, learning, orion, charters, hygiene_notes,
                  update_findings):
    lines = ["📊 Relatório semanal do Governor"]
    insights = learning.insights()
    if insights:
        lines.append("\n🧠 Padrões aprendidos:")
        lines.extend("  " + i for i in insights)
    if update_findings:
        lines.append("\n⬆️ Atualizações:")
        for item in update_findings[:10]:
            lines.append("  • [%s] %s" % (item["project"], item["detail"]))
    if hygiene_notes:
        lines.append("\n🔎 Revisões sugeridas (não vou mexer sem você):")
        for note in hygiene_notes[:15]:
            lines.append("  " + note)
    pending = hygiene.pending_summary(cfg, limit=10)
    if pending:
        lines.append("\n" + pending)
    missions = [c for c in charters.values() if c.get("status") == "confirmed"]
    if missions:
        lines.append("\n🎯 Missões sob guarda:")
        for c in missions[:12]:
            lines.append("  • %s: %s" % (c["id"], (c.get("mission") or "")[:90]))
    if len(lines) == 1:
        lines.append("Semana tranquila — nada digno de nota.")
    orion.send("\n".join(lines), silent=True)


def status_text(cfg, journal, catalog, charters):
    incidents = journal.open_incidents()
    lines = ["🏛 Governor — status",
             "Projetos no catálogo: %d" % len(catalog)]
    for pid, c in sorted(charters.items()):
        badge = {"confirmed": "✅", "draft": "📝", "ignored": "🚫"}.get(
            c.get("status"), "?")
        open_here = [i for i in incidents.values() if i["project"] == pid]
        flag = " 🔴%d incidente(s)" % len(open_here) if open_here else ""
        lines.append("%s %s%s" % (badge, pid, flag))
    if incidents:
        lines.append("\nIncidentes abertos:")
        for inc in incidents.values():
            lines.append("  • [%s] %s" % (inc["project"], inc["detail"]))
    else:
        lines.append("\nSem incidentes abertos. ✨")
    return "\n".join(lines)
