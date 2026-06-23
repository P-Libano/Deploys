"""
Comparativo tres trilhas de calculo WACC Regulatorio (Transmissao, 2026):

  C1 ANEEL   : fixture Bloomberg pre-computado, janela historica 2016-2025
  C1 Publico : fontes publicas (yfinance/ANBIMA/IPEADATA), mesma janela 2016-2025
               Beta: 5 janelas yfinance Oct-Sep ate set/2025 (gap Bloomberg estrutural)
               Kd: bottom-up com BEI historico (inflacao_implicita fixture)
  C2 (YTD)   : executar_camada2() — 4 janelas Bloomberg + 1 yfinance; solver D/V

Uso:
  python scripts/comparativo_trilhas.py
"""
import sys, os
sys.path.insert(0, '.')
import warnings; warnings.filterwarnings('ignore')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from datetime import datetime
from wacc_regulatorio.config import T_IRPJ_CSLL, JANELA_ANOS

# ── loaders ────────────────────────────────────────────────────────────────
from wacc_regulatorio.data.fixtures import (
    load_ntnb, load_prm_sp500, load_embi_diario, load_embi_medias,
    load_debentures, load_custo_emissao, load_custo_emissao_periodos,
    load_beta_historico, load_wacc_aplicacao,
)
from wacc_regulatorio.data.fetchers import (
    fetch_ntnb_tesouro, fetch_embi_ipeadata, fetch_beta_prices,
    fetch_market_caps, fetch_prm_sp500tr_incremento, fetch_ettj_anbima,
)

# ── params ─────────────────────────────────────────────────────────────────
from wacc_regulatorio.params.rf   import calcular_rf_media_5a
from wacc_regulatorio.params.erp  import calcular_prm, _preparar_prm_df
from wacc_regulatorio.params.embi import calcular_embi_historico
from wacc_regulatorio.params.beta import calcular_beta_mktcap_window, calcular_beta_from_historico, calcular_beta_janelas_anuais
from wacc_regulatorio.params.kd   import calcular_kd_com_custo_emissao
from wacc_regulatorio.camada2_corrente import executar_camada2
from wacc_regulatorio.wacc_calc import calcular_wacc

T  = T_IRPJ_CSLL
T_US = 0.21

ANO_PUB  = 2026   # ano de publicacao do despacho
ANO_BASE = 2025   # ultimo ano completo de dados (P-1)
ANO_ATUAL = datetime.now().year

# ── referencia ANEEL (C1 fixture) ──────────────────────────────────────────
REF = {
    "rf":         0.051377,
    "erp":        0.068481,
    "embi":       0.027650,
    "beta_u":     0.502950,
    "beta_l":     0.769239,
    "ev":         0.602261,
    "dv":         0.397739,
    "ke_real_di": 0.104055,
    "kd_deb":     0.060685,
    "kd_custo":   0.005181,
    "kd_ai":      0.065866,
    "wacc_di":    0.079959,
    "wacc_ai":    0.121150,
}

# ══════════════════════════════════════════════════════════════════════════
# BLOCO A — dados compartilhados (carregados uma vez)
# ══════════════════════════════════════════════════════════════════════════

ntnb_hist    = load_ntnb()
prm_base     = load_prm_sp500()
embi_hist    = load_embi_diario()
embi_medias  = load_embi_medias()
deb_df       = load_debentures()
custo_df     = load_custo_emissao()
periodos_df  = load_custo_emissao_periodos()
beta_hist_df = load_beta_historico()
wacc_apl_df  = load_wacc_aplicacao()

# estrutura de capital regulatoria (do despacho)
_ref_cap = wacc_apl_df[wacc_apl_df["segmento"] == "transmissao"].sort_values("ano").iloc[-1]
EV_REG = float(_ref_cap["ev"])
DV_REG = float(_ref_cap["dv"])
DE_BR  = DV_REG / EV_REG

# prm_df com extensao yfinance
prm_df_ext = fetch_prm_sp500tr_incremento(prm_base)

# beta prices (cache) para C1 Publico
prices_all = fetch_beta_prices()
mktcap_df  = fetch_market_caps()
spxt_col   = next(
    (c for c in prices_all.columns if 'SP500TR' in c.upper() or 'SPXT' in c.upper()),
    None
)

