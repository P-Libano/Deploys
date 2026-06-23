"""
Comparativo: ANEEL fixture vs calculadora ao vivo (C2) na MESMA janela temporal.

Isola a limitação das bases de dados públicas (yfinance, IPEADATA, ANBIMA pública)
vs Bloomberg, sem confundir com diferença de período.

Período de referência: idêntico ao Despacho 675/1174-2026
  - Rf, EMBI, Kd: janelas históricas até dez/2025
  - Beta: 5 janelas Oct-Sep de 2020-2021 até 2024-2025
  - ERP (PRM): série acumulada 1928-2025
"""
import sys; sys.path.insert(0, '.')
import warnings; warnings.filterwarnings('ignore')
import pandas as pd

# ── fixtures ──────────────────────────────────────────────────────────────
from wacc_regulatorio.data.fixtures import (
    load_ntnb, load_prm_sp500, load_embi_diario, load_debentures,
    load_custo_emissao, load_beta_historico, load_custo_emissao_periodos,
)
from wacc_regulatorio.data.fetchers import (
    fetch_beta_prices, fetch_market_caps, fetch_ettj_anbima,
)

# ── params ─────────────────────────────────────────────────────────────────
from wacc_regulatorio.params.rf   import calcular_rf_media_5a
from wacc_regulatorio.params.erp  import calcular_prm, _preparar_prm_df
from wacc_regulatorio.params.embi import calcular_embi_historico
from wacc_regulatorio.params.beta import calcular_beta_mktcap_window
from wacc_regulatorio.params.kd   import calcular_kd_com_custo_emissao, calcular_kd_ettj_atualizado
from wacc_regulatorio.wacc_calc   import calcular_wacc

ANO = 2026

# ── referência ANEEL ───────────────────────────────────────────────────────
REF = {
    "rf":            0.051377,
    "erp":           0.068481,
    "embi":          0.027650,
    "beta_l":        0.769239,
    "beta_u":        0.502950,
    "ev":            0.602261,
    "dv":            0.397739,
    "ke_real_di":    0.104055,
    "kd_deb":        0.060685,
    "kd_custo":      0.005181,
    "kd_real_ai":    0.065866,
    "wacc_di":       0.079959,
    "wacc_ai":       0.121150,
}

# ═══════════════════════════════════════════════════════════════════════════
# 1. Rf — mesma série NTN-B fixture (ANBIMA histórico), truncada em dez/2025
# ═══════════════════════════════════════════════════════════════════════════
ntnb = load_ntnb()
ntnb['data'] = pd.to_datetime(ntnb['data'], errors='coerce')
ntnb['vencimento'] = pd.to_datetime(ntnb['vencimento'], errors='coerce')
ntnb['taxa_compra_manha'] = pd.to_numeric(ntnb['taxa_compra_manha'], errors='coerce')
ntnb['taxa_venda_manha']  = pd.to_numeric(ntnb['taxa_venda_manha'],  errors='coerce')
# truncar em dez/2025 — mesma janela ANEEL
ntnb_fixture = ntnb[ntnb['data'] <= '2025-12-31'].copy()

rf_c2, rf_detalhes = calcular_rf_media_5a(ANO, ntnb_fixture)
rf_fonte = "NTN-B fixture ANBIMA (mesmo arquivo ANEEL, truncado dez/2025)"

# ═══════════════════════════════════════════════════════════════════════════
# 2. ERP (PRM) — fixture série 1928–2025 (Bloomberg base + yfinance extensão)
# ═══════════════════════════════════════════════════════════════════════════
prm_base = load_prm_sp500()
prm_df = _preparar_prm_df(prm_base)
# truncar em dez/2025
prm_df_2025 = prm_df[prm_df['data'] <= '2025-12-31'].copy()
erp_c2, erp_detalhes = calcular_prm(ANO, prm_df_2025)
erp_fonte = "SP500TR fixture (Bloomberg 1928–1987) + yfinance (1988–dez/2025)"

# ═══════════════════════════════════════════════════════════════════════════
# 3. EMBI — fixture IPEADATA truncado em dez/2025, mesmo método C1
# ═══════════════════════════════════════════════════════════════════════════
embi_df = load_embi_diario()
embi_df['data'] = pd.to_datetime(embi_df['data'], errors='coerce')
embi_df_2025 = embi_df[embi_df['data'] <= '2025-12-31'].copy()

