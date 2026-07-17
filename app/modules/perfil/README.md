# app/modules/perfil/ — Perfil e indicadores derivados (IMC)

Responsável pelos dados de perfil do usuário (altura, data de nascimento,
via `profiles`, e `esta_gestante` via `condicoes_saude`) e pelo primeiro
indicador derivado do produto, o IMC, exposto em `GET /perfil/imc`.
`calculos.py` é função pura (sem I/O, sem conhecimento de idade/gestação);
`service.py` orquestra perfil + pesagem mais recente (consumida via
`app.modules.pesagens.service.obter_pesagem_mais_recente`, nunca acessando
`public.pesagens` direto) + checagem de completude + elegibilidade
(idade < 18, gestante) antes de calcular. O IMC nunca é persistido. Ver
`specs/2026-07-17-calculo-imc.md`.

`PATCH /perfil/condicoes-saude` grava `esta_gestante` (o único campo
gravável por este módulo hoje) via UPSERT em `condicoes_saude` — tabela
sem trigger de auto-criação no signup, diferente de `profiles`. O UPSERT
envia só `user_id`/`esta_gestante`, preservando outros campos já
preenchidos (ex.: `condicoes`, texto livre).
