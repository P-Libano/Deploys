"""
Camada 2 — WACC corrente implícito (radar de mercado).

Usa dados ao vivo (yfinance, IPEADATA, Tesouro Nacional) para calcular
o WACC com os parâmetros mais recentes disponíveis. Produz snapshot atual e sinaliza
a direção e magnitude do próximo despacho ANEEL antes de ele ser publicado.

Parâmetros ao vivo (metodologia ANEEL):
    Rf     → NTN-B: média 5 anos de médias diárias rolling 10 anos (compra+venda)
    PRM    → S&P500 vs US10Y: média dos 5 valores anuais acumulados desde 1928
    EMBI   → IPEADATA JPM366_EMBI366 (média 10a YTD)
    Beta   → yfinance: OLS 5a + market cap weighted + Hamada por empresa
    Kd     → bottom-up: média ponderada de taxa_real das debêntures (janela 10a)
             + custo de emissão ponderado; dados ANBIMA live quando disponíveis

Cache local com TTL 1 dia para não sobrecarregar as APIs.

Execução:
    python -m wacc_regulatorio.camada2_corrente
"""
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from wacc_regulatorio.config import T_IRPJ_CSLL, JANELA_ANOS
from wacc_regulatorio.data.fixtures import (
    load_embi_diario,
    load_ntnb,
    load_prm_sp500,
    load_wacc_aplicacao,
    load_debentures,
    load_custo_emissao,
    load_custo_emissao_periodos,
    load_beta_historico,
)
from wacc_regulatorio.data.fetchers import (
    fetch_ntnb_tesouro,
    fetch_embi_ipeadata,
    fetch_beta_prices,
    fetch_market_caps,
    fetch_universo_anbima,
    fetch_prm_sp500tr_incremento,
    fetch_ettj_anbima,
)
from wacc_regulatorio.params.rf import calcular_rf_media_5a
from wacc_regulatorio.params.erp import calcular_prm
from wacc_regulatorio.params.embi import calcular_embi_historico
from wacc_regulatorio.params.beta import (
    BetaResult,
    calcular_beta_from_fixture,
    calcular_beta_from_historico,
    calcular_beta_mktcap_window,
)
from wacc_regulatorio.params.kd import calcular_kd_ettj_atualizado
from wacc_regulatorio.params.estruturais import resolver_dv_wacc_iterativo
from wacc_regulatorio.params.kd_cesta import (
    inferir_cesta_transmissao,
    executar_kd_sensibilidade,
    resolver_overrides,
)
from wacc_regulatorio.wacc_calc import calcular_wacc, WACCResult

warnings.filterwarnings("ignore")


@dataclass
class Camada2Result:
    wacc: WACCResult
    data_referencia: str          # Data dos dados mais recentes usados
    ano_base: int
    delta_vs_publicado: float     # Diferença vs WACC_ai do último despacho (em pp)
    direcao: str                  # "subindo" | "caindo" | "estavel"
    snapshot_params: dict = field(default_factory=dict)
    kd_cenarios: dict = field(default_factory=dict)       # {"base": KdResult, "amplo": ..., "custom": ...}
    kd_cesta_df: object = None                            # pd.DataFrame com coluna 'categoria' (A/B/C/X)

    def __str__(self) -> str:
        sinal = "+" if self.delta_vs_publicado >= 0 else ""
        return (
            f"\n=== WACC Corrente Implícito (Camada 2) ===\n"
            f"  Referência: {self.data_referencia}\n"
            f"  WACC_ai atual:     {self.wacc.wacc_real_antes_impostos:.4%}\n"
            f"  Delta vs despacho: {sinal}{self.delta_vs_publicado:.4%}\n"
            f"  Tendência:         {self.direcao}\n"
            f"  Ke:  {self.wacc.ke_real_di:.4%}  |  "
            f"Kd_ai: {self.wacc.kd_real_ai:.4%}  |  "
            f"E/V: {self.wacc.ev:.1%}\n"
        )


# WACC publicado mais recente (Despacho 675/2026)
WACC_AI_PUBLICADO = 0.121150


