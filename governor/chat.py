"""Conversa em linguagem natural com o operador (mensagens sem "/").

O Governante responde perguntas sobre o VPS ("como estão os projetos?",
"o que você fez hoje?", "quem é você?") usando um LLM externo (MiniMax-M3,
API OpenAI-compatível) alimentado com um RETRATO REAL do estado atual —
charters, incidentes, propostas e as últimas ações do journal. Sem chave de
API configurada (chat.api_key na config), cai num modo determinístico que
devolve o /status e explica o que sabe fazer.

Stdlib pura (urllib) — invariante do projeto. O LLM só ESCREVE a resposta;
nenhuma ação é executada por aqui (ações continuam nos comandos e botões,
com as travas de sempre).
"""

import json
import urllib.error
import urllib.request

PERSONA = (
    "Você é o GOVERNANTE 🏛 (@governante0001_bot), o agente-governador do VPS "
    "do Rafa. Sua função permanente: DESCOBRIR os projetos do servidor, "
    "MONITORAR a saúde deles (systemd, docker, pm2, portas, HTTP, logs, "
    "memória, certificados, disco), CORRIGIR sozinho o que tem playbook "
    "seguro em projeto confirmado, propor LIMPEZAS (sempre com aprovação e "
    "quarentena, nunca deleção direta), acompanhar ATUALIZAÇÕES e reportar "
    "tudo por este bot no Telegram. Ações sensíveis (ex.: docker prune, "
    "mudanças de update_cmd) você SEMPRE pergunta antes, com botões. Você "
    "também faz VIGILÂNCIA DE SEGURANÇA comportamental (observe-only): detecta "
    "sinais de agente hostil/ransomware no VPS — banco gerando shell, porta de "
    "C2, nota de resgate, cron que baixa-e-executa — e alerta na hora (nunca "
    "corrige sozinho suspeita de intrusão; isso é pra humano decidir).\n"
    "Como responder: em PT-BR, direto e claro, com analogias simples quando "
    "ajudarem. Baseie-se SOMENTE no ESTADO ATUAL abaixo — são seus dados "
    "reais de agora. NÃO invente números, projetos nem incidentes. Se a "
    "resposta não estiver nos dados, diga o que você checaria e sugira o "
    "comando certo (/status, /projetos, /missao <id>, /propostas, "
    "/relatorio, /confirmar <id>, /pausar). Perguntas fora do tema VPS: "
    "responda curto e traga a conversa de volta pro servidor. Assine ideias "
    "de melhoria como sugestão, não como ação já feita."
)

FALLBACK = (
    "🏛 Sou o Governante — descubro, vigio e corrijo os projetos deste VPS "
    "e te aviso por aqui. Ainda estou sem meu cérebro de conversa (chat."
    "api_key não configurada), então vou de resposta objetiva:\n\n%s\n\n"
    "Comandos: /status /projetos /missao <id> /propostas /relatorio /ajuda"
)


def answer(cfg, journal, question, context_text):
    """Responde `question` usando o LLM com `context_text` como realidade.

    Nunca levanta exceção — em qualquer falha devolve o fallback com status.
    """
    api_key = cfg.get("chat", "api_key", default="") or ""
    if not cfg.get("chat", "enabled", default=True) or not api_key:
        return FALLBACK % context_text[:2500]
    base_url = cfg.get(
        "chat", "base_url",
        default="https://api.minimax.io/v1/text/chatcompletion_v2")
    model = cfg.get("chat", "model", default="MiniMax-M3")
    max_chars = int(cfg.get("chat", "max_context_chars", default=9000))
    payload = {
        "model": model,
        "messages": [
            {"role": "system",
             "content": PERSONA + "\n\n=== ESTADO ATUAL DO VPS (agora) ===\n"
             + context_text[:max_chars]},
            {"role": "user", "content": question[:2000]},
        ],
        "max_tokens": 900,
        "temperature": 0.4,
    }
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer %s" % api_key})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        choices = data.get("choices") or []
        msg = (choices[0].get("message") or {}) if choices else {}
        text = (msg.get("content") or "").strip()
        if text:
            return text[:3800]
        journal.log("chat", "LLM devolveu resposta vazia",
                    data={"base_resp": str(data)[:300]})
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        journal.log("chat", "LLM indisponível: %s" % str(exc)[:150])
    return ("⚠️ Meu cérebro de conversa não respondeu agora — vou de resposta "
            "objetiva:\n\n%s" % context_text[:2500])
