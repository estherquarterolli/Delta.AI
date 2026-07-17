"""Cálculos puros de indicadores de saúde derivados do perfil.

Funções aqui não fazem I/O, não acessam banco e não conhecem idade,
gestação ou a origem do peso/altura (isso é responsabilidade da camada de
service/router de `app/modules/perfil`) — só a fórmula e a classificação
em si, testáveis isoladamente sem mock.
"""

from __future__ import annotations

from typing import Literal

Classificacao = Literal[
    "abaixo_do_peso",
    "peso_normal",
    "sobrepeso",
    "obesidade_grau_1",
    "obesidade_grau_2",
    "obesidade_grau_3",
]

# Rótulos em pt-BR pra cada classificação, na mesma ordem da tabela OMS do
# spec (`specs/2026-07-17-calculo-imc.md`, seção "Faixas de classificação").
CLASSIFICACAO_LABELS: dict[Classificacao, str] = {
    "abaixo_do_peso": "Abaixo do peso",
    "peso_normal": "Peso normal",
    "sobrepeso": "Sobrepeso",
    "obesidade_grau_1": "Obesidade grau I",
    "obesidade_grau_2": "Obesidade grau II",
    "obesidade_grau_3": "Obesidade grau III",
}

# Faixas OMS ordenadas do maior corte pro menor. Limite inferior de cada
# faixa é inclusivo (>=) — percorrido em ordem decrescente, o primeiro
# corte que o IMC atingir ou superar define a classificação.
_FAIXAS: tuple[tuple[float, Classificacao], ...] = (
    (40.0, "obesidade_grau_3"),
    (35.0, "obesidade_grau_2"),
    (30.0, "obesidade_grau_1"),
    (25.0, "sobrepeso"),
    (18.5, "peso_normal"),
    (0.0, "abaixo_do_peso"),
)


def calcular_imc(peso_kg: float, altura_cm: float) -> tuple[float, Classificacao]:
    """Calcula o IMC (kg/m²) e sua classificação nas 6 faixas padrão da OMS.

    Função pura: sem I/O, sem banco, sem conhecimento de idade/gestação —
    a checagem de elegibilidade é responsabilidade da camada de
    service/router de `app/modules/perfil`, não desta função.

    Retorna `(valor_arredondado_1_decimal, classificacao)`. O cálculo
    interno (`peso_kg / altura_m**2`) não tem arredondamento intermediário
    — só o resultado final é arredondado pra 1 casa decimal.

    Levanta `ValueError` se `peso_kg <= 0` ou `altura_cm <= 0` (não deveria
    acontecer — `CHECK`s do banco já impedem — mas a função defende a si
    mesma contra dado corrompido/inválido).
    """
    if peso_kg <= 0:
        raise ValueError("peso_kg deve ser maior que zero.")
    if altura_cm <= 0:
        raise ValueError("altura_cm deve ser maior que zero.")

    altura_m = altura_cm / 100
    imc = peso_kg / (altura_m**2)
    imc_arredondado = round(imc, 1)

    # Classificação usa o valor já arredondado (o mesmo exposto na API), não
    # o valor bruto de ponto flutuante — evita que ruído de ponto flutuante
    # (ex.: 24.999999999999996 em vez de 25.0 exato) jogue um caso de borda
    # pra faixa errada. Ver critério de aceitação de bordas exatas no spec.
    classificacao = next(
        classificacao for limite, classificacao in _FAIXAS if imc_arredondado >= limite
    )

    return imc_arredondado, classificacao
