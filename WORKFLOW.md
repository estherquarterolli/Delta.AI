# Workflow — Como orquestrar os sub-agentes

Este documento é um guia prático de como o Opus deve orquestrar os sub-agentes Sonnet. Também serve pra você (humano) entender o fluxo.

## Como isso funciona no Claude Code

1. Você abre o Claude Code no diretório do projeto com Opus como modelo principal:
   ```bash
   claude --model opus
   ```
2. Claude Code lê `CLAUDE.md` como contexto persistente.
3. Sub-agentes ficam em `.claude/agents/*.md` — carregados no início da sessão.
4. Opus decide quando delegar (baseado na descrição de cada sub-agente) ou você invoca explicitamente:
   ```
   > Use the backend-engineer subagent to implement /nutricao/refeicoes
   ```
5. Sub-agentes recebem só o próprio system prompt (não o CLAUDE.md inteiro), então o system prompt deles é auto-suficiente.

> **Gotcha comum**: sub-agentes definidos em arquivo são carregados no início da sessão. Se você editar o `.md` de um agente, **precisa reiniciar** o Claude Code pra pegar. Alternativa: usar o comando `/agents` dentro do Claude Code pra editar interativamente (aplica na hora).

## Fluxo padrão de feature

### 1. Discovery (Opus + product-spec)

Você: "quero adicionar cálculo de calorias queimadas por treino"

Opus:
- Verifica se já existe spec relacionado (`Grep` em `specs/`)
- Delega pro `product-spec` com o pedido bruto
- `product-spec` cria `specs/2026-07-16-calorias-queimadas.md` com status DRAFT
- Faz até 3 perguntas se ambíguo

Você responde as perguntas, spec vira `READY_FOR_ARCH`.

### 2. Arquitetura de dados (supabase-architect)

Se o spec toca dado novo:
- Opus delega pro `supabase-architect`
- Ele lê o spec, desenha tabela, escreve migration + RLS
- Atualiza `docs/erd.md`
- Marca spec como `READY_FOR_BUILD`

Se não toca dado, pula direto pra próxima etapa.

### 3. Implementação paralela (backend + frontend)

Opus delega **em paralelo** (Claude Code suporta chamadas paralelas):
- `backend-engineer` → módulo `app/modules/treinos/` com nova rota
- `frontend-engineer` → tela em `web/src/app/(app)/treinos/`

Se envolve chat/prompt: `ai-integration` também em paralelo.

### 4. Testes (test-engineer)

Depois que backend + frontend reportam pronto:
- Opus delega pro `test-engineer`
- Ele escreve testes cobrindo o novo caminho
- Roda a suíte inteira, reporta cobertura

Se falha: retorna pro engineer responsável, itera.

### 5. Auditoria (security-reviewer) — obrigatório em dado sensível

Se a feature tocou dado sensível, foto, chat IA, autenticação ou secrets:
- Opus delega pro `security-reviewer`
- Ele NÃO escreve código, só audita
- Gera relatório em `docs/security/`
- Se ❌: bloqueia. Volta pro engineer com problema.

### 6. Deploy (devops-engineer)

Se a feature exige nova var, novo serviço externo, ou mudança de deploy:
- Opus delega pro `devops-engineer`
- Ele atualiza CI, Dockerfile, docs de env, análise de custo

### 7. Merge

Opus revisa: spec DONE, testes passando, security ok, deploy configurado → aprova merge.

## Fluxo de bug fix

1. Você reporta bug
2. Opus faz diagnóstico (usa `Read`, `Grep`, `Bash` pra reproduzir)
3. Delega pro engineer do módulo afetado
4. `test-engineer` escreve teste de regressão ANTES do fix
5. Engineer resolve
6. `test-engineer` confirma teste passa
7. Se tocou dado sensível: `security-reviewer` audita
8. Merge

## Fluxo de mudança arquitetural

Toda decisão arquitetural (troca de provedor, mudança de padrão) vira ADR:

1. Você ou Opus propõe
2. Opus escreve draft do ADR em `docs/adr/YYYY-MM-DD-titulo.md`
3. Você aprova / pede mudança
4. Sub-agentes relevantes implementam mudança em fases
5. ADR marcado como ACCEPTED

## Padrões de invocação explícita

Quando você quer forçar uso de um sub-agente específico:

```
Use the supabase-architect subagent para adicionar tabela de feedback do chat.
```

```
Delegate to test-engineer: writing regression test for issue #42.
```

```
Have security-reviewer audit the last commit for LGPD compliance.
```

## Quando NÃO delegar

Opus deve fazer sozinho (sem delegar) quando:
- Pergunta é de contexto/orientação (não código)
- Refactoring pequeno em 1 arquivo
- Update de docs
- Debug de 5 min que já sabe onde tá o problema
- Explicação de código existente

## Anti-padrões (evitar)

- ❌ Delegar tudo sem analisar (aumenta latência sem ganho)
- ❌ Opus escrevendo código de módulo que tem engineer especializado
- ❌ Sub-agente chamando outro sub-agente sem passar pelo Opus (perde visibilidade)
- ❌ Pular `test-engineer` pra "ganhar tempo" (você paga com bug depois)
- ❌ Pular `security-reviewer` em dado sensível (você paga em multa da ANPD)

## Custos e otimização

Cada delegação = nova chamada de modelo. Sonnet é ~5x mais barato que Opus, mas ainda custa. Otimizações:

- Sub-agente com contexto reduzido (só o system prompt) = tokens muito menores
- Delegações em paralelo quando independentes (backend + frontend)
- `security-reviewer` é read-only → cabe em Sonnet baixo custo
- `product-spec` no início economiza retrabalho depois
