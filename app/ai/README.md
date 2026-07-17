# app/ai/ — Wrapper Grok + Anonimizador

Dono: `ai-integration`.

Todo acesso ao Grok (xAI) passa por aqui — nenhum módulo em
`app/modules/` pode chamar a API do Grok diretamente (regra
não-negociável do CLAUDE.md).

Fluxo obrigatório:

1. Módulo de domínio monta o contexto (ex.: histórico do chat).
2. `Anonymizer` remove dado identificável (nome, email, id do banco,
   CPF, telefone, endereço) antes de qualquer chamada externa.
3. `grok_client.py` envia o prompt anonimizado pro Grok e aplica os
   guardrails (sem diagnóstico médico, sem prescrição de dose/medicamento,
   detecção de padrões de TCA → acolher + sugerir profissional).

Cache agressivo (system prompt fixo, contexto compactado) é
obrigatório aqui por causa do limite de custo do MVP free tier, além
do limite duro de 30 msgs/dia por usuário no chat.