def executar_camada2(
    segmento: str = "transmissao",
    T: float = T_IRPJ_CSLL,
    verbose: bool = True,
    overrides: list[str] | None = None,
) -> Camada2Result:
    """
    Calcula o WACC corrente implícito com dados ao vivo.

    Args:
        segmento:  "transmissao"
        T:         Alíquota composita IRPJ + CSLL
        verbose:   Imprime snapshot atual
        overrides: Códigos CETIP ou substrings de empresa adicionados manualmente
                   ao cenário 'custom' do basket inference de Kd.
                   Exemplo: ["TAEE22", "NOVA TRANSMISSORA S.A."]

    Returns:
        Camada2Result com WACCResult, metadados de mercado e cenários Kd.
    """
    ano_atual = datetime.now().year
    if verbose:
        print(f"\n=== Camada 2 — WACC Corrente ({segmento}, {ano_atual}) ===")

    # -----------------------------------------------------------------------
    # Rf: NTN-B ao vivo + histórico → média 5 anos de rolling 10 anos
    # Metodologia: calcular_rf_media_5a(P, ntnb) onde P = ano_atual + 1
    # (P-5 a P-1 = últimos 5 anos com dados; inclui YTD do ano corrente)
    # -----------------------------------------------------------------------
    try:
        ntnb_live = fetch_ntnb_tesouro()
        ntnb_hist = load_ntnb()
        ntnb_all = pd.concat([ntnb_hist, ntnb_live], ignore_index=True).drop_duplicates(
            subset=["data", "vencimento"]
        )
    except Exception:
        ntnb_all = load_ntnb()

    ano_publicacao_corrente = ano_atual + 1
    try:
        rf, rf_detalhes = calcular_rf_media_5a(ano_publicacao_corrente, ntnb_all)
        data_ref = f"{ano_atual}-YTD (5ax10a)"
    except ValueError:
        # Fallback: publicação com P = ano atual (dados até P-1 = ano anterior)
        rf, rf_detalhes = calcular_rf_media_5a(ano_atual, ntnb_all)
        data_ref = f"{ano_atual - 1}-completo (5ax10a)"

    if verbose:
        print(f"  Rf atual:   {rf:.4%}  ({data_ref})")

    # -----------------------------------------------------------------------
    # PRM: S&P500 vs US10Y → média 5 anos de PRM acumulado desde 1928
    # Metodologia: calcular_prm(P, prm_df) onde P = ano_publicacao_corrente
    # Nota: fixture Bloomberg (base ~17.66 em 1928) e yfinance usam escalas diferentes
    # → não fazer merge. Usar fixture até que se normalize a série ao vivo.
    # -----------------------------------------------------------------------
    wacc_apl_df = load_wacc_aplicacao()
    prm_df_base = load_prm_sp500()

    # Estende a série histórica com o ano corrente via ^SP500TR (mesma fórmula, janela ampliada)
    # rf_tbill congelado no último valor da fixture — série Bloomberg/ECB sem equivalente público
    prm_df = fetch_prm_sp500tr_incremento(prm_df_base)
    erp_fonte = "PRM-5ax1928+SP500TR" if len(prm_df) > len(prm_df_base) else "PRM-5ax1928"

    erp_ref_row = wacc_apl_df[wacc_apl_df["segmento"] == segmento].sort_values("ano").iloc[-1]
    erp_fallback = float(erp_ref_row["erp"])
    prm_detalhes: list[tuple[int, float]] = []
    try:
        erp, prm_detalhes = calcular_prm(ano_publicacao_corrente, prm_df)
    except Exception:
        erp = erp_fallback
        erp_fonte = "fixture (fallback)"

    if verbose:
        print(f"  PRM:        {erp:.4%}  [{erp_fonte}]")

    # -----------------------------------------------------------------------
    # EMBI: ao vivo via IPEADATA — janela 10a YTD (inclui ano corrente parcial)
    # -----------------------------------------------------------------------
    try:
        embi_live = fetch_embi_ipeadata()
        if embi_live.empty:
            raise ValueError("EMBI live vazio")
        embi_hist = load_embi_diario()
        embi_all = pd.concat([embi_hist, embi_live], ignore_index=True).drop_duplicates(
            subset=["data"]
        ).sort_values("data")
    except Exception:
        embi_all = load_embi_diario()

    embi = calcular_embi_historico(
        ano_atual,  # janela terminando no ano corrente (inclui YTD)
        embi_df=embi_all,
        janela_anos=JANELA_ANOS,
    )
    if verbose:
        print(f"  EMBI+:      {embi:.4%}  (media {JANELA_ANOS}a YTD)")

    # -----------------------------------------------------------------------
    # Beta, E/V: ao vivo via yfinance (market cap weighted), fallback fixture
    # Janela: 5 anos Oct-Sep mais recente; D/E por empresa via balance sheet.
    # -----------------------------------------------------------------------
    beta_res = None
    beta_fonte = "fixture"

    # Estrutura de capital regulatória brasileira: último despacho publicado.
    # beta_l usa D/E americano (EMBI implícito via re-alavancagem) — E/V e D/V
    # são definidos pelo arcabouço regulatório ANEEL, não pelo mercado americano.
    _ref_cap = wacc_apl_df[wacc_apl_df["segmento"] == segmento].sort_values("ano").iloc[-1]
    ev_reg = float(_ref_cap["ev"])
    dv_reg = float(_ref_cap["dv"])

    # Metodologia ANEEL: média das 5 janelas mais recentes de beta_l_br.
    # C2 estende o fixture com a janela ao vivo (yfinance) como janela mais recente,
    # depois aplica o mesmo AVERAGE(5 janelas) do despacho.
    beta_hist_df = load_beta_historico()
    _beta_janelas = beta_hist_df.tail(5).copy()
    _beta_janelas["fonte"] = "Bloomberg (fixture ANEEL)"

    try:
        prices_live = fetch_beta_prices(
            start=(pd.Timestamp.now() - pd.DateOffset(years=6)).strftime("%Y-%m-%d")
        )
        mktcaps = fetch_market_caps()
        if not prices_live.empty and not mktcaps.empty:
            _spxt_col = next(
                (c for c in prices_live.columns if "SP500TR" in c.upper() or "SPXT" in c.upper()),
                "^SP500TR",
            )
            _beta_live = calcular_beta_mktcap_window(
                prices_live, mktcaps, spxt_col=_spxt_col, T=T
            )
            # Constrói linha sintética para a janela corrente (ano_atual)
            # com D/E regulatório brasileiro (E/V, D/V do último despacho)
            _beta_u_live = _beta_live.beta_u
            _beta_l_br_live = _beta_u_live * (1 + (1 - T) * (dv_reg / ev_reg))
            _row_live = pd.DataFrame([{
                "ano": ano_atual,
                "beta_u_eua": _beta_u_live,
                "dv_brasil": dv_reg,
                "ev_brasil": ev_reg,
                "T_brasil": T,
                "beta_l_brasil": _beta_l_br_live,
            }])
            # Substitui ou acrescenta a janela ao vivo no histórico
            _hist_sem_atual = beta_hist_df[beta_hist_df["ano"] != ano_atual]
            _beta_ext = pd.concat([_hist_sem_atual, _row_live], ignore_index=True).sort_values("ano")
            beta_res = calcular_beta_from_historico(_beta_ext)
            beta_fonte = f"media5a(fixture+live-{ano_atual})"
            # Expõe as 5 janelas usadas na média (tail 5 de _beta_ext)
            _beta_janelas = _beta_ext.tail(5).copy()
            _beta_janelas["fonte"] = [
                "yfinance (live)" if int(r["ano"]) == ano_atual else "Bloomberg (fixture ANEEL)"
                for _, r in _beta_janelas.iterrows()
            ]
    except Exception as _e:
        warnings.warn(f"Beta live falhou: {_e} — usando fixture")

    if beta_res is None:
        # Fallback: média 5a apenas com histórico (sem janela ao vivo)
        beta_res = calcular_beta_from_historico(beta_hist_df)
        _beta_janelas = beta_hist_df.tail(5).copy()
        _beta_janelas["fonte"] = "Bloomberg (fixture ANEEL)"
        beta_fonte = "media5a(fixture)"

    # Garante que E/V e D/V são os regulatórios brasileiros
    beta_res = BetaResult(
        beta_l=beta_res.beta_l,
        beta_u=beta_res.beta_u,
        ev=ev_reg,
        dv=dv_reg,
        beta_u_por_ano=beta_res.beta_u_por_ano,
    )

    if verbose:
        print(f"  Beta_l:     {beta_res.beta_l:.4f}  E/V={beta_res.ev:.1%}  D/V={beta_res.dv:.1%}  [{beta_fonte}]")

    # -----------------------------------------------------------------------
    # Kd: basket inference — cesta de debêntures de transmissão (janela 10 anos)
    # 1. Universo ANBIMA ao vivo (secundário) enriquecido com empresa da fixture
    # 2. inferir_cesta_transmissao() classifica A/B/C/X
    # 3. executar_kd_sensibilidade() calcula 3 cenários: base, amplo, custom
    # C2 usa cenário "base" (A = transmissoras confirmadas) para o WACC.
    # Cenários "amplo" e "custom" ficam em kd_cenarios para UI e auditoria.
    # -----------------------------------------------------------------------
    deb_fixture = load_debentures()
    custo_emissao_df = load_custo_emissao()

    import os
    tem_anbima = bool(
        os.environ.get("ANBIMA_CLIENT_ID") and os.environ.get("ANBIMA_CLIENT_SECRET")
    )

    ano_janela = ano_publicacao_corrente - 1  # último ano com dados completos

    if tem_anbima:
        # Caminho C2 completo: basket inference com universo ANBIMA ao vivo
        universo_anbima = fetch_universo_anbima(fixture_df=deb_fixture, raise_sem_credenciais=True)
        if universo_anbima.empty:
            raise RuntimeError(
                "fetch_universo_anbima() retornou vazio com credenciais presentes. "
                "Verifique conectividade com api.anbima.com.br ou validade das credenciais."
            )

        kd_fonte = "anbima_live"
        janela = (ano_janela - JANELA_ANOS + 1, ano_janela)

        df_cesta = inferir_cesta_transmissao(
            df_universo=universo_anbima,
            df_fixture=deb_fixture,
            overrides=overrides or [],
            janela=janela,
        )

        kd_cenarios = executar_kd_sensibilidade(
            df_cesta=df_cesta,
            custo_emissao_df=custo_emissao_df,
            ano=ano_janela,
            T=T,
        )

        kd_res = kd_cenarios["base"]
        kd_ai = kd_res.kd_real_ai

        if verbose:
            n_A = int((df_cesta["categoria"] == "A").sum())
            n_B = int((df_cesta["categoria"] == "B").sum())
            n_C = int((df_cesta["categoria"] == "C").sum())
            kd_base  = kd_cenarios["base"].kd_real_ai
            kd_amplo = kd_cenarios["amplo"].kd_real_ai
            print(
                f"  Kd_deb:     {kd_res.kd_debentures:.4%}  "
                f"Custo: {kd_res.custo_emissao:.4%}  "
                f"Kd_ai: {kd_ai:.4%}  [{kd_fonte}]"
            )
            print(
                f"  Cesta:      A={n_A} B={n_B} C={n_C}  "
                f"amplo={kd_amplo:.4%} (d{(kd_amplo-kd_base)*10000:+.1f}bp)"
            )

    else:
        # Kd-mid: mesma amostra ANEEL + BEI atualizado via ETTJ ao vivo
        # Não requer credenciais ANBIMA; captura o efeito de mercado nas taxas reais
        ettj_df = fetch_ettj_anbima()
        periodos_df = load_custo_emissao_periodos()   # custo emissão frozen (CVM 160)
        kd_res = calcular_kd_ettj_atualizado(
            ano=ano_janela,
            debentures_df=deb_fixture,
            custo_emissao_df=custo_emissao_df,
            ettj_df=ettj_df,
            segmento=segmento,
            T=T,
            periodos_df=periodos_df,
        )
        kd_fonte = "ettj_atualizado"
        kd_cenarios = {"base": kd_res, "amplo": kd_res, "custom": kd_res}
        df_cesta = None
        kd_ai = kd_res.kd_real_ai

        if verbose:
            print(
                f"  Kd_deb:     {kd_res.kd_debentures:.4%}  "
                f"Custo: {kd_res.custo_emissao:.4%}  "
                f"Kd_ai: {kd_ai:.4%}  [{kd_fonte}]"
            )
            print("  (sem ANBIMA_CLIENT_ID/SECRET — usando Kd-mid via ETTJ ao vivo)")

    # -----------------------------------------------------------------------
    # D/V endógeno via solver regulatório ANEEL
    # Formula AD10: D/V = 3 × (0.0307 + WACC_ai)  — resolve ponto fixo
    # -----------------------------------------------------------------------
    try:
        dv_solver, _ = resolver_dv_wacc_iterativo(
            rf=rf,
            erp=erp,
            beta_u=beta_res.beta_u,
            kd_real_ai=kd_ai,
            T=T,
            dv_inicial=beta_res.dv,
        )
        ev_solver = 1.0 - dv_solver
    except Exception:
        dv_solver = beta_res.dv
        ev_solver = beta_res.ev

    # beta_l re-alavancado com D/V do solver (iteração já inclui isso internamente)
    de_solver = dv_solver / ev_solver if ev_solver > 0 else 0.0
    beta_l_solver = beta_res.beta_u * (1.0 + (1.0 - T) * de_solver)

    if verbose:
        print(
            f"  D/V solver: {dv_solver:.4%}  E/V={ev_solver:.4%}  "
            f"(fixture: D/V={beta_res.dv:.4%}  delta={((dv_solver-beta_res.dv)*10000):+.1f}bp)"
        )

    # -----------------------------------------------------------------------
    # Montagem WACC
    # -----------------------------------------------------------------------
    result = calcular_wacc(
        rf=rf,
        erp=erp,
        embi=embi,
        beta_l=beta_l_solver,
        beta_u=beta_res.beta_u,
        ev=ev_solver,
        dv=dv_solver,
        kd_real_ai=kd_ai,
        T=T,
    )

    delta = result.wacc_real_antes_impostos - WACC_AI_PUBLICADO
    if abs(delta) < 0.0025:
        direcao = "estavel"
    elif delta > 0:
        direcao = "subindo"
    else:
        direcao = "caindo"

    c2 = Camada2Result(
        wacc=result,
        data_referencia=data_ref,
        ano_base=ano_atual,
        delta_vs_publicado=delta,
        direcao=direcao,
        snapshot_params={
            "rf": rf, "rf_detalhes": rf_detalhes,
            "prm": erp, "prm_fonte": erp_fonte, "prm_detalhes": prm_detalhes,
            "embi": embi,
            "beta_l": beta_l_solver, "beta_u": beta_res.beta_u,
            "beta_fonte": beta_fonte,
            "beta_janelas": _beta_janelas.to_dict("records"),
            "ev": ev_solver, "dv": dv_solver,
            "ev_fixture": beta_res.ev, "dv_fixture": beta_res.dv,
            "kd_debentures": kd_res.kd_debentures,
            "kd_custo_emissao": kd_res.custo_emissao,
            "kd_ai": kd_ai,
            "kd_fonte": kd_fonte,
            "kd_n_deb": kd_res.n_debentures,
            "kd_n_A": int((df_cesta["categoria"] == "A").sum()) if df_cesta is not None else None,
            "kd_n_B": int((df_cesta["categoria"] == "B").sum()) if df_cesta is not None else None,
            "kd_n_C": int((df_cesta["categoria"] == "C").sum()) if df_cesta is not None else None,
            "kd_amplo": kd_cenarios["amplo"].kd_real_ai,
            "kd_custom": kd_cenarios["custom"].kd_real_ai,
        },
        kd_cenarios=kd_cenarios,
        kd_cesta_df=df_cesta,
    )

    if verbose:
        print(c2)
        print(f"  Sinal para próximo despacho: WACC {direcao}")
        sinal = "+" if delta >= 0 else ""
        print(f"  Delta vs último publicado: {sinal}{delta:.4%}")

    return c2


if __name__ == "__main__":
    result = executar_camada2()
