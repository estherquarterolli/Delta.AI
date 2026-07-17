"""Testes unitários de `calcular_imc` — função pura, sem I/O, sem mock.

Cobre (ver `specs/2026-07-17-calculo-imc.md`, seção "Regras de negócio"):
- Bordas exatas de faixa (18.5/25.0/30.0/35.0/40.0 caem na faixa SUPERIOR).
- Um caso representativo de cada uma das 6 faixas OMS.
- Arredondamento pra 1 decimal.
- `ValueError` explícito pra `altura_cm <= 0` e `peso_kg <= 0`.
- Valores extremos fisiologicamente plausíveis pelos CHECKs do banco (altura
  50-250cm, peso 20-400kg) calculam sem erro.
"""

from __future__ import annotations

import pytest

from app.modules.perfil.calculos import calcular_imc

# Com altura_cm = 100 (altura_m = 1.0), imc == peso_kg exatamente — usado
# pra testar as bordas de faixa sem ruído de ponto flutuante na conversão
# de unidade, só o corte de classificação em si.
_ALTURA_CM_NEUTRA = 100.0


class TestBordasDeFaixa:
    """IMC exatamente igual a um corte cai na faixa SUPERIOR (inclusiva)."""

    @pytest.mark.parametrize(
        ("peso_kg", "classificacao_esperada"),
        [
            (18.5, "peso_normal"),
            (25.0, "sobrepeso"),
            (30.0, "obesidade_grau_1"),
            (35.0, "obesidade_grau_2"),
            (40.0, "obesidade_grau_3"),
        ],
    )
    def test_corte_exato_cai_na_faixa_superior(
        self, peso_kg: float, classificacao_esperada: str
    ) -> None:
        imc, classificacao = calcular_imc(peso_kg, _ALTURA_CM_NEUTRA)

        assert imc == peso_kg
        assert classificacao == classificacao_esperada


class TestFaixasRepresentativas:
    """Um valor representativo dentro de cada uma das 6 faixas OMS."""

    @pytest.mark.parametrize(
        ("peso_kg", "classificacao_esperada"),
        [
            (17.0, "abaixo_do_peso"),
            (22.0, "peso_normal"),
            (27.0, "sobrepeso"),
            (32.0, "obesidade_grau_1"),
            (37.0, "obesidade_grau_2"),
            (45.0, "obesidade_grau_3"),
        ],
    )
    def test_valor_dentro_da_faixa(self, peso_kg: float, classificacao_esperada: str) -> None:
        _imc, classificacao = calcular_imc(peso_kg, _ALTURA_CM_NEUTRA)

        assert classificacao == classificacao_esperada


class TestArredondamento:
    def test_arredonda_para_1_casa_decimal(self) -> None:
        # Mesmo exemplo do contrato do endpoint em
        # specs/2026-07-17-calculo-imc.md: peso 70kg, altura 173cm -> 23.4.
        imc, classificacao = calcular_imc(70.0, 173)

        assert imc == 23.4
        assert classificacao == "peso_normal"

    def test_resultado_e_float_com_1_decimal_mesmo_quando_exato(self) -> None:
        imc, _classificacao = calcular_imc(20.0, 100.0)

        assert imc == 20.0
        assert isinstance(imc, float)


class TestValoresInvalidos:
    """Casos pedidos explicitamente no spec: `ValueError` pra dado corrompido
    que não deveria existir (os `CHECK`s do banco já impedem), mas a função
    se defende mesmo assim."""

    def test_altura_cm_zero_levanta_value_error(self) -> None:
        with pytest.raises(ValueError):
            calcular_imc(70.0, 0)

    def test_altura_cm_negativa_levanta_value_error(self) -> None:
        with pytest.raises(ValueError):
            calcular_imc(70.0, -170)

    def test_peso_kg_zero_levanta_value_error(self) -> None:
        with pytest.raises(ValueError):
            calcular_imc(0.0, 170)

    def test_peso_kg_negativo_levanta_value_error(self) -> None:
        with pytest.raises(ValueError):
            calcular_imc(-70.0, 170)


class TestValoresExtremosPlausiveis:
    """Extremos fisiologicamente plausíveis pelos CHECKs do banco (altura
    50-250cm, peso 20-400kg via `profiles`/`pesagens`) calculam sem erro."""

    def test_altura_maxima_peso_maximo(self) -> None:
        imc, classificacao = calcular_imc(400.0, 250)

        assert imc == 64.0
        assert classificacao == "obesidade_grau_3"

    def test_altura_minima_peso_minimo(self) -> None:
        imc, classificacao = calcular_imc(20.0, 50)

        assert imc == 80.0
        assert classificacao == "obesidade_grau_3"
