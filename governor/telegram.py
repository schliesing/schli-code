"""Cliente do bot Telegram Orion — canal de informações dos projetos.

- Envio com fila offline: se o Telegram estiver inacessível, a mensagem é
  gravada em disco e reenviada quando a conexão voltar (nada se perde).
- Long-polling de comandos (/status, /aprovar, /confirmar, ...) restrito
  aos chats autorizados.
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
    def send(self, text, chat_id=None, silent=False):
        """Envia mensagem; em falha, enfileira em disco para reenvio."""
        chat = str(chat_id or self.chat_id)
        if not self.token or not chat:
            # Sem Telegram configurado: registra no journal para não perder.
            self.journal.log("telegram", "nao configurado; msg registrada",
                             data={"text": text[:500]})
            return False
        ok = True
        for chunk in _split(text):
            if not self._send_once(chunk, chat, silent):
                self._enqueue(chunk, chat)
                ok = False
        return ok

    def _send_once(self, text, chat, silent):
        try:
            result = self._call("sendMessage", {
                "chat_id": chat,
                "text": text,
                "disable_notification": "true" if silent else "false",
            })
            return bool(result.get("ok"))
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return False

    def _enqueue(self, text, chat):
        append_jsonl(self.queue_path, {"ts": time.time(), "chat": chat, "text": text})

    def flush_queue(self):
        """Reenvia mensagens represadas (chamado periodicamente pelo daemon)."""
        pending = read_jsonl(self.queue_path)
        if not pending:
            return 0
        sent = 0
        remaining = []
        for item in pending:
            if sent < 20 and self._send_once(item["text"], item["chat"], True):
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
        atomic_write_json(self.offset_path, state)

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