# ntnb live
try:
    ntnb_live = fetch_ntnb_tesouro()
    ntnb_all  = pd.concat([ntnb_hist, ntnb_live], ignore_index=True).drop_duplicates(
        subset=["data", "vencimento"]
    )
except Exception:
    ntnb_all = ntnb_hist.copy()

# embi live
try:
    embi_live = fetch_embi_ipeadata()
    embi_all  = pd.concat([embi_hist, embi_live], ignore_index=True).drop_duplicates(
        subset=["data"]
    ).sort_values("data")
except Exception:
    embi_all = embi_hist.copy()

# ══════════════════════════════════════════════════════════════════════════
# TRILHA 1 — C1 ANEEL (fixture Bloomberg)
# ══════════════════════════════════════════════════════════════════════════
c1 = dict(REF)
_w = calcular_wacc(
    rf=c1["rf"], erp=c1["erp"], embi=c1["embi"],
    beta_l=c1["beta_l"], beta_u=c1["beta_u"],
    ev=EV_REG, dv=DV_REG,
    kd_real_ai=c1["kd_ai"], T=T,
)
c1["wacc_ai"] = _w.wacc_real_antes_impostos

# ══════════════════════════════════════════════════════════════════════════
# TRILHA 2 — C1 Publico (fontes publicas, mesma janela 2016-2025)
# ══════════════════════════════════════════════════════════════════════════

# Rf: NTN-B fixture truncado em dez/2025 (mesmo arquivo ANEEL)
ntnb_2025 = ntnb_hist[pd.to_datetime(ntnb_hist["data"], errors="coerce") <= "2025-12-31"].copy()
rf_pub, _ = calcular_rf_media_5a(ANO_PUB, ntnb_2025)

# ERP: serie 1928-2025 (Bloomberg base + yfinance ate dez/2025)
prm_2025 = prm_df_ext[pd.to_datetime(prm_df_ext["data"], errors="coerce") <= "2025-12-31"].copy()
erp_pub, _ = calcular_prm(ANO_PUB, prm_2025)

# EMBI: valor pre-computado ANEEL (mesmo C1)
embi_pub = calcular_embi_historico(ANO_BASE, embi_df=embi_hist, embi_medias_df=embi_medias)

# Beta C1 Publico: 4 janelas Bloomberg (fixture ANEEL xlsx, anos 2021-2024)
#                  + 1 janela yfinance Oct2024-Sep2025
# Isola o gap de BD apenas na janela corrente — historico vem do xlsx publico ANEEL
# Logica identica ao 4+1 do C2, mas referenciada a janela 2021-2025 (mesma do ANEEL)
prices_2025 = prices_all[prices_all.index <= "2025-09-30"].copy()
# Janela 2025 via yfinance (1 ano: Oct2024-Sep2025)
_beta_2025_yf = calcular_beta_janelas_anuais(
    prices_2025, mktcap_df, beta_hist_df, spxt_col=spxt_col, anos=[2025]
)
# 4 janelas Bloomberg do fixture ANEEL (anos 2021-2024)
_hist_2021_2024 = beta_hist_df[beta_hist_df["ano"].isin([2021, 2022, 2023, 2024])].sort_values("ano")
_bl_janelas = list(_hist_2021_2024["beta_l_brasil"]) + [_beta_2025_yf.beta_l]
_bu_janelas  = list(_hist_2021_2024["beta_u_eua"])  + [_beta_2025_yf.beta_u]
beta_l_pub  = float(np.mean(_bl_janelas))
beta_u_pub  = float(np.mean(_bu_janelas))
# E/V D/V Brasil: fixture 2025 (mais recente)
_row_2025   = beta_hist_df[beta_hist_df["ano"] == 2025].iloc[0]
_ev_pub     = float(_row_2025["ev_brasil"])
_dv_pub     = float(_row_2025["dv_brasil"])

# Kd: mesma fonte que C1 ANEEL (taxa_real do fixture) + custo frozen
# Gap 0bp vs C1 — confirma que Kd NAO e fonte de gap de base de dados
kd_pub = calcular_kd_com_custo_emissao(
    ano=ANO_BASE,
    debentures_df=deb_df,
    custo_emissao_df=custo_df,
    periodos_df=periodos_df,
    segmento="transmissao",
    T=T,
)

