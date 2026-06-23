"""
Replica exatamente a fórmula ANEEL para beta:
=IFERROR(COVARIANCE.S(col_acao; col_spxt) / VAR.S(col_spxt); "")

Onde:
- col_acao = retorno simples semanal P_n/P_{n-1} da utility
- col_spxt = mesmo para SPXT (S&P 500 Total Return)

Executar: python scripts/beta_aneel_metodologia.py
"""
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
from wacc_regulatorio.data.fetchers import fetch_beta_prices, fetch_market_caps
from wacc_regulatorio.config import T_IRPJ_CSLL

T_BR  = T_IRPJ_CSLL   # 0.34
T_US  = 0.257          # taxa efetiva EUA pos-reforma 2025
EV_BR = 0.602261
DV_BR = 0.397739
DE_BR = DV_BR / EV_BR

prices = fetch_beta_prices(start="2019-10-01")
mktcaps = fetch_market_caps()

# Janela 2025: Oct-2020 a Set-2025 (mesma do fixture ANEEL)
start = pd.Timestamp("2020-10-01")
end   = pd.Timestamp("2025-09-30")
df = prices[(prices.index >= start) & (prices.index <= end)].copy()

sp = "^SP500TR"
# Retorno simples P_n/P_{n-1} — replica Excel ANEEL (nao log)
rets = (df / df.shift(1)).dropna(how="all")
tickers = [c for c in rets.columns if c != sp]

de_map = dict(zip(mktcaps["ticker"], mktcaps["de_ratio"]))
mc_map = dict(zip(mktcaps["ticker"], mktcaps["market_cap_usd"]))

print("=" * 60)
print("BETA METODOLOGIA ANEEL")
print("=" * 60)
print(f"Retorno : simples  P_n / P_{{n-1}}")
print(f"Benchmark: {sp}  (SPXT Total Return)")
print(f"Formula : COVARIANCE.S(col_acao, col_spxt) / VAR.S(col_spxt)")
print(f"Janela  : Oct-2020 a Set-2025  ({len(df)} semanas)")
print()

betas_u = {}
print(f"  {'Ticker':<5}  {'beta_l':>8}  {'D/E_us':>7}  {'beta_u':>8}  {'mktcap':>10}")
print("  " + "-" * 50)

for t in tickers:
    col = rets[[sp, t]].dropna()
    if len(col) < 50:
        print(f"  {t:<5}  insuficiente ({len(col)} obs)")
        continue
    # COVARIANCE.S / VAR.S = exatamente o slope OLS
    cov = np.cov(col[sp].values, col[t].values, ddof=1)[0, 1]
    var = np.var(col[sp].values, ddof=1)
    beta_l_us = cov / var
    de = de_map.get(t)
    mc = mc_map.get(t, 0)
    if de is not None:
        bu = beta_l_us / (1 + (1 - T_US) * de)
        betas_u[t] = bu
        print(f"  {t:<5}  {beta_l_us:>8.4f}  {de:>7.3f}  {bu:>8.4f}  {mc/1e9:>8.1f}Bi")
    else:
        print(f"  {t:<5}  {beta_l_us:>8.4f}  sem D/E")

# Pesos mktcap com cap 50%
total_mc = sum(mc_map.get(t, 0) for t in betas_u)
raw_w = {t: mc_map.get(t, 0) / total_mc for t in betas_u}
excesso = sum(max(0, w - 0.5) for w in raw_w.values())
n_abaixo = sum(1 for w in raw_w.values() if w < 0.5)
pesos = {}
for t, w in raw_w.items():
    pesos[t] = 0.5 if w >= 0.5 else w + excesso / n_abaixo
soma_p = sum(pesos.values())
pesos = {t: w / soma_p for t, w in pesos.items()}

beta_u_pond = sum(pesos[t] * betas_u[t] for t in betas_u)
beta_l_br   = beta_u_pond * (1 + (1 - T_BR) * DE_BR)

print()
print("=== RESULTADO ===")
print(f"  beta_u ponderado mktcap = {beta_u_pond:.6f}")
print(f"  Re-alavancagem com D/E_BR:")
print(f"  beta_l = {beta_u_pond:.6f} x (1 + {1-T_BR:.2f} x {DE_BR:.4f})")
print(f"         = {beta_u_pond:.6f} x {1 + (1-T_BR)*DE_BR:.6f}")
print(f"         = {beta_l_br:.6f}")
print()
print("=== Referencia fixture ANEEL (janela 2025) ===")
print(f"  beta_u = 0.293106   beta_l_br = 0.420863")
print(f"  Delta beta_u : {(beta_u_pond - 0.293106)*10000:+.1f}bp")
print(f"  Delta beta_l : {(beta_l_br   - 0.420863)*10000:+.1f}bp")
print()
print("Nota: CHG e POM ausentes (delistadas/sem dados yfinance).")
print("      ANEEL usou dados Bloomberg com amostra completa na epoca.")
