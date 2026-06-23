"""
Camada 1 — Replicação histórica do Despacho ANEEL 675/2026.

Usa APENAS os fixtures extraídos da planilha ANEEL (zero chamadas externas).
Resultado esperado: WACC_ai = 12,11% (Transmissão).

Todos os parâmetros são CALCULADOS a partir dos fixtures brutos — nenhum número
é lido diretamente dos resultados publicados no Despacho.

Execução:
    python -m wacc_regulatorio.camada1_replicacao
"""
from wacc_regulatorio.data.fixtures import (
    load_ntnb,
    load_prm_sp500,
    load_embi_diario,
    load_embi_medias,
    load_debentures,
    load_custo_emissao,
    load_custo_emissao_periodos,
    load_beta_historico,
)
from wacc_regulatorio.params.rf import calcular_rf_media_5a
from wacc_regulatorio.params.erp import calcular_prm
from wacc_regulatorio.params.embi import calcular_embi_historico
from wacc_regulatorio.params.beta import calcular_beta_from_historico
from wacc_regulatorio.params.kd import calcular_kd_com_custo_emissao
from wacc_regulatorio.wacc_calc import calcular_wacc, WACCResult
from wacc_regulatorio.config import T_IRPJ_CSLL

# Ano de referência: o Despacho 675/2026 usa dados coletados até dez/2025
ANO_BASE_DADOS = 2025
ANO_PUBLICACAO = 2026


def executar_camada1(
    segmento: str = "transmissao",
    T: float = T_IRPJ_CSLL,
    verbose: bool = True,
) -> WACCResult:
    """
    Replica o cálculo do WACC do Despacho ANEEL 675/2026.

    Todos os parâmetros são computados a partir dos fixtures brutos (NTN-B,
    SP500, debêntures). Os valores do Despacho ficam apenas no validator.py.

    Args:
        segmento: "transmissao" (distribuicao a implementar em iteração futura)
        T: Alíquota composita IRPJ + CSLL (default 34%)
        verbose: Imprime os parâmetros calculados

    Returns:
        WACCResult com todos os componentes do WACC regulatório
    """
    if verbose:
        print(f"\n=== Camada 1 — Replicacao Despacho ANEEL 675/2026 ({segmento}) ===")
        print(f"    Ano base dados  : {ANO_BASE_DADOS}")
        print(f"    Ano publicacao  : {ANO_PUBLICACAO}")

    # --- Carrega fixtures brutos ---
    ntnb_df      = load_ntnb()
    prm_df       = load_prm_sp500()
    embi_df      = load_embi_diario()
    embi_medias_df = load_embi_medias()
    deb_df       = load_debentures()
    custo_df     = load_custo_emissao()
    periodos_df  = load_custo_emissao_periodos()
    beta_hist_df = load_beta_historico()

    # --- Rf: média de 5 médias anuais rolantes de 10a (NTN-B fixture) ---
    rf, rf_detalhes = calcular_rf_media_5a(ANO_PUBLICACAO, ntnb_df)
    if verbose:
        print(f"\n  Rf (5a × 10a)    = {rf:.4%}  [ref: 5,138%]")

    # --- PRM: média de 5 acumulados SP500 vs T-Bill (1928–ano) ---
    erp, _ = calcular_prm(ANO_PUBLICACAO, prm_df)
    if verbose:
        print(f"  PRM (5a acum.)   = {erp:.4%}  [ref: 6,848%]")

    # --- EMBI: média 10 anos (janela 2016-2025) ---
    embi = calcular_embi_historico(
        ANO_BASE_DADOS,
        embi_df=embi_df,
        embi_medias_df=embi_medias_df,
    )
    if verbose:
        print(f"  EMBI+ (10a)      = {embi:.4%}  [ref: 2,765%]")

    # --- Beta: média móvel 5a de beta_l_brasil (metodologia ANEEL confirmada no xlsx) ---
    beta_res = calcular_beta_from_historico(beta_hist_df)
    if verbose:
        print(f"  Beta_l (5a médio)= {beta_res.beta_l:.4f}  [ref: 0.7692]")
        print(f"  Beta_u (diagn.)  = {beta_res.beta_u:.4f}")
        print(f"  E/V              = {beta_res.ev:.4%}  [ref: 60,23%]")
        print(f"  D/V              = {beta_res.dv:.4%}  [ref: 39,77%]")

    # --- Kd: bottom-up de debêntures + custo de emissão (IPCA+DI pré-computado ANEEL) ---
    kd_res = calcular_kd_com_custo_emissao(
        ANO_BASE_DADOS, deb_df, custo_df, segmento, T=T, periodos_df=periodos_df
    )
    if verbose:
        print(f"  Kd debentures    = {kd_res.kd_debentures:.4%}  [ref: 6,069%]")
        print(f"  Kd custo emissao = {kd_res.custo_emissao:.4%}  [ref: 0,518%]")
        print(f"  Kd real a.i.     = {kd_res.kd_real_ai:.4%}  [ref: 6,587%]")

    # --- Montagem WACC ---
    result = calcular_wacc(
        rf=rf,
        erp=erp,
        embi=embi,
        beta_l=beta_res.beta_l,
        beta_u=beta_res.beta_u,
        ev=beta_res.ev,
        dv=beta_res.dv,
        kd_real_ai=kd_res.kd_real_ai,
        T=T,
    )

    if verbose:
        print(f"\n  --- Resultado ---")
        print(f"  Ke real d.i.     = {result.ke_real_di:.4%}  [ref: 10,405%]")
        print(f"  WACC real d.i.   = {result.wacc_real_depois_impostos:.4%}  [ref: 8,00%]")
        print(f"  WACC real a.i.   = {result.wacc_real_antes_impostos:.4%}  [ref: 12,11%]")

    return result


if __name__ == "__main__":
    result = executar_camada1()
    print()
    print(result)
    print()
    from wacc_regulatorio.validator import validar
    validar(result)