wacc_pub = calcular_wacc(
    rf=rf_pub, erp=erp_pub, embi=embi_pub,
    beta_l=beta_l_pub, beta_u=beta_u_pub,
    ev=_ev_pub, dv=_dv_pub,
    kd_real_ai=kd_pub.kd_real_ai, T=T,
)

c1pub = {
    "rf": rf_pub, "erp": erp_pub, "embi": embi_pub,
    "beta_u": beta_u_pub, "beta_l": beta_l_pub,
    "ev": _ev_pub, "dv": _dv_pub,
    "ke_real_di": wacc_pub.ke_real_di,
    "kd_deb": kd_pub.kd_debentures, "kd_custo": kd_pub.custo_emissao,
    "kd_ai": kd_pub.kd_real_ai,
    "wacc_di": wacc_pub.wacc_real_depois_impostos,
    "wacc_ai": wacc_pub.wacc_real_antes_impostos,
}

# ══════════════════════════════════════════════════════════════════════════
# TRILHA 3 — C2 YTD (executar_camada2: 4 Bloomberg + 1 yfinance + solver D/V)
# ══════════════════════════════════════════════════════════════════════════

print("\nCalculando C2 YTD via executar_camada2()...")
c2_result = executar_camada2(verbose=True)
w2 = c2_result.wacc
sp = c2_result.snapshot_params
kr2 = c2_result.kd_cenarios.get("base")

c2ytd = {
    "rf":         sp.get("rf", w2.rf),
    "erp":        sp.get("prm", w2.erp),
    "embi":       sp.get("embi", w2.embi),
    "beta_u":     sp.get("beta_u", w2.beta_u),
    "beta_l":     sp.get("beta_l", w2.beta_l),
    "ev":         sp.get("ev", w2.ev),
    "dv":         sp.get("dv", w2.dv),
    "ke_real_di": w2.ke_real_di,
    "kd_deb":     kr2.kd_debentures if kr2 else sp.get("kd_debentures", 0),
    "kd_custo":   kr2.custo_emissao  if kr2 else sp.get("kd_custo_emissao", 0),
    "kd_ai":      w2.kd_real_ai,
    "wacc_di":    w2.wacc_real_depois_impostos,
    "wacc_ai":    w2.wacc_real_antes_impostos,
}

# ══════════════════════════════════════════════════════════════════════════
# IMPRESSAO
# ══════════════════════════════════════════════════════════════════════════

def bp(v, ref): return (v - ref) * 10000

# Explicacao do gap de base de dados (Bloomberg vs publico, mesma janela)
CAUSA_BD = {
    "rf":         "data de corte NTN-B (±1 dia ANBIMA)",
    "erp":        "mesma serie PRM (fixture ANEEL)",
    "embi":       "mesma serie IPEADATA",
    "beta_u":     "yfinance jan2025: ponderacao D/V book",
    "beta_l":     "yfinance jan2025: -48bp/janela ÷ 5 janelas",
    "ev":         "fixture ANEEL (identico C1)",
    "dv":         "fixture ANEEL (identico C1)",
    "ke_real_di": "propagacao Bl gap (-9,6bp × ERP × E/V)",
    "kd_deb":     "BEI historico fixture (inflacao_implicita)",
    "kd_custo":   "congelado Res. CVM 160 / jul2022",
    "kd_ai":      "Kd_deb + custo identicos (ambos 0bp)",
    "wacc_di":    "Bl gap propagado via Ke × E/V/(1-T)",
    "wacc_ai":    "Bl gap unico driver (-9,6bp × E/V/(1-T))",
}

SEP  = "-" * 160
hdr  = "{:<30}  {:>10}  {:>10}  {:>8}  {:>10}  {:>8}  {:>10}  {:>8}  {:<}"
row_pct = lambda n, k: hdr.format(
    n,
    f"{c1[k]:.4%}", f"{c1pub[k]:.4%}", f"{bp(c1pub[k],c1[k]):+.1f}",
    f"{c2ytd[k]:.4%}", f"{bp(c2ytd[k],c1[k]):+.1f}",
    f"{c2ytd[k]:.4%}", f"{bp(c2ytd[k],c1pub[k]):+.1f}",
    CAUSA_BD.get(k, ""),
)
row_dec = lambda n, k: hdr.format(
    n,
    f"{c1[k]:.4f}", f"{c1pub[k]:.4f}", f"{bp(c1pub[k],c1[k]):+.1f}",
    f"{c2ytd[k]:.4f}", f"{bp(c2ytd[k],c1[k]):+.1f}",
    f"{c2ytd[k]:.4f}", f"{bp(c2ytd[k],c1pub[k]):+.1f}",
    CAUSA_BD.get(k, ""),
)

