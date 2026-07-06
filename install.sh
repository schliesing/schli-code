#!/usr/bin/env bash
# Instalador do Governor no VPS.
# Uso: sudo bash install.sh   (rode de dentro do clone deste repositório)
set -euo pipefail

INSTALL_DIR=/opt/governor
HOME_DIR=/var/lib/governor
CONFIG_DIR=/etc/governor
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Rode como root: sudo bash install.sh" >&2
  exit 1
fi

if ! command -v python3 >/dev/null; then
  echo "python3 não encontrado — instale com: apt-get install -y python3" >&2
  exit 1
fi

echo "==> Instalando código em $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
if [[ -d "$REPO_DIR/.git" && "$REPO_DIR" != "$INSTALL_DIR" ]]; then
  # instala como clone git para habilitar `governorctl self-update`
  if [[ ! -d "$INSTALL_DIR/.git" ]]; then
    rm -rf "$INSTALL_DIR"
    git clone "$REPO_DIR" "$INSTALL_DIR"
    (cd "$INSTALL_DIR" && git remote set-url origin \
      "$(cd "$REPO_DIR" && git remote get-url origin 2>/dev/null || echo "$REPO_DIR")")
  else
    (cd "$INSTALL_DIR" && git pull --ff-only || true)
  fi
else
  cp -r "$REPO_DIR/governor" "$INSTALL_DIR/"
fi

echo "==> Criando diretórios de estado em $HOME_DIR"
mkdir -p "$HOME_DIR"/{charters,state,journal,quarantine,playbooks}
chmod 750 "$HOME_DIR"

echo "==> Config em $CONFIG_DIR/config.json"
mkdir -p "$CONFIG_DIR"
if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
  cp "$REPO_DIR/config/config.example.json" "$CONFIG_DIR/config.json"
  chmod 600 "$CONFIG_DIR/config.json"
  echo "    !!! Edite $CONFIG_DIR/config.json e preencha token e chat_id do bot Orion."
fi

echo "==> Validando instalação (selftest)"
(cd "$INSTALL_DIR" && python3 -m governor selftest)

echo "==> CLI: /usr/local/bin/governorctl"
cat > /usr/local/bin/governorctl <<WRAP
#!/usr/bin/env bash
export GOVERNOR_HOME=\${GOVERNOR_HOME:-$HOME_DIR}
export GOVERNOR_CONFIG=\${GOVERNOR_CONFIG:-$CONFIG_DIR/config.json}
cd $INSTALL_DIR && exec python3 -m governor "\$@"
WRAP
chmod +x /usr/local/bin/governorctl

echo "==> Serviço systemd"
cp "$REPO_DIR/systemd/governor.service" /etc/systemd/system/governor.service
systemctl daemon-reload
systemctl enable governor.service

cat <<FIM

Instalação concluída. Próximos passos:
  1. Edite $CONFIG_DIR/config.json (token/chat_id do Orion, raízes de varredura)
  2. sudo systemctl start governor
  3. Acompanhe: journalctl -u governor -f
  4. No Telegram: /status  — e confirme os charters com /confirmar <id>

Comandos úteis: governorctl status | scan | health | hygiene | proposals
FIM
