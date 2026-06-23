"""
Validação das mecânicas da projeção ETTJ BEI.

Cobre três níveis:
  1. Identidade matemática — forwards decompostos reconstroem os spots originais
  2. Coerência de conversão — mensal composta fecha na taxa anual
  3. Comportamento da projeção — transição de vértices e cobertura total

Executar: pytest tests/test_ettj_mechanics.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import pytest

from engine.projector import (
    _bei_forward_intervals,
    _forward_for_du,
    build_ettj_projection,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def bei_monotone():
    """Curva BEI crescente simples — fácil de raciocinar sobre os forwards."""
    return pd.DataFrame({
        "vertice_du": [126, 252, 504, 756, 1260],
        "bei_pct":    [4.0, 5.0, 5.5, 5.8,  6.0],
    })


@pytest.fixture
def bei_invertida():
    """Curva BEI invertida (curva de inflação esperada declinante)."""
    return pd.DataFrame({
        "vertice_du": [126, 252, 504, 756],
        "bei_pct":    [6.0, 5.5, 5.0, 4.5],
    })


@pytest.fixture
def bei_plana():
    """Curva BEI completamente plana — forward deve ser igual ao spot em todos os vértices."""
    return pd.DataFrame({
        "vertice_du": [126, 252, 504, 756],
        "bei_pct":    [5.0, 5.0, 5.0, 5.0],
    })


@pytest.fixture
def realized_recente():
    """Série realizada de 12 meses terminando no mês anterior ao atual."""
    today = pd.Period(pd.Timestamp.today(), freq="M")
    idx = pd.period_range(end=today - 1, periods=12, freq="M")
    return pd.Series(0.42, index=idx, dtype=float)


# ─── 1. Identidade matemática: forwards → spots ───────────────────────────────

class TestForwardReconstrucaoSpot:
    """
    Propriedade central: o acúmulo dos forwards deve reproduzir os spots originais.

    Para cada vértice v_n com spot s_n e anos_n anos:
        ∏_i (1 + fwd_i/100)^Δt_i = (1 + s_n/100)^anos_n

    Esta é uma identidade aritmética: se falhar, há bug no bootstrap.
    """

    def _reconstruir_spots(self, bei_df):
        """Retorna lista de (du, spot_original, spot_reconstruido)."""
        intervals = _bei_forward_intervals(bei_df)
        rows = bei_df.sort_values("vertice_du").reset_index(drop=True)

        fator_acum = 1.0
        anos_prev = 0.0
        resultado = []

        for i, row in rows.iterrows():
            du   = float(row["vertice_du"])
            spot = float(row["bei_pct"])
            anos = du / 252

            # Ponto médio do segmento que termina neste vértice
            lo = float(rows.loc[i - 1, "vertice_du"]) if i > 0 else 0.0
            du_mid = (lo + du) / 2
            fwd = _forward_for_du(intervals, du_mid)

            delta = anos - anos_prev
            fator_acum *= (1 + fwd / 100) ** delta
            spot_rec = (fator_acum ** (1 / anos) - 1) * 100

            resultado.append((du, spot, spot_rec))
            anos_prev = anos

        return resultado

    def test_curva_crescente(self, bei_monotone):
        for du, spot, rec in self._reconstruir_spots(bei_monotone):
            assert abs(rec - spot) < 1e-8, \
                f"du={du}: spot={spot}% reconstruído={rec:.10f}%"

    def test_curva_invertida(self, bei_invertida):
        for du, spot, rec in self._reconstruir_spots(bei_invertida):
            assert abs(rec - spot) < 1e-8, \
                f"du={du}: spot={spot}% reconstruído={rec:.10f}%"

    def test_curva_plana(self, bei_plana):
        """Curva plana: todos os forwards devem ser iguais ao spot."""
        intervals = _bei_forward_intervals(bei_plana)
        for lo, hi, fwd in intervals[:-1]:  # ignora segmento de extrapolação
            assert abs(fwd - 5.0) < 1e-8, \
                f"Segmento ({lo}→{hi}): forward={fwd:.10f}%, esperado=5.0%"

    def test_primeiro_segmento_forward_igual_spot(self, bei_monotone):
        """Segmento 0→v1 não tem prior, logo forward = spot do primeiro vértice."""
        intervals = _bei_forward_intervals(bei_monotone)
        spot_v1 = float(bei_monotone.iloc[0]["bei_pct"])
        fwd = _forward_for_du(intervals, 63.0)  # ponto interno ao 1º segmento
        assert abs(fwd - spot_v1) < 1e-10, \
            f"1º segmento: forward={fwd}%, spot_v1={spot_v1}%"

    def test_ultimo_segmento_extrapola_ultimo_forward(self, bei_monotone):
        """Além do último vértice, a taxa deve ser o último forward calculado."""
        intervals = _bei_forward_intervals(bei_monotone)
        penultimo_forward = intervals[-2][2]  # último segmento real (não extrapolação)
        fwd_alem = _forward_for_du(intervals, 9999.0)
        assert abs(fwd_alem - penultimo_forward) < 1e-10


# ─── 2. Coerência de conversão anual ↔ mensal ─────────────────────────────────

class TestConversaoAnualMensal:

    @pytest.mark.parametrize("annual_pct", [2.0, 4.88, 5.49, 6.0, 10.0, 14.5])
    def test_12_mensais_fecham_anual(self, annual_pct):
        """(1 + mensal)^12 deve reconstituir exatamente a taxa anual."""
        monthly = (1 + annual_pct / 100) ** (1 / 12) - 1
        reconstructed = ((1 + monthly) ** 12 - 1) * 100
        assert abs(reconstructed - annual_pct) < 1e-10, \
            f"annual={annual_pct}% → monthly={monthly:.8f} → rec={reconstructed:.10f}%"

    def test_taxa_mensal_positiva_para_forward_positivo(self, bei_monotone):
        """Se BEI > 0 em todos os vértices, todas as taxas mensais devem ser positivas."""
        intervals = _bei_forward_intervals(bei_monotone)
        for lo, hi, fwd in intervals:
            monthly = (1 + fwd / 100) ** (1 / 12) - 1
            assert monthly > 0, f"Taxa mensal negativa para fwd={fwd}% no segmento {lo}→{hi}"


# ─── 3. Comportamento da projeção ────────────────────────────────────────────

class TestProjecaoETTJ:

    def test_retorna_realized_only_se_dentro_do_realizado(self, bei_monotone, realized_recente):
        """Se target <= last_realized, não deve haver projeção."""
        last_real = realized_recente.index.max()
        unified, lr, fonte = build_ettj_projection(realized_recente, bei_monotone, last_real)
        assert fonte == "realized only"
        assert len(unified) == len(realized_recente)

    def test_serie_sem_gaps(self, bei_monotone, realized_recente):
        """Projeção de 24 meses deve gerar série contínua sem NaN."""
        today = pd.Period(pd.Timestamp.today(), freq="M")
        unified, last_real, fonte = build_ettj_projection(
            realized_recente, bei_monotone, today + 24
        )
        proj = unified[unified.index > last_real]
        assert not proj.isna().any(), "Série projetada contém NaN"
        assert fonte == "ETTJ BEI"

    def test_transicao_no_sexto_mes(self, bei_monotone, realized_recente):
        """
        Com âncora no primeiro mês projetado (du = mês * 21):
          meses 1-5: du 21-105 → intervalo (0, 126) → mesma taxa
          mês 6:     du 126    → intervalo (126, 252) → taxa diferente
        """
        today = pd.Period(pd.Timestamp.today(), freq="M")
        unified, last_real, _ = build_ettj_projection(
            realized_recente, bei_monotone, today + 12
        )
        proj = unified[unified.index > last_real]

        taxa_mes1 = float(proj.iloc[0])
        taxa_mes5 = float(proj.iloc[4])
        taxa_mes6 = float(proj.iloc[5])

        # Meses 1–5: mesma taxa (primeiro vértice)
        assert abs(taxa_mes1 - taxa_mes5) < 1e-10, \
            f"Meses 1-5 deveriam ter mesma taxa: {taxa_mes1:.6f} ≠ {taxa_mes5:.6f}"

        # Mês 6: taxa diferente (segundo vértice, forward mais alto)
        assert abs(taxa_mes6 - taxa_mes1) > 1e-6, \
            f"Mês 6 deveria ter taxa diferente: {taxa_mes6:.6f} == {taxa_mes1:.6f}"

    def test_curva_plana_gera_taxa_uniforme(self, bei_plana, realized_recente):
        """BEI plano → todos os meses projetados com taxa mensal idêntica."""
        today = pd.Period(pd.Timestamp.today(), freq="M")
        unified, last_real, _ = build_ettj_projection(
            realized_recente, bei_plana, today + 24
        )
        proj = unified[unified.index > last_real]
        assert np.allclose(proj.values, proj.iloc[0], atol=1e-10), \
            "Curva BEI plana deveria gerar taxa mensal uniforme"

    def test_todos_os_meses_taxa_positiva(self, bei_monotone, realized_recente):
        """Com BEI positivo, todas as taxas mensais projetadas devem ser > 0."""
        today = pd.Period(pd.Timestamp.today(), freq="M")
        unified, last_real, _ = build_ettj_projection(
            realized_recente, bei_monotone, today + 36
        )
        proj = unified[unified.index > last_real]
        assert (proj > 0).all(), f"Taxa ≤ 0 encontrada: {proj[proj <= 0]}"

    def test_lookup_sem_gaps_de_cobertura(self, bei_monotone):
        """_forward_for_du deve retornar um float válido para qualquer du >= 0."""
        intervals = _bei_forward_intervals(bei_monotone)
        last_du = float(bei_monotone["vertice_du"].max())

        for du in [0, 1, 63, 126, 252, 500, last_du, last_du * 2, 99999]:
            fwd = _forward_for_du(intervals, du)
            assert isinstance(fwd, float) and not np.isnan(fwd) and fwd > 0, \
                f"forward inválido para du={du}: {fwd}"


# ─── 4. Sanidade com dados reais ANBIMA (requer conexão) ─────────────────────

@pytest.mark.integration
class TestForwardRealANBIMA:

    @pytest.fixture
    def bei_real(self):
        from collectors.anbima_ettj import fetch_ettj
        df, _ = fetch_ettj()
        return df.dropna(subset=["bei_pct"]).sort_values("vertice_du").reset_index(drop=True)

    def test_reconstituicao_spots_reais(self, bei_real):
        """Com dados reais, erro de reconstrução deve ser < 0,001 p.p. (< 0,1 bp)."""
        intervals = _bei_forward_intervals(bei_real)
        rows = bei_real.reset_index(drop=True)

        fator_acum = 1.0
        anos_prev = 0.0
        erros = []

        for i, row in rows.iterrows():
            du   = float(row["vertice_du"])
            spot = float(row["bei_pct"])
            anos = du / 252
            lo   = float(rows.loc[i - 1, "vertice_du"]) if i > 0 else 0.0
            fwd  = _forward_for_du(intervals, (lo + du) / 2)
            fator_acum *= (1 + fwd / 100) ** (anos - anos_prev)
            spot_rec = (fator_acum ** (1 / anos) - 1) * 100
            erros.append(abs(spot_rec - spot))
            anos_prev = anos

        max_erro = max(erros)
        assert max_erro < 0.001, \
            f"Erro máximo de reconstrução = {max_erro:.8f} p.p. (limite: 0,001 p.p.)"

    def test_forwards_positivos_dados_reais(self, bei_real):
        """Com BEI real positivo, nenhum forward deve ser negativo."""
        intervals = _bei_forward_intervals(bei_real)
        negativos = [(lo, hi, fwd) for lo, hi, fwd in intervals if fwd < 0]
        assert not negativos, f"Forwards negativos encontrados: {negativos}"

    def test_projecao_24_meses_sem_nan(self, bei_real, realized_recente):
        """Projeção completa de 24 meses com dados reais não deve conter NaN."""
        today = pd.Period(pd.Timestamp.today(), freq="M")
        unified, last_real, fonte = build_ettj_projection(
            realized_recente, bei_real, today + 24
        )
        proj = unified[unified.index > last_real]
        assert not proj.isna().any()
        assert fonte == "ETTJ BEI"
