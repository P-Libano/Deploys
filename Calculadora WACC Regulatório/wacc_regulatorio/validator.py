"""
Validação dos resultados da Camada 1 contra os valores publicados no Despacho ANEEL 675/2026.

Tolerâncias:
    Parâmetros intermediários : ±1bp (0,0001)  — variações aceitáveis de filtragem de dados brutos
    WACC final                : ±5bp (0,0005)  — acumula deltas de rf + kd quando computando de fixtures

Nota: C1 computa TODOS os parâmetros de fixtures brutos (NTN-B, SP500, debêntures).
Deltas de até 5bp são esperados por diferenças de corte de data e critérios de filtragem
entre a nossa implementação e a planilha ANEEL. A tolerância de 0bp era válida apenas
quando C1 lia os resultados publicados diretamente — prática eliminada.

Referências extraídas de
    anexo-despacho-1174-2026-aneel-2-Anexo_Memoria_de_Calculo_WACC_2026.xlsx
com 6+ dígitos significativos (não arredondados).
"""
from wacc_regulatorio.wacc_calc import WACCResult

VALORES_REFERENCIA = {
    "transmissao": {
        "rf":             (0.051377,  "Taxa Livre de Risco"),
        "erp":            (0.068481,  "Premio de Risco de Mercado (ERP)"),
        "beta_l":         (0.769239,  "Beta Alavancado (US leverage)"),
        "beta_u":         (0.50295,   "Beta Desalavancado EUA (media 5a janelas 2021-2025)"),
        "ev":             (0.602261,  "E/V Estrutura de Capital"),
        "dv":             (0.397739,  "D/V Estrutura de Capital"),
        "ke_real_di":     (0.104055,  "Ke Real Depois de Impostos"),
        "kd_real_ai":     (0.065866,  "Kd Real Antes de Impostos"),
        "kd_debentures":  (0.060685,  "Kd Debentures"),
        "custo_emissao":  (0.005181,  "Custo de Emissao"),
        "wacc_di":        (0.079959,  "WACC Real Depois de Impostos"),
        "wacc_ai":        (0.121150,  "WACC Real Antes de Impostos"),
    }
}

TOL_PARAMETRO = 0.0001    # ±1bp  — variações aceitáveis de filtragem de dados brutos
TOL_WACC      = 0.0005    # ±5bp  — acumulado de rf + kd quando computando de fixtures

# Parâmetros com tolerância ajustada por razão documentada
TOL_OVERRIDE = {
    "rf":         0.0005, # Residual -0.15bp (ANEEL inclui NTN-B com yield negativo — sem filtro de piso)
    "beta_u":     0.005,  # diagnóstico: não entra no WACC, apenas exibido; tolerância 50bp
    "ke_real_di": 0.0005, # Acumula delta do Rf
    "kd_real_ai": 0.0002, # Residual ~0bp (custo emissão usa agregado IPCA+DI do fixture periodos)
}


def validar(
    result: WACCResult,
    segmento: str = "transmissao",
    verbose: bool = True,
) -> bool:
    """
    Compara WACCResult com os valores publicados do Despacho ANEEL 675/2026.

    Args:
        result: Resultado calculado pela Camada 1
        segmento: "transmissao"
        verbose: Se True, imprime tabela de comparação

    Returns:
        True se WACC_ai e WACC_di convergem dentro da tolerância
    """
    if segmento not in VALORES_REFERENCIA:
        raise ValueError(f"Segmento '{segmento}' sem referência (disponível: transmissao)")

    refs = VALORES_REFERENCIA[segmento]

    result_map = {
        "rf":            result.rf,
        "erp":           result.erp,
        "beta_l":        result.beta_l,
        "beta_u":        result.beta_u,
        "ev":            result.ev,
        "dv":            result.dv,
        "ke_real_di":    result.ke_real_di,
        "kd_real_ai":    result.kd_real_ai,
        "wacc_di":       result.wacc_real_depois_impostos,
        "wacc_ai":       result.wacc_real_antes_impostos,
    }

    wacc_ok = True
    if verbose:
        print(f"\n{'='*65}")
        print(f"Validacao WACC {segmento.upper()} — Despacho ANEEL 675/2026")
        print(f"{'='*65}")
        print(f"{'Parametro':<25} {'Ref':>8} {'Calc':>8} {'Delta_bp':>8} {'Status'}")
        print(f"{'-'*65}")

    for key, (ref_val, label) in refs.items():
        calc_val = result_map.get(key)
        if calc_val is None:
            continue

        delta = calc_val - ref_val
        delta_bp = delta * 10000

        tol = TOL_OVERRIDE.get(key, TOL_PARAMETRO)
        if key in ("wacc_di", "wacc_ai"):
            tol = TOL_WACC

        ok = abs(delta) <= tol
        if key in ("wacc_di", "wacc_ai") and not ok:
            wacc_ok = False

        if verbose:
            status = "OK" if ok else "WARN"
            print(
                f"{label[:25]:<25} {ref_val:>8.4%} {calc_val:>8.4%} "
                f"{delta_bp:>+8.1f}  {status}"
            )

    if verbose:
        print(f"{'='*65}")
        final = "PASS" if wacc_ok else "FAIL"
        print(f"Resultado: {final}  (WACC_ai tol=±{TOL_WACC*10000:.0f}bp)")
        if not wacc_ok:
            raise AssertionError(
                f"WACC_ai calculado={result.wacc_real_antes_impostos:.4%} "
                f"diverge mais de {TOL_WACC*10000:.0f}bp do referencial "
                f"{VALORES_REFERENCIA[segmento]['wacc_ai'][0]:.4%}"
            )

    return wacc_ok


if __name__ == "__main__":
    from wacc_regulatorio.camada1_replicacao import executar_camada1
    result = executar_camada1()
    validar(result, segmento="transmissao")
