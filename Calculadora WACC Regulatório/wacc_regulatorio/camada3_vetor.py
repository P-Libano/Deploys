"""
Camada 3 — Vetor projetado de WACC (horizonte até 30 anos).

Recalcula o WACC completo para cada ano t do horizonte:
    - Parâmetros com curva forward (Rf): extraídos da curva ETTJ ANBIMA
    - Parâmetros estruturais (ERP, Beta, E/V): congelados no último valor calibrado
    - Parâmetros de cenário (EMBI): cenário base + embi_delta opcional
    - Kd: projetado via regressão Kd ~ f(Rf, EMBI)

Output: pd.DataFrame com PeriodIndex(freq='A') compatível com solver BRR × WACC_t.

Execução:
    python -m wacc_regulatorio.camada3_vetor
"""
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from wacc_regulatorio.config import T_IRPJ_CSLL, KD_REGRESSAO_JSON
from wacc_regulatorio.data.fetchers import fetch_ettj_anbima
from wacc_regulatorio.data.fixtures import (
    load_wacc_aplicacao,
    load_embi_medias,
    load_embi_diario,
    load_wacc_historico,
    load_ntnb,
)
from wacc_regulatorio.params.rf import (
    calcular_rf_forward,
    build_ettj_from_ntnb_fixture,
    calcular_rf_spot_serie,
    calcular_rf_rolling_projetado,
    calcular_rf_media_5a,
)
from wacc_regulatorio.params.erp import calcular_prm
from wacc_regulatorio.data.fixtures import load_prm_sp500
from wacc_regulatorio.params.embi import calcular_embi_projetado, calcular_embi_historico
from wacc_regulatorio.params.kd import kd_projetado, calibrar_regressao_kd, carregar_coeficientes_kd
from wacc_regulatorio.wacc_calc import calcular_wacc

warnings.filterwarnings("ignore")


