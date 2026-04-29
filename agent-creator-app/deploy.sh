#!/bin/bash
set -e

echo "🚀 Iniciando deploy do CriaBot Agent Creator..."

# 1. Atualizar código do repositório
echo "📥 Baixando atualizações..."
git pull origin claude/agent-creator-app-0KB5D

# 2. Verificar se o .env existe
if [ ! -f ".env" ]; then
  echo "⚠️  Arquivo .env não encontrado!"
  echo "   Copie o exemplo: cp .env.example .env"
  echo "   Depois edite com suas chaves: nano .env"
  exit 1
fi

# 3. Build e subir containers
echo "🔨 Construindo imagens Docker..."
docker compose build --no-cache

echo "▶️  Subindo serviços..."
docker compose up -d

# 4. Aguardar backend ficar pronto
echo "⏳ Aguardando backend inicializar..."
for i in {1..30}; do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend OK!"
    break
  fi
  sleep 2
done

echo ""
echo "✅ Deploy concluído!"
echo "   Acesse: http://$(curl -sf ifconfig.me 2>/dev/null || echo 'SEU-IP')"
echo ""
echo "📋 Comandos úteis:"
echo "   Ver logs:     docker compose logs -f"
echo "   Parar:        docker compose down"
echo "   Reiniciar:    docker compose restart"