ANO_BASE = 2025  # ANEEL: ano_base_dados = ano_publicacao - 1
try:
    from wacc_regulatorio.data.fixtures import load_embi_medias
    embi_medias = load_embi_medias()
    embi_c2 = calcular_embi_historico(ANO_BASE, embi_df=embi_df_2025, embi_medias_df=embi_medias)
    embi_fonte = "IPEADATA fixture -- pre-computado ANEEL (identico C1)"
except Exception as e:
    embi_c2 = calcular_embi_historico(ANO_BASE, embi_df=embi_df_2025)
    embi_fonte = f"IPEADATA fixture -- media diaria ({e})"

# ═══════════════════════════════════════════════════════════════════════════
# 4. Beta — yfinance, mesmas 5 janelas Oct-Sep 2020-21..2024-25
#    (fonte diferente: yfinance vs Bloomberg — aqui fica o gap principal)
# ═══════════════════════════════════════════════════════════════════════════
prices_df   = fetch_beta_prices()
mktcap_df   = fetch_market_caps()

# truncar preços em set/2025 (fim da última janela Oct-Sep)
prices_2025 = prices_df[prices_df.index <= '2025-09-30'].copy()

spxt_col = next(
    (c for c in prices_2025.columns if 'SP500TR' in c.upper() or 'SPXT' in c.upper() or '^GSPC' in c.upper()),
    None
)
if spxt_col is None:
    raise ValueError(f"Benchmark não encontrado. Colunas: {list(prices_2025.columns)}")

beta_res = calcular_beta_mktcap_window(prices_2025, mktcap_df, spxt_col=spxt_col)
beta_fonte = "yfinance OLS semanal — D/V book weighting (metodologia ANEEL)"

# ─── re-alavancagem para media 5a de beta_l_brasil usando beta_u C2 ───────
# A ANEEL calcula beta_l_br por janela e faz a média. Aqui temos 1 janela (5a)
# portanto beta_l = beta_u × (1 + (1-T_br) × D/E_br_2025)
T_BR = 0.34
dv_br_2025 = 0.397739
ev_br_2025 = 0.602261
de_br_2025 = dv_br_2025 / ev_br_2025  # = 0.6604

beta_l_c2 = beta_res.beta_u * (1 + (1 - T_BR) * de_br_2025)
beta_u_c2 = beta_res.beta_u

# ═══════════════════════════════════════════════════════════════════════════
# 5. Kd — mesmos 192 títulos fixture, BEI recalculado via ETTJ ao vivo
#    (Kd-mid: isola impacto de "calcular taxa_real do zero" vs ANEEL pré-computado)
# ═══════════════════════════════════════════════════════════════════════════
deb_df   = load_debentures()
custo_df = load_custo_emissao()
periodos_df = load_custo_emissao_periodos()
ettj_df = fetch_ettj_anbima()   # curva ETTJ ao vivo (ou fallback NTN-B)

kd_mid = calcular_kd_ettj_atualizado(
    ano=ANO,
    debentures_df=deb_df,
    custo_emissao_df=custo_df,
    ettj_df=ettj_df,
    segmento="transmissao",
    T=T_BR,
)
kd_fonte = "Kd-mid: mesmos 192 títulos ANEEL + BEI ETTJ ao vivo (ANBIMA pública)"

# Também calculamos o C1 direto (fixture pré-computado) para comparar Kd isolado
kd_c1 = calcular_kd_com_custo_emissao(
    ano=ANO,
    debentures_df=deb_df,
    custo_emissao_df=custo_df,
    segmento="transmissao",
    T=T_BR,
    periodos_df=periodos_df,
)

# ═══════════════════════════════════════════════════════════════════════════
# 6. WACC final C2 (mesma janela)
# ═══════════════════════════════════════════════════════════════════════════
wacc_c2 = calcular_wacc(
    rf=rf_c2,
    erp=erp_c2,
    embi=embi_c2,
    beta_l=beta_l_c2,
    beta_u=beta_u_c2,
    ev=ev_br_2025,
    dv=dv_br_2025,
    kd_real_ai=kd_mid.kd_real_ai,
    T=T_BR,
)

