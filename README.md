# 🏛 Governor — agente governante do VPS

Agente de background que **descobre, entende, monitora, corrige, testa,
higieniza e reporta** todos os projetos do servidor — e que também cuida
de si mesmo. Reporta pelo bot Telegram **Orion**.

Zero dependências: Python 3.8+ puro (stdlib). Exporte para o VPS e rode.

## O que ele resolve

| Problema | Resposta do Governor |
|---|---|
| "algo quebra de tempo em tempo" | checagens de saúde a cada 60s + playbooks de correção com teste pós-fix |
| "desconecta sozinho / falha silenciosamente" | monitora portas, endpoints HTTP, containers, units, pm2 e erros novos em logs |
| "esquece a missão primária do projeto" | carta de missão (charter) por projeto, confirmada por você e vigiada como lei |
| "sai do contexto ordenado original" | baseline de "estado bom conhecido" + alerta de drift estrutural |
| "acumula dados desnecessários" | varredura de higiene: duplicados, órfãos, versões mortas, logs gigantes |
| "não se atualiza sozinho" | detecção de updates (git/apt); aplica sozinho só onde você autorizar, com teste e reporte |
| "nada observa o todo nem aprende padrões" | learning: incidentes crônicos, padrões de horário, taxa de sucesso de cada correção |
| "e se o vigia quebrar?" | self-healing próprio: watchdog systemd, bulkheads, self-journal, auto-update com rollback |

## Instalação no VPS

```bash
git clone <este-repo> schli-code && cd schli-code
sudo bash install.sh
sudo nano /etc/governor/config.json   # token e chat_id do bot Orion
sudo systemctl start governor
```

Acompanhe com `journalctl -u governor -f` e, no Telegram, `/status`.

## O ciclo de vida de um projeto

1. **Descoberta** — o Governor varre `scan_roots` (e docker, systemd, pm2,
   portas) a cada 10 min. Projeto novo → gera uma **carta de missão
   rascunho** inferindo missão, serviços, portas e endpoints, e avisa no Orion.
2. **Confirmação** — você revisa e responde `/confirmar <id>` (ou edita
   `/var/lib/governor/charters/<id>.json` antes). Até lá o projeto fica em
   **modo observação**: o Governor reporta, mas não toca em nada.
3. **Governo** — com a carta confirmada, as regras viram lei: serviço caiu →
   playbook corrige → a checagem roda de novo para **provar** que corrigiu →
   você recebe "corrigido sozinho" no Orion. Se não conseguir, escala com o
   histórico do que tentou.
4. **Aprendizado** — cada correção alimenta as estatísticas: ações boas sobem
   na fila, ações que falham 3x entram em quarentena, incidente que repete 3x
   em 24h é declarado **crônico** (reiniciar mascara; ele pede investigação e
   mostra o padrão de horário). Após 7 dias estável, o estado vira baseline.

## Segurança em camadas (por que ele não vai destruir nada)

- **Observe-only até você confirmar** a carta de missão de cada projeto.
- Limpeza **nunca deleta**: achado → proposta → sua aprovação → **quarentena**
  em `/var/lib/governor/quarantine` → só some de verdade após 14 dias
  (restaure com `/restaurar <id>` ou `governorctl restore <id>`).
- Anti-flapping: no máx. `max_restarts_per_hour` correções; acima disso, escala.
- `dry_run: true` na config faz ele registrar o que **faria**, sem executar.
- `/pausar` suspende qualquer ação na hora (continua observando).
- Auto-update do próprio Governor só é adotado se o **selftest** da versão
  nova passar; senão faz rollback automático e avisa.

## Comandos

**Telegram (Orion):** `/status` `/projetos` `/missao <id>` `/confirmar <id>`
`/ignorar <id>` `/propostas` `/aprovar <id>` `/rejeitar <id>` `/restaurar <id>`
`/relatorio` `/pausar` `/retomar` `/ajuda`

**CLI (`governorctl`):** `status` `scan` `health` `hygiene` `charters`
`confirm` `proposals` `approve` `reject` `restore` `note <id> <texto>`
`journal` `insights` `selftest` `self-update`

## Integração com projetos (e com o Claude)

- Cada projeto pode se **auto-declarar** criando `.governor.json` na raiz
  (missão, endpoints, serviços, `update_cmd`, `test_cmd`, regras). Campos
  declarados têm prioridade sobre os inferidos. Exemplo em
  [`docs/governor.example.json`](docs/governor.example.json).
- Adicione o bloco de [`docs/CLAUDE-SNIPPET.md`](docs/CLAUDE-SNIPPET.md) ao
  `CLAUDE.md` de cada projeto do VPS: assim toda sessão do Claude que mexer no
  projeto mantém o charter em dia e registra mudanças com
  `governorctl note <id> "..."` — o Governor aprende que a mudança foi
  intencional em vez de tratá-la como drift.

## O que ele reporta (e quando)

- **Na hora**: incidente aberto, corrigido sozinho, escalado, crônico;
  projeto novo/removido; drift de baseline; previsão de disco cheio.
- **Diário** (8h): resumo do dia — incidentes, correções, pendências suas.
- **Semanal** (segunda): padrões aprendidos, updates disponíveis, sugestões
  de revisão (código órfão, .env aberto), missões sob guarda.
- **Silêncio = tudo bem.** Ele só fala quando há algo útil.

## Arquitetura

```
governor/
├── daemon.py     loop principal + agenda + comandos Telegram
├── discovery.py  auto-descoberta (fs, docker, systemd, pm2, portas)
├── charter.py    cartas de missão + confirmação + .governor.json
├── monitor.py    checagens de saúde (units, containers, portas, http,
│                 logs, memória c/ tendência, certs, git, backups)
├── healing.py    playbooks + verificação pós-fix + anti-flapping
├── hygiene.py    duplicados/órfãos/versões mortas → proposta → quarentena
├── learning.py   padrões, crônicos, baseline, ranking de ações
├── selfcare.py   bulkheads, watchdog, memória própria, auto-update c/ rollback
├── updates.py    updates git/apt (aplica só com autorização + teste)
├── reporting.py  mensagens do Orion (incidentes, digests, relatórios)
├── journal.py    trilha de auditoria + self-journal de erros próprios
├── telegram.py   bot Orion (fila offline: mensagem nunca se perde)
└── selftest.py   autoteste completo — gate do auto-update
```

Estado em `/var/lib/governor` (charters, journal, quarentena, aprendizado).
Playbooks custom por projeto em `/var/lib/governor/playbooks/<id>.json`.
