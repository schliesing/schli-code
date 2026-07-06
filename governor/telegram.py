"""Cliente do bot Telegram do Governor (bot PRÓPRIO — ex.: @governante0001_bot).

⚠️ NUNCA reutilize o token de outro bot que já faça getUpdates (ex.: o Orion
do VPS): o Telegram só permite UM consumidor de getUpdates por token — dois
processos no mesmo token entram em guerra de 409 e ambos param de receber.

- Envio com fila offline: se o Telegram estiver inacessível, a mensagem é
  gravada em disco e reenviada quando a conexão voltar (nada se perde).
- Long-polling de comandos (/status, /aprovar, /confirmar, ...) restrito
  aos chats autorizados.
- Botões inline: send(..., buttons=[[("rótulo", "dado"), ...]]) e handlers
  de callback por prefixo (register_callback) — toda pergunta de modificação
  de sistema vai com botões, não com "digite /comando".
- Conversa livre: mensagem que NÃO começa com "/" vai para o chat_handler
  (o Governor responde em linguagem natural sobre o estado do VPS).
- Sem dependências: usa urllib da stdlib.
"""

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .util import append_jsonl, atomic_write_json, read_json, read_jsonl

API = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 3900  # margem sob o limite de 4096 do Telegram


class Orion:
    def __init__(self, cfg, journal):
        self.cfg = cfg
        self.journal = journal
        self.token = cfg.get("telegram", "token", default="") or ""
        self.chat_id = str(cfg.get("telegram", "chat_id", default="") or "")
        allowed = cfg.get("telegram", "allowed_chat_ids", default=[]) or []
        self.allowed = {str(c) for c in allowed}
        if self.chat_id:
            self.allowed.add(self.chat_id)
        self.queue_path = cfg.state_file("telegram-queue.jsonl")
        self.offset_path = cfg.state_file("telegram-offset.json")
        self.handlers = {}      # comando -> fn(args, chat_id) -> resposta str
        self.callback_handlers = {}  # prefixo -> fn(data, chat_id) -> resposta
        self.chat_handler = None     # fn(texto, chat_id) -> resposta (conversa livre)
        self._stop = threading.Event()
        self._thread = None

    @property
    def configured(self):
        return bool(self.token and self.chat_id)

    # --- API bruta -----------------------------------------------------------
    def _call(self, method, params, timeout=15):
        url = API.format(token=self.token, method=method)
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())

    # --- envio ---------------------------------------------------------------
    def send(self, text, chat_id=None, silent=False, buttons=None):
        """Envia mensagem; em falha, enfileira em disco para reenvio.

        buttons: lista de LINHAS de botões inline; cada botão é (rótulo, dado)
        — o dado volta no callback_query e é roteado por register_callback.
        """
        chat = str(chat_id or self.chat_id)
        if not self.token or not chat:
            # Sem Telegram configurado: registra no journal para não perder.
            self.journal.log("telegram", "nao configurado; msg registrada",
                             data={"text": text[:500]})
            return False
        ok = True
        chunks = _split(text)
        for i, chunk in enumerate(chunks):
            # botões só no último pedaço (a pergunta fica junto da resposta)
            btns = buttons if i == len(chunks) - 1 else None
            if not self._send_once(chunk, chat, silent, btns):
                self._enqueue(chunk, chat, btns)
                ok = False
        return ok

    def _send_once(self, text, chat, silent, buttons=None):
        params = {
            "chat_id": chat,
            "text": text,
            "disable_notification": "true" if silent else "false",
        }
        if buttons:
            params["reply_markup"] = json.dumps({"inline_keyboard": [
                [{"text": label, "callback_data": data[:64]}
                 for (label, data) in row]
                for row in buttons
            ]})
        try:
            result = self._call("sendMessage", params)
            return bool(result.get("ok"))
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return False

    def _enqueue(self, text, chat, buttons=None):
        item = {"ts": time.time(), "chat": chat, "text": text}
        if buttons:
            item["buttons"] = [[list(b) for b in row] for row in buttons]
        append_jsonl(self.queue_path, item)

    def flush_queue(self):
        """Reenvia mensagens represadas (chamado periodicamente pelo daemon)."""
        pending = read_jsonl(self.queue_path)
        if not pending:
            return 0
        sent = 0
        remaining = []
        for item in pending:
            btns = [[tuple(b) for b in row] for row in item.get("buttons") or []] or None
            if sent < 20 and self._send_once(item["text"], item["chat"], True, btns):
                sent += 1
            else:
                remaining.append(item)
        try:
            os.remove(self.queue_path)
        except OSError:
            pass
        for item in remaining:
            append_jsonl(self.queue_path, item)
        if sent:
            self.journal.log("telegram", "fila reenviada: %d mensagens" % sent)
        return sent

    # --- comandos ------------------------------------------------------------
    def register(self, command, handler):
        """Registra handler para um comando (sem a barra)."""
        self.handlers[command.lstrip("/").lower()] = handler

    def register_callback(self, prefix, handler):
        """Registra handler para callback_data que começa com 'prefixo:'.
        handler(data, chat_id) -> resposta opcional (str)."""
        self.callback_handlers[prefix.lower()] = handler

    def poll_loop(self):
        """Long-polling do getUpdates; roda em thread própria."""
        while not self._stop.is_set():
            if not self.configured:
                self._stop.wait(30)
                continue
            try:
                self._poll_once()
            except Exception as exc:  # nunca derruba a thread
                self.journal.self_error("telegram.poll", exc)
                self._stop.wait(15)

    def _poll_once(self):
        state = read_json(self.offset_path, default={"offset": 0})
        try:
            result = self._call("getUpdates", {
                "offset": state["offset"] + 1,
                "timeout": 25,
            }, timeout=35)
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            self._stop.wait(15)
            return
        for update in result.get("result", []):
            state["offset"] = max(state["offset"], update["update_id"])
            # 1) botão inline clicado
            callback = update.get("callback_query")
            if callback:
                self._handle_callback(callback)
                continue
            # 2) mensagem de texto
            message = update.get("message") or update.get("edited_message") or {}
            text = (message.get("text") or "").strip()
            chat = str((message.get("chat") or {}).get("id", ""))
            if not text or not chat:
                continue
            if chat not in self.allowed:
                self.journal.log("telegram", "comando de chat nao autorizado",
                                 data={"chat": chat, "text": text[:100]})
                continue
            if text.startswith("/"):
                self._dispatch(text, chat)
            elif self.chat_handler:
                self._dispatch_chat(text, chat)
        atomic_write_json(self.offset_path, state)

    def _handle_callback(self, callback):
        """Botão inline: valida o chat, confirma o clique (answerCallbackQuery)
        e roteia pelo prefixo do callback_data ('prefixo:resto')."""
        data = str(callback.get("data") or "")
        chat = str(((callback.get("message") or {}).get("chat") or {})
                   .get("id", "") or (callback.get("from") or {}).get("id", ""))
        try:  # tira o "relógio" do botão; best-effort
            self._call("answerCallbackQuery", {"callback_query_id": callback.get("id", "")})
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            pass
        if not data or chat not in self.allowed:
            self.journal.log("telegram", "callback de chat nao autorizado",
                             data={"chat": chat, "data": data[:80]})
            return
        prefix = data.split(":", 1)[0].lower()
        handler = self.callback_handlers.get(prefix)
        if not handler:
            self.send("Botão sem dono (prefixo '%s') — versão antiga?" % prefix,
                      chat_id=chat)
            return
        self.journal.log("telegram", "callback recebido",
                         data={"data": data[:120], "chat": chat})
        try:
            reply = handler(data, chat)
        except Exception as exc:  # nunca derruba a thread de polling
            self.journal.self_error("telegram.callback.%s" % prefix, exc)
            reply = "⚠️ Erro ao processar o botão — registrado no meu journal."
        if reply:
            self.send(reply, chat_id=chat)

    def _dispatch_chat(self, text, chat):
        """Mensagem livre (sem '/') → conversa em linguagem natural."""
        self.journal.log("telegram", "conversa recebida",
                         data={"chat": chat, "text": text[:200]})
        try:
            reply = self.chat_handler(text, chat)
        except Exception as exc:  # noqa: BLE001 — conversa nunca derruba o polling
            self.journal.self_error("telegram.chat", exc)
            reply = ("⚠️ Tropecei ao pensar na resposta (erro registrado). "
                     "Tenta /status ou /ajuda enquanto me recupero.")
        if reply:
            self.send(reply, chat_id=chat)

    def _dispatch(self, text, chat):
        parts = text.split()
        command = parts[0].lstrip("/").split("@")[0].lower()
        args = parts[1:]
        handler = self.handlers.get(command)
        if not handler:
            known = ", ".join("/" + c for c in sorted(self.handlers))
            self.send("Comando desconhecido. Disponíveis: %s" % known, chat_id=chat)
            return
        self.journal.log("telegram", "comando recebido: /%s" % command,
                         data={"args": args, "chat": chat})
        try:
            reply = handler(args, chat)
        except Exception as exc:
            self.journal.self_error("telegram.cmd.%s" % command, exc)
            reply = "⚠️ Erro ao executar /%s — registrado no meu journal." % command
        if reply:
            self.send(reply, chat_id=chat)

    def start_polling(self):
        if self._thread:
            return
        self._thread = threading.Thread(target=self.poll_loop, name="orion-poll",
                                        daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()


def _split(text):
    if len(text) <= MAX_LEN:
        return [text]
    chunks = []
    while text:
        cut = text.rfind("\n", 0, MAX_LEN)
        if cut < MAX_LEN // 2:
            cut = MAX_LEN
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks
