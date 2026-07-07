"""Configuração do Governor.

Ordem de busca do config.json:
  1. $GOVERNOR_CONFIG
  2. /etc/governor/config.json
  3. <GOVERNOR_HOME>/config.json

Diretório de estado (GOVERNOR_HOME): $GOVERNOR_HOME ou /var/lib/governor.
Tudo que o Governor aprende e registra vive dentro de GOVERNOR_HOME.
"""

import copy
import os

from .util import atomic_write_json, ensure_dir, read_json

DEFAULTS = {
    "telegram": {
        # Bot PRÓPRIO do Governor (crie no BotFather — ex.: @governante0001_bot).
        # ⚠️ NUNCA reutilize o token de um bot que já faz getUpdates em outro
        # processo (ex.: o Orion): o Telegram derruba os dois com 409 Conflict.
        "token": "",
        "chat_id": "",
        # Somente estes chats podem enviar comandos; vazio = apenas chat_id.
        "allowed_chat_ids": [],
    },
    "chat": {
        # Conversa em linguagem natural (mensagens sem "/") — LLM externo.
        # Sem api_key: modo determinístico (status + comandos), nada quebra.
        "enabled": True,
        "api_key": "",
        "model": "MiniMax-M3",
        "base_url": "https://api.minimax.io/v1/text/chatcompletion_v2",
        "max_context_chars": 9000,
    },
    "scan_roots": ["/opt", "/srv", "/var/www", "/home", "/root"],
    "exclude_dirs": [
        "node_modules", ".git", "venv", ".venv", "env", "__pycache__",
        ".cache", ".npm", ".local", "snap", ".cargo", ".rustup",
        "site-packages", "dist-packages", ".Trash", "lost+found",
    ],
    "max_scan_depth": 3,
    "intervals": {
        "health": 60,          # checagens de saúde (s)
        "discovery": 600,      # busca por projetos novos (s)
        "hygiene": 86400,      # varredura de higiene (s)
        "learning": 300,       # consolidação de padrões (s)
        "selfcare": 60,        # auto-cuidado do Governor (s)
        "updates": 43200,      # checagem de updates dos projetos (s)
        "flush_queue": 120,    # reenvio de mensagens Telegram represadas (s)
        "idle_guard": 60,      # observação de recursos pesados parados (s)
    },
    "digest_hour": 8,          # hora local do resumo diário
    "weekly_digest_day": 0,    # 0 = segunda-feira (relatório semanal)
    "thresholds": {
        "disk_pct": 85,
        "disk_critical_pct": 95,
        "mem_pct": 90,
        "load_per_core": 2.0,
        "log_size_mb": 200,
        "big_file_mb": 100,
        "dup_min_mb": 1,
        "fails_before_incident": 2,   # debounce: falhas consecutivas p/ abrir incidente
        "max_heals_per_hour": 3,      # acima disso = flapping -> escala p/ humano
        "mem_growth_pct_per_hour": 10,  # tendência de vazamento de memória
        "cert_warn_days": 14,
        "self_mem_limit_mb": 300,     # RSS máximo do próprio Governor
    },
    "quarantine": {"retention_days": 14},
    "journal": {"retention_months": 6},
    "dry_run": False,          # true = registra o que faria, não executa ações
    "healing_enabled": True,
    "http_timeout": 6,
    "systemd_activating_grace_s": 900,
    "idle_guard": {
        "enabled": True,
        "observe_only": True,
        "notify": True,
        "browser": {
            "enabled": True,
            "profiles_dir": "/root/browser-harness/profiles",
            "lock_dir": "/run/browser-harness",
            "service_template": "browser-harness-chrome@%s.service",
            "idle_s": 300,
            "cooldown_s": 1800,
        },
        "tts": {
            "enabled": True,
            "pm2_name": "tts-local",
            "port": 8791,
            "idle_s": 300,
            "cooldown_s": 1800,
            "allow_stop": False,
        },
    },
    # Se o loop principal ficar sem progredir por este tempo (s), o Governor
    # para de alimentar o watchdog do systemd, que o mata e reinicia.
    "watchdog_stall_limit": 600,
}

_ENV_HOME = "GOVERNOR_HOME"
_ENV_CONFIG = "GOVERNOR_CONFIG"


def home_dir():
    return os.environ.get(_ENV_HOME, "/var/lib/governor")


def config_path():
    explicit = os.environ.get(_ENV_CONFIG)
    if explicit:
        return explicit
    etc = "/etc/governor/config.json"
    if os.path.exists(etc):
        return etc
    return os.path.join(home_dir(), "config.json")


def _deep_merge(base, override):
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class Config:
    """Config carregada + caminhos padrão de estado."""

    def __init__(self, data=None, path=None):
        self.path = path or config_path()
        self.data = _deep_merge(DEFAULTS, data or {})
        self.home = home_dir()

    # --- caminhos de estado -------------------------------------------------
    @property
    def charters_dir(self):
        return ensure_dir(os.path.join(self.home, "charters"))

    @property
    def state_dir(self):
        return ensure_dir(os.path.join(self.home, "state"))

    @property
    def journal_dir(self):
        return ensure_dir(os.path.join(self.home, "journal"))

    @property
    def quarantine_dir(self):
        return ensure_dir(os.path.join(self.home, "quarantine"))

    @property
    def playbooks_dir(self):
        return ensure_dir(os.path.join(self.home, "playbooks"))

    def state_file(self, name):
        return os.path.join(self.state_dir, name)

    # --- acesso -------------------------------------------------------------
    def get(self, *keys, default=None):
        node = self.data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    @property
    def dry_run(self):
        return bool(self.data.get("dry_run"))

    def threshold(self, name):
        return self.data["thresholds"].get(name, DEFAULTS["thresholds"].get(name))

    def interval(self, name):
        return self.data["intervals"].get(name, DEFAULTS["intervals"].get(name))


def load():
    path = config_path()
    data = read_json(path, default={})
    return Config(data=data, path=path)


def write_example(path):
    example = copy.deepcopy(DEFAULTS)
    example["telegram"]["token"] = \
        "TOKEN_DE_UM_BOT_NOVO_SO_DO_GOVERNOR (BotFather; NUNCA o do Orion)"
    example["telegram"]["chat_id"] = "COLOQUE_O_CHAT_ID"
    example["chat"]["api_key"] = "OPCIONAL_MINIMAX_API_KEY_para_conversa_livre"
    atomic_write_json(path, example)
    return path
