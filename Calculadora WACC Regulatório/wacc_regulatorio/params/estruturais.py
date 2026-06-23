"""
Projecao de parametros estruturais da Camada 3, e solver da estrutura de capital
regulatória ANEEL (D/V endógeno ao WACC).

As politicas daqui so afetam cenarios projetados. A Camada 1 continua usando
os valores oficiais da planilha ANEEL.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Solver D/V ↔ WACC (modelo regulatório ANEEL — aba WACC Histórico)
# ---------------------------------------------------------------------------

# Constantes da planilha ANEEL (aba WACC Histórico, colunas Q/R):
#   Q6: Ativos Operacionais = 100 (normalizado)
#   Q7: Taxa de depreciação regulatória = 0.0307
#   Q9: Indicador regulatório de endividamento: Dívida/EBITDA× = 3
#
# Fórmula AD10 (D/V calculado, aba WACC Histórico):
#   EBITDA = (taxa_deprec + WACC_ai) × Ativos = (0.0307 + WACC_ai) × 100
#   D/V = Indicador × EBITDA / Ativos = 3 × (0.0307 + WACC_ai)
#
# Circularidade: O22 (WACC_ai) depende de O19 (D/V = AD4, colado);
# AD10 (D/V calculado) depende de O22. A ANEEL quebra colando AD10 → AD4.
# Em Python, resolvemos por iteração de ponto fixo.

_TAXA_DEPREC_REG = 0.0307   # taxa de depreciação regulatória (constante)
_IND_DIVIDA_EBITDA = 3.0    # Dívida/EBITDA× (constante)


def _formula_dv_aneel(wacc_ai: float) -> float:
    """D/V = 3 × (0.0307 + WACC_ai)  — fórmula AD10 da aba WACC Histórico."""
    return _IND_DIVIDA_EBITDA * (_TAXA_DEPREC_REG + wacc_ai)


def resolver_dv_wacc_iterativo(
    rf: float,
    erp: float,
    beta_u: float,
    kd_real_ai: float,
    T: float = 0.34,
    dv_inicial: Optional[float] = None,
    tol: float = 1e-8,
    max_iter: int = 200,
) -> tuple[float, float]:
    """
    Resolve a circularidade WACC_ai ↔ D/V do modelo regulatório ANEEL.

    A planilha ANEEL (aba WACC Histórico) computa:
        EBITDA = (taxa_deprec_reg + WACC_ai) × Ativos_normalizados
        D/V    = Dívida/EBITDA × EBITDA / Ativos = 3 × (0.0307 + WACC_ai)

    WACC_ai por sua vez depende de D/V (via beta_l e pesos E/V×D/V).
    A ANEEL quebra a referência circular colando o valor; em Python iteramos.

    Nota: a fórmula D/V = 3 × (0.0307 + WACC_ai) usa os parâmetros do ANO_t
    para determinar D/V_t, que então serve de input para WACC_{t+1}. Para C2,
    usamos os parâmetros de mercado atuais (rf, erp, kd) para projetar o D/V
    implícito de mercado consistente com o WACC corrente.

    Args:
        rf:        Taxa livre de risco (decimal)
        erp:       Equity Risk Premium (decimal)
        beta_u:    Beta desalavancado EUA (decimal)
        kd_real_ai: Custo de dívida real antes de impostos (decimal)
        T:         Alíquota IRPJ+CSLL
        dv_inicial: Chute inicial; None usa o valor fixo ANEEL 2026 (0.3977)
        tol:       Tolerância de convergência |D/V_new - D/V_old|
        max_iter:  Máximo de iterações

    Returns:
        (dv_converged, wacc_ai_converged) — ponto fixo D/V = f(WACC_ai(D/V))
    """
    dv = dv_inicial if dv_inicial is not None else 0.3977

    for _ in range(max_iter):
        ev = 1.0 - dv
        de = dv / ev if ev > 0 else 0.0
        beta_l = beta_u * (1.0 + (1.0 - T) * de)
        ke = rf + beta_l * erp
        kd_di = kd_real_ai * (1.0 - T)
        wacc_ai = (ev * ke + dv * kd_di) / (1.0 - T)
        dv_new = _formula_dv_aneel(wacc_ai)
        dv_new = float(np.clip(dv_new, 0.05, 0.95))   # limites físicos
        if abs(dv_new - dv) < tol:
            return dv_new, wacc_ai
        dv = dv_new

    return dv, wacc_ai


POLITICAS_ESTRUTURAIS = {
    "valor_atual",
    "media_5a",
    "media_10a",
    "regressao_5a",
    "regressao_10a",
}


@dataclass(frozen=True)
class EstruturalAno:
    beta_l: float
    beta_u: float
    erp: float
    ev: float
    dv: float
    fonte_beta: str
    fonte_erp: str
    fonte_estrutura: str


def _validar_politica(politica: str) -> None:
    if politica not in POLITICAS_ESTRUTURAIS:
        opts = ", ".join(sorted(POLITICAS_ESTRUTURAIS))
        raise ValueError(f"Politica estrutural invalida '{politica}'. Use: {opts}")


def _clip_min(value: float, minimum: float = 0.0) -> float:
    if pd.isna(value):
        return minimum
    return float(max(minimum, value))


def _clip_unit(value: float, minimum: float = 0.01, maximum: float = 0.99) -> float:
    if pd.isna(value):
        return 0.5
    return float(min(max(value, minimum), maximum))


def _serie_base(
    coluna: str,
    wacc_historico_df: pd.DataFrame,
    beta_historico_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if coluna == "beta_u" and beta_historico_df is not None:
        df = beta_historico_df[["ano", "beta_u_eua"]].rename(
            columns={"beta_u_eua": "valor"}
        )
    elif coluna == "ev" and beta_historico_df is not None:
        df = beta_historico_df[["ano", "ev_brasil"]].rename(
            columns={"ev_brasil": "valor"}
        )
    else:
        df = wacc_historico_df[["ano", coluna]].rename(columns={coluna: "valor"})

    df = df.dropna(subset=["ano", "valor"]).copy()
    df["ano"] = df["ano"].astype(int)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.dropna(subset=["valor"]).sort_values("ano")


def _valor_projetado(df: pd.DataFrame, ano: int, politica: str) -> float:
    _validar_politica(politica)
    if df.empty:
        raise ValueError("Serie historica vazia para politica estrutural")

    if politica == "valor_atual":
        return float(df.iloc[-1]["valor"])

    janela = 5 if politica.endswith("_5a") else 10
    sub = df.tail(janela)

    if politica.startswith("media_"):
        return float(sub["valor"].mean())

    x = sub["ano"].to_numpy(dtype=float)
    y = sub["valor"].to_numpy(dtype=float)
    if len(sub) < 2 or np.isclose(x.std(), 0.0):
        return float(y[-1])
    slope, intercept = np.polyfit(x, y, 1)
    return float(intercept + slope * ano)


def projetar_parametros_estruturais(
    anos: list[int],
    ref: pd.Series,
    wacc_historico_df: pd.DataFrame,
    beta_historico_df: pd.DataFrame,
    politica_beta: str = "valor_atual",
    politica_erp: str = "valor_atual",
    politica_estrutura: str = "valor_atual",
) -> dict[int, EstruturalAno]:
    """
    Monta parametros estruturais por ano para a Camada 3.

    beta_l usa a serie historica oficial de WACC. beta_u e E/V usam
    beta_historico.csv quando disponivel, pois e a base granular da etapa beta.
    ERP usa wacc_historico.csv.
    """
    for politica in (politica_beta, politica_erp, politica_estrutura):
        _validar_politica(politica)

    ref_beta_l = float(ref["beta_l"])
    ref_beta_u = float(ref.get("beta_u", ref_beta_l))
    ref_erp = float(ref["erp"])
    ref_ev = float(ref["ev"])

    series = {
        "beta_l": _serie_base("beta_l", wacc_historico_df, beta_historico_df),
        "beta_u": _serie_base("beta_u", wacc_historico_df, beta_historico_df),
        "erp": _serie_base("erp", wacc_historico_df, beta_historico_df),
        "ev": _serie_base("ev", wacc_historico_df, beta_historico_df),
    }

    result: dict[int, EstruturalAno] = {}
    for ano in anos:
        if politica_beta == "valor_atual":
            beta_l = ref_beta_l
            beta_u = ref_beta_u
        else:
            beta_l = _valor_projetado(series["beta_l"], ano, politica_beta)
            beta_u = _valor_projetado(series["beta_u"], ano, politica_beta)

        erp = ref_erp if politica_erp == "valor_atual" else _valor_projetado(
            series["erp"], ano, politica_erp
        )
        ev = ref_ev if politica_estrutura == "valor_atual" else _valor_projetado(
            series["ev"], ano, politica_estrutura
        )

        beta_l = _clip_min(beta_l)
        beta_u = _clip_min(beta_u)
        erp = _clip_min(erp)
        ev = _clip_unit(ev)
        dv = 1.0 - ev

        result[ano] = EstruturalAno(
            beta_l=beta_l,
            beta_u=beta_u,
            erp=erp,
            ev=ev,
            dv=dv,
            fonte_beta=politica_beta,
            fonte_erp=politica_erp,
            fonte_estrutura=politica_estrutura,
        )

    return result