def projetar_vetor_wacc(
    horizonte_anos: int = 30,
    ano_base: int = 2026,
    segmento: str = "transmissao",
    modo: str = "base",
    embi_delta: Optional[dict] = None,
    kd_spec: str = "simples",
    beta_override: Optional[dict] = None,
    rf_spot_projetado: Optional[float] = None,
    T: float = T_IRPJ_CSLL,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Projeta o vetor anual de WACC para até 30 anos.

    Args:
        horizonte_anos: Número de anos do horizonte (padrão 30)
        ano_base: Ano de partida da projeção (padrão 2026)
        segmento: "transmissao"
        modo: "base" = parâmetros congelados no último despacho publicado;
              "cenario" = Rf e PRM atualizados com dados mais recentes disponíveis
              (mesmo output que C2 como ponto de partida da curva)
        embi_delta: Sensibilização EMBI por ano: {ano: delta_decimal}
                    Ex: {2027: +0.015, 2028: +0.008}
        kd_spec: "simples" (Kd~Rf) ou "embi" (Kd~Rf+EMBI)
        beta_override: Override manual de beta_l por ano: {ano: beta_l}
        rf_spot_projetado: Nível de Rf projetado para anos futuros (sobrescreve ETTJ)
        T: Alíquota composita IRPJ + CSLL
        verbose: Imprime log do vetor

    Returns:
        DataFrame com index pd.PeriodIndex(freq='A') e colunas:
            Ano, Rf, ERP, EMBI, Beta_l, Beta_u, E/V, D/V,
            Ke_real_di, Kd_real_ai, Kd_real_di,
            WACC_depois_impostos, WACC_antes_impostos, fonte_rf, modo
    """
    if modo not in ("base", "cenario"):
        raise ValueError(f"modo deve ser 'base' ou 'cenario', recebido: '{modo}'")

    # -----------------------------------------------------------------------
    # Parâmetros estruturais: congelados do último despacho publicado (ano_base)
    # -----------------------------------------------------------------------
    wacc_apl_df = load_wacc_aplicacao()
    ref = wacc_apl_df[
        (wacc_apl_df["ano"] == ano_base) &
        (wacc_apl_df["segmento"] == segmento)
    ]
    if ref.empty:
        # Usa o mais recente disponível
        ref = wacc_apl_df[wacc_apl_df["segmento"] == segmento].sort_values("ano").iloc[[-1]]

    r = ref.iloc[0]
    beta_l_base = float(r["beta_l"])
    beta_u_base = float(r.get("beta_u", beta_l_base))  # fallback
    ev_base   = float(r["ev"])
    dv_base   = float(r["dv"])

    # ERP/PRM: publicado (base) ou calculado com dados mais recentes (cenario)
    if modo == "base":
        erp_base = float(r["erp"])
        _modo_label = "base (publicado)"
    else:
        # Cenário: PRM com dados atualizados (mesma janela 5 anos acumulados)
        ntnb_df_c3 = load_ntnb()
        prm_df_c3 = load_prm_sp500()
        ano_pub_corrente = ano_base + 1
        try:
            erp_base, _ = calcular_prm(ano_pub_corrente, prm_df_c3)
        except Exception:
            erp_base = float(r["erp"])
        _modo_label = "cenario (dados atualizados)"

    # -----------------------------------------------------------------------
    # EMBI base: último valor da janela 10 anos
    # -----------------------------------------------------------------------
    try:
        embi_medias_df = load_embi_medias()
        embi_diario_df = load_embi_diario()
        embi_base = calcular_embi_historico(
            ano_base - 1,
            embi_df=embi_diario_df,
            embi_medias_df=embi_medias_df,
        )
    except Exception:
        embi_base = 0.02765  # fallback para valor do Despacho 675/2026

    # -----------------------------------------------------------------------
    # Rf rolling: série histórica + nível projetado para anos futuros
    # Nota: NTN-B com vencimentos futuros como Rf é uma heurística do custo
    # de capital corrente, não uma previsão do Rf futuro. Yields de longo prazo
    # precificam o mercado hoje; o Rf realizado pode divergir substancialmente.
    # -----------------------------------------------------------------------
    if "ntnb_df_c3" not in dir():
        ntnb_df_c3 = load_ntnb()

    # Para Rf rolling: base usa rf_spot (1 ano/janela legado) para compatibilidade com
    # calcular_rf_rolling_projetado; cenário usa mesma série mas com spot mais recente.
    rf_spot_historico = calcular_rf_spot_serie(
        ntnb_df_c3, ano_inicio=ano_base - 15, ano_fim=ano_base - 1
    )

    # Nível projetado para anos futuros: parâmetro explícito, ETTJ, ou Rf publicado
    if rf_spot_projetado is not None:
        _rf_proj = rf_spot_projetado
        _fonte_proj = "cenario"
    elif modo == "cenario":
        # Cenário: usa Rf 5ax10a mais recente como nível de projeção
        try:
            _rf_proj, _ = calcular_rf_media_5a(ano_base + 1, ntnb_df_c3)
            _fonte_proj = "rf_5ax10a_corrente"
        except Exception:
            _rf_proj = float(r["rf"])
            _fonte_proj = "rf_publicado_fallback"
    else:
        # Base: tenta ETTJ, senão Rf publicado
        ettj_df = pd.DataFrame()
        try:
            ettj_df = fetch_ettj_anbima()
            if ettj_df.empty or ettj_df["yield_real"].std() < 0.0001:
                raise ValueError("curva plana")
        except Exception:
            try:
                ettj_df = build_ettj_from_ntnb_fixture(
                    ntnb_df_c3, ano_ref=ano_base - 1, ano_base=ano_base
                )
            except Exception:
                pass
        if not ettj_df.empty:
            _rf_proj = float(ettj_df["yield_real"].mean())
        else:
            _rf_proj = float(r["rf"])
        _fonte_proj = "ettj_media"

    if verbose:
        print(f"\n=== Camada 3 — Vetor WACC {segmento} ({ano_base}–{ano_base+horizonte_anos-1}) [{_modo_label}] ===")
        print(f"  Rf rolling 10a: historico {min(rf_spot_historico)}-{max(rf_spot_historico)} | projetado={_rf_proj:.4%} ({_fonte_proj})")
        print(f"  ERP={erp_base:.4%}  Beta_l={beta_l_base:.4f}  E/V={ev_base:.1%}")
        print(f"  EMBI base: {embi_base:.4%}  |  Kd spec: {kd_spec}")
        print()

    # -----------------------------------------------------------------------
    # Coeficientes Kd
    # -----------------------------------------------------------------------
    if not KD_REGRESSAO_JSON.exists():
        if verbose:
            print("  Calibrando regressao Kd para Camada 3...")
        wacc_hist_df = load_wacc_historico()
        calibrar_regressao_kd(wacc_hist_df, KD_REGRESSAO_JSON)
    coef_kd = carregar_coeficientes_kd(KD_REGRESSAO_JSON)

    # -----------------------------------------------------------------------
    # Loop de projeção
    # -----------------------------------------------------------------------
    rows = []
    fontes_extrapol = []

    for t in range(horizonte_anos):
        ano = ano_base + t

        # Rf rolling: média dos últimos 10 anos de rf_spot,
        # com anos futuros substituídos por _rf_proj
        rf_t, fonte_rf = calcular_rf_rolling_projetado(
            ano_publicacao=ano,
            rf_spot_historico=rf_spot_historico,
            rf_spot_projetado=_rf_proj,
            janela=10,
        )

        if fonte_rf != "ettj":
            fontes_extrapol.append(ano)

        # EMBI projetado
        embi_t = calcular_embi_projetado(ano_base, t, embi_base, embi_delta)

        # Beta (congelado ou override)
        beta_l_t = (beta_override or {}).get(ano, beta_l_base)

        # Kd projetado via regressão
        kd_ai_t = kd_projetado(rf_t, embi_t, coef_kd, spec=kd_spec)
        # Garante Kd razoável (entre 2% e 20%)
        kd_ai_t = max(0.02, min(0.20, kd_ai_t))

        wacc = calcular_wacc(
            rf=rf_t,
            erp=erp_base,
            embi=embi_t,
            beta_l=beta_l_t,
            beta_u=beta_u_base,
            ev=ev_base,
            dv=dv_base,
            kd_real_ai=kd_ai_t,
            T=T,
        )

        rows.append({
            "Ano": ano,
            "Rf": wacc.rf,
            "ERP": wacc.erp,
            "EMBI": wacc.embi,
            "Beta_l": wacc.beta_l,
            "Beta_u": wacc.beta_u,
            "EV": wacc.ev,
            "DV": wacc.dv,
            "Ke_real_di": wacc.ke_real_di,
            "Kd_real_ai": wacc.kd_real_ai,
            "Kd_real_di": wacc.kd_real_di,
            "WACC_depois_impostos": wacc.wacc_real_depois_impostos,
            "WACC_antes_impostos": wacc.wacc_real_antes_impostos,
            "fonte_rf": fonte_rf,
            "modo": modo,
        })

    df = pd.DataFrame(rows)
    df.index = pd.PeriodIndex(df["Ano"], freq="Y")
    df = df.drop(columns=["Ano"])

    # Aviso sobre extrapolação
    if fontes_extrapol and verbose:
        print(
            f"  AVISO: {len(fontes_extrapol)} ano(s) com Rf extrapolado "
            f"(fonte_rf != 'ettj'): {fontes_extrapol[:5]}{'...' if len(fontes_extrapol) > 5 else ''}"
        )

    if verbose:
        print(df[["Rf", "EMBI", "Kd_real_ai", "WACC_antes_impostos", "fonte_rf"]].to_string())

    return df


if __name__ == "__main__":
    print("--- CURVA BASE (último despacho publicado) ---")
    df_base = projetar_vetor_wacc(horizonte_anos=30, modo="base")
    print("\nPrimeiros 10 anos (base):")
    print(df_base[["WACC_antes_impostos", "Rf", "ERP", "Kd_real_ai", "fonte_rf"]].head(10).to_string())

    print("\n--- CURVA CENÁRIO (dados mais recentes) ---")
    df_cen = projetar_vetor_wacc(horizonte_anos=30, modo="cenario")
    print("\nPrimeiros 10 anos (cenario):")
    print(df_cen[["WACC_antes_impostos", "Rf", "ERP", "Kd_real_ai", "fonte_rf"]].head(10).to_string())

    print("\n--- COMPARAÇÃO BASE vs CENÁRIO (WACC_ai, delta em bp) ---")
    delta = (df_cen["WACC_antes_impostos"] - df_base["WACC_antes_impostos"]) * 10000
    print(delta.head(10).apply(lambda x: f"{x:+.1f}bp").to_string())