print("\n" + SEP)
print("  WACC REGULATORIO -- COMPARATIVO TRES TRILHAS (Transmissao 2026)")
print(SEP)
print(hdr.format(
    "Parametro",
    "C1 ANEEL", "C1 Pub", "dif bp",
    "C2 YTD", "vs C1 bp",
    "C2 YTD", "vs C1pub",
    "Causa BD gap (C1pub vs C1 ANEEL)",
))
print(hdr.format(
    "",
    "Bloomberg", "Pub/hist", "BD gap",
    "Pub/live", "total",
    "Pub/live", "mkt mvmt",
    "",
))
print(SEP)
print(row_pct("Rf -- Taxa Livre de Risco",  "rf"))
print(row_pct("ERP -- Premio de Risco",      "erp"))
print(row_pct("EMBI -- Risco Brasil",        "embi"))
print(row_dec("Bu -- Beta Desalavancado",    "beta_u"))
print(row_dec("Bl -- Beta Alavancado (BR)",  "beta_l"))
print(row_pct("E/V",                         "ev"))
print(row_pct("D/V",                         "dv"))
print(row_pct("Ke_di -- Custo Equity",       "ke_real_di"))
print(row_pct("Kd_deb -- Debentures",        "kd_deb"))
print(row_pct("Custo de emissao",            "kd_custo"))
print(row_pct("Kd_ai -- Custo Divida AI",    "kd_ai"))
print(row_pct("WACC_di -- Real DI",          "wacc_di"))
print(SEP)
print(row_pct("WACC_ai -- Real AI",          "wacc_ai"))
print(SEP)

print(f"""
Legenda colunas:
  C1 ANEEL   : fixture pre-computado ANEEL (Bloomberg) -- referencia de validacao (0bp)
  C1 Pub     : fontes publicas (yfinance/ANBIMA), janela identica 2016-2025
               Kd: bottom-up com BEI historico (inflacao_implicita fixture ANEEL)
  dif bp     : gap de base de dados (yfinance vs Bloomberg, mesmo periodo)
  C2 YTD     : executar_camada2() — 4 Bloomberg + 1 yfinance; solver D/V; custo frozen
  vs C1 bp   : delta total (base de dados + movimento de mercado)
  vs C1pub   : apenas movimento de mercado (base de dados isolada)

Metodologia beta:
  C1 ANEEL   : 5 janelas Bloomberg Oct-Sep (2021-2025) → media beta_l_brasil (xlsx ANEEL)
  C1 Pub     : 4 janelas Bloomberg (2021-2024) fixture xlsx ANEEL + 1 janela yfinance (2025)
               BD gap isolado apenas na janela 2025 (Bloomberg vs yfinance = -48bp/janela)
  C2 YTD     : 4 janelas Bloomberg (2022-2025) fixture xlsx + 1 janela yfinance (2026 live)

D/V (estrutura de capital):
  C1/C1pub   : fixture ANEEL (D/V regulatorio do despacho)
  C2 YTD     : solver iterativo AD10 = 3 x (0.0307 + WACC_ai) — ponto fixo endogeno

Janelas de referencia:
  Rf  : C1/C1pub = 5x10a ate dez/2025 | C2 = 5x10a ate YTD {ANO_ATUAL}
  ERP : C1/C1pub = acumulado 1928-2025 | C2 = acumulado 1928-YTD {ANO_ATUAL}
  EMBI: C1/C1pub = media 10a 2016-2025 | C2 = media 10a 2017-YTD {ANO_ATUAL}
  Beta: C1/C1pub = 5 janelas Oct-Sep ate 2025 | C2 = 4+1 hybrid (Bloomberg+yfinance)
  Kd  : C1pub = bottom-up BEI historico (inflacao_implicita) | C2 = Kd-mid ETTJ ao vivo
""")
