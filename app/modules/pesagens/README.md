# app/modules/pesagens/ — Histórico de pesagens

Responsável por registrar, listar, editar e excluir as pesagens (peso +
data/hora) do usuário autenticado em `public.pesagens`, e por expor a
função reutilizável `service.obter_pesagem_mais_recente(user)` — o único
ponto de acesso permitido a esse dado por outros módulos (ex.: cálculo de
IMC em `app/modules/perfil`). Nenhum outro módulo deve importar
`repository.py` diretamente. RLS (`auth.uid() = user_id`) garante que cada
usuário só vê/altera as próprias pesagens; ver
`specs/2026-07-17-registro-de-peso.md`.
