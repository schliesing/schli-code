# CLAUDE.md — repositório do Governor

Este repositório contém o **Governor**, o agente governante do VPS: ele
descobre, monitora, corrige, higieniza e reporta todos os projetos do
servidor via bot Telegram Orion. O Governor faz parte do ecossistema de
mudanças, aprendizados e melhorias — toda sessão do Claude que trabalhar
aqui deve tratá-lo como infraestrutura de produção.

## Invariantes (não quebre)

1. **Stdlib apenas.** Nenhuma dependência externa (pip). Compatível com
   Python 3.8+ — nada de `match`, `tomllib` ou sintaxe 3.10+.
2. **Observe-only até confirmação.** Projeto sem charter `confirmed` nunca
   sofre ação de healing — apenas relatório. Isso está em
   `healing.Healer.can_heal`; qualquer nova ação precisa respeitar isso.
3. **Nada é deletado diretamente.** Limpeza segue o funil: achado → proposta
   pendente → aprovação humana → quarentena → purga só após retenção.
4. **Estado sempre atômico.** Escreva estado com `util.atomic_write_json`
   (tmp + rename + .bak). Leituras usam `util.read_json`, que recupera do
   `.bak` em corrupção.
5. **Nenhuma exceção pode derrubar o daemon.** Todo código chamado pelo loop
   roda dentro de `selfcare.Bulkhead`. Erros vão para o self-journal — é
   assim que o Governor aprende sobre os próprios defeitos.
6. **Mensagens ao usuário em PT-BR**, identificadores de código em inglês.

## Como estender

- **Nova checagem de saúde**: adicione uma função em `monitor.py` que
  devolve `CheckResult` e chame-a em `project_checks`/`system_checks`.
  Prefixo do `check` (antes do `:`) decide o playbook em `healing.py`.
- **Nova ação de correção**: adicione em `healing.DEFAULT_ACTIONS[prefixo]`.
  A ação será automaticamente ranqueada/quarentenada pelo learning.
- **Playbook específico de um projeto** (no VPS): crie
  `/var/lib/governor/playbooks/<id>.json` com `{"prefixo": [["cmd", ...]]}`.
- **Novo comando Telegram/CLI**: registre em `daemon._register_commands`
  (com alias PT e EN) e/ou em `cli.py`.

## Teste obrigatório

Depois de qualquer mudança:

```bash
python3 -m governor selftest
```

O selftest é o **gate do auto-update**: no VPS, `governorctl self-update`
só adota uma versão nova se o selftest dela passar (senão faz rollback).
Portanto, se você adicionar um subsistema, adicione checagens dele ao
`selftest.py` — é isso que protege a produção de nós mesmos.

## Convenções de mudança

- Ao alterar comportamento visível (mensagens, comandos, regras), atualize
  `README.md` e, se afetar projetos governados, `docs/CLAUDE-SNIPPET.md`.
- Mudanças no formato de estado (charters, proposals, learning) precisam
  ler o formato antigo sem quebrar (migração suave ou defaults).
- O snippet `docs/CLAUDE-SNIPPET.md` é colado no CLAUDE.md dos projetos do
  VPS — mantenha-o curto e correto.
