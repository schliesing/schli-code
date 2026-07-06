# Bloco para o CLAUDE.md dos projetos do VPS

Cole a seção abaixo no `CLAUDE.md` de **cada projeto** rodando no VPS.
Assim, toda sessão do Claude que mexer no projeto coopera com o Governor —
mudanças intencionais são registradas (em vez de parecerem drift) e a carta
de missão nunca fica desatualizada.

---

## 🏛 Governor (agente governante do VPS)

Este projeto é monitorado pelo **Governor** (`/opt/governor`), que vigia
serviços, portas, endpoints, logs e recursos, corrige quedas conforme a
carta de missão e reporta pelo bot Telegram Orion.

Regras para qualquer sessão do Claude neste projeto:

1. **Carta de missão é lei.** O arquivo `.governor.json` na raiz declara a
   missão, serviços, portas, endpoints e comandos de update/teste deste
   projeto. Se você criar, renomear ou remover um serviço, porta, endpoint
   ou log, **atualize `.governor.json` no mesmo commit** — senão o Governor
   tratará a mudança como desvio e poderá "corrigi-la" de volta.
2. **Registre mudanças relevantes** para o Governor aprender que foram
   intencionais:
   `governorctl note <id-do-projeto> "o que mudou e por quê"`
3. **Não crie arquivos-lixo** (`*.bak`, `arquivo_v2`, `copia de ...`):
   o Governor os detecta e propõe remoção. Use git para versões.
4. **Missão primária** — nunca a perca de vista; ela está no topo de
   `.governor.json` e pode ser consultada com `/missao <id>` no Orion ou
   `governorctl charters`.
5. Se o deploy mudar (systemd ↔ docker ↔ pm2), rode `governorctl scan` e
   confira o charter com `governorctl charters` antes de encerrar a sessão.

Estado do Governor: `/var/lib/governor` (charters, journal, quarentena).
Comandos úteis: `governorctl status | health | note | charters`.