# ═══════════════════════════════════════════════════════════════════════════
# 7. Impressão do quadro
# ═══════════════════════════════════════════════════════════════════════════
def bp(v_c2, v_ref):
    return (v_c2 - v_ref) * 10000

SEP = "-" * 110
linha = "{:<30} {:>12} {:>12} {:>10}   {}"

print("\n" + SEP)
print("  WACC REGULATORIO -- ANEEL FIXTURE vs C2 (MESMA JANELA 2016-2025)")
print("  Objetivo: isolar limitacoes de base de dados, sem diferenca de periodo")
print(SEP)
print(linha.format("Parametro", "ANEEL ref", "C2 (pub)", "Delta bp", "Fonte C2"))
print(SEP)

# (nome, ref, c2, fonte, formato_pct)  — False para adimensionais como beta
rows = [
    ("Rf -- Taxa Livre de Risco",      REF["rf"],       rf_c2,                              rf_fonte,    True),
    ("ERP -- Premio de Risco",         REF["erp"],      erp_c2,                             erp_fonte,   True),
    ("EMBI -- Risco Brasil",           REF["embi"],     embi_c2,                            embi_fonte,  True),
    ("Bu -- Beta Desalavancado (EUA)", REF["beta_u"],   beta_u_c2,                          beta_fonte,  False),
    ("Bl -- Beta Alavancado (BR)",     REF["beta_l"],   beta_l_c2,                          beta_fonte,  False),
    ("E/V -- Estrutura de Capital",    REF["ev"],       ev_br_2025,                         "Fixture (invariante)", True),
    ("D/V -- Estrutura de Capital",    REF["dv"],       dv_br_2025,                         "Fixture (invariante)", True),
    ("Ke_di -- Custo do Equity",       REF["ke_real_di"], wacc_c2.ke_real_di,               "Rf + Bl x ERP",        True),
    ("Kd_deb -- Debentures",           REF["kd_deb"],   kd_mid.kd_debentures,               kd_fonte,    True),
    ("Custo de emissao",               REF["kd_custo"], kd_mid.custo_emissao,               "Media individual (sem agregado ANEEL)", True),
    ("Kd_ai -- Custo da Divida AI",    REF["kd_real_ai"], kd_mid.kd_real_ai,                "",          True),
    ("WACC_di -- Real depois impostos",REF["wacc_di"],  wacc_c2.wacc_real_depois_impostos,  "",          True),
    ("WACC_ai -- Real antes impostos", REF["wacc_ai"],  wacc_c2.wacc_real_antes_impostos,   "RESULTADO FINAL", True),
]

for nome, ref, c2, fonte, pct in rows:
    delta = bp(c2, ref)
    sinal = f"{delta:+.1f}"
    fmt = ".4%" if pct else ".4f"
    print(linha.format(nome, format(ref, fmt), format(c2, fmt), sinal, fonte[:65]))

print(SEP)

print("\n  DETALHE Kd -- mesmo periodo, duas formas de calcular taxa_real:")
print(f"  C1  (taxa_real ANEEL - BEI na data emissao): Kd_deb={kd_c1.kd_debentures:.4%}  custo={kd_c1.custo_emissao:.4%}  Kd_ai={kd_c1.kd_real_ai:.4%}")
print(f"  mid (taxa_real recalculada - BEI ETTJ live): Kd_deb={kd_mid.kd_debentures:.4%}  custo={kd_mid.custo_emissao:.4%}  Kd_ai={kd_mid.kd_real_ai:.4%}")
print(f"  Delta Kd-mid vs C1: {bp(kd_mid.kd_real_ai, kd_c1.kd_real_ai):+.1f} bp")
print("  Explicacao: BEI ETTJ atual != BEI Bloomberg na data de emissao de cada titulo")

print(f"\n  DETALHE BETA -- yfinance vs Bloomberg (mesma janela Oct-Sep 2020-2025):")
print(f"  Bu yfinance:  {beta_u_c2:.6f}   (delta vs ANEEL: {bp(beta_u_c2, REF['beta_u']):+.1f} bp)")
print(f"  Bu Bloomberg: {REF['beta_u']:.6f}   (referencia ANEEL)")
print("  Gap estrutural: ajustes dividendo, horario fechamento, dados faltantes por empresa")
print()
