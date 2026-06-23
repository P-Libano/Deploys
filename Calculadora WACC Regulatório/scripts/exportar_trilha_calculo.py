"""
Exporta todos os dados granulares utilizados no cálculo do WACC ANEEL (C1).

Saída: data/trilha_calculo/*.csv
  01_rf_ntnb_filtrado.csv        — NTN-B diário após filtros ANEEL (usado no Rf)
  02_rf_media_anual.csv          — Rf anual de cada uma das 5 janelas rolantes
  03_erp_serie_mensal.csv        — Série mensal SP500 + T-Bill + PRM_mensal (1928-2025)
  04_erp_prm_anual.csv           — PRM acumulado até cada um dos 5 anos
  05_embi_diario.csv             — EMBI+ diário janela [2016-2025]
  06_embi_media_anual.csv        — Média EMBI por ano e média da janela
  07_beta_historico.csv          — Beta por janela anual (1 linha/ano, fixture ANEEL)
  08_beta_c2_por_empresa.csv     — Beta, covariância, D/V, peso por empresa (C2 yfinance)
  09_beta_c2_retornos_semanais.csv — Retornos semanais simples por ticker (janela Oct-Sep)
  10_kd_debentures.csv           — 192 debêntures transmissão janela [2016-2025]
  11_kd_custo_emissao.csv        — Custo emissão por título (fixture ANEEL)
  12_kd_custo_emissao_periodos.csv — Agregado IPCA+DI por janela (pré-computado ANEEL)
  13_wacc_componentes.csv        — Saída final: todos os parâmetros e resultado WACC
"""
import sys; sys.path.insert(0, '.')
import warnings; warnings.filterwarnings('ignore')
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import linregress

from wacc_regulatorio.data.fixtures import (
    load_ntnb, load_prm_sp500, load_embi_diario, load_embi_medias,
    load_debentures, load_custo_emissao, load_custo_emissao_periodos,
    load_beta_historico,
)
from wacc_regulatorio.params.rf import calcular_rf_anual_10a, calcular_rf_media_5a
from wacc_regulatorio.params.erp import _preparar_prm_df, _prm_acumulado_ate_ano
from wacc_regulatorio.params.beta import _hamada_unlever
from wacc_regulatorio.config import T_IRPJ_CSLL, JANELA_BETA_ANOS

ANO_BASE = 2025
ANO_PUB  = 2026
OUT      = Path('data/trilha_calculo')
OUT.mkdir(parents=True, exist_ok=True)

print("=== Exportando trilha de cálculo WACC ANEEL 675/2026 ===\n")

# ─────────────────────────────────────────────────────────────
# 01 — Rf NTN-B diário após filtros ANEEL
# ─────────────────────────────────────────────────────────────
print("01 Rf — NTN-B filtrado...")
ntnb = load_ntnb()
ntnb['data'] = pd.to_datetime(ntnb['data'], errors='coerce')
ntnb['vencimento'] = pd.to_datetime(ntnb['vencimento'], errors='coerce')
ntnb['taxa_compra_manha'] = pd.to_numeric(ntnb['taxa_compra_manha'], errors='coerce')
ntnb['taxa_venda_manha']  = pd.to_numeric(ntnb['taxa_venda_manha'],  errors='coerce')

# Janela mais ampla necessária: ano 2021 usa [2012,2021], começa em 2012
ntnb_filt = ntnb[(ntnb['data'] >= '2012-01-01') & (ntnb['data'] <= '2025-12-31')].copy()
ntnb_filt = ntnb_filt[ntnb_filt['vencimento'] > ntnb_filt['data']]
ntnb_filt = ntnb_filt[ntnb_filt['taxa_compra_manha'].notna() & (ntnb_filt['taxa_compra_manha'] <= 0.25)]
ntnb_filt['taxa_media'] = ntnb_filt[['taxa_compra_manha', 'taxa_venda_manha']].mean(axis=1)
ntnb_filt['prazo_anos'] = (ntnb_filt['vencimento'] - ntnb_filt['data']).dt.days / 365.25
ntnb_filt = ntnb_filt[['data', 'vencimento', 'prazo_anos', 'taxa_compra_manha', 'taxa_venda_manha', 'taxa_media']].sort_values(['data', 'vencimento'])
ntnb_filt.to_csv(OUT / '01_rf_ntnb_filtrado.csv', index=False, sep=';', decimal=',', float_format='%.6f')
print(f"   -> {len(ntnb_filt)} linhas")

# ─────────────────────────────────────────────────────────────
# 02 — Rf anual de cada uma das 5 janelas
# ─────────────────────────────────────────────────────────────
print("02 Rf — médias anuais rolantes...")
rf_rows = []
for ano in range(ANO_PUB - 5, ANO_PUB):
    inicio = pd.Timestamp(f'{ano-9}-01-01')
    fim    = pd.Timestamp(f'{ano}-12-31')
    sub = ntnb_filt[(ntnb_filt['data'] >= inicio) & (ntnb_filt['data'] <= fim)]
    daily = sub.groupby('data')['taxa_media'].mean()
    rf_ano = float(daily.mean())
    rf_rows.append({
        'ano_publicacao': ANO_PUB,
        'ano_janela': ano,
        'janela_inicio': ano - 9,
        'janela_fim': ano,
        'n_dias_pregao': len(daily),
        'n_vencimentos_distintos': sub['vencimento'].nunique(),
        'rf_anual_decimal': rf_ano,
        'rf_anual_pct': rf_ano * 100,
    })

rf_anual_df = pd.DataFrame(rf_rows)
rf_final = rf_anual_df['rf_anual_decimal'].mean()
rf_rows.append({
    'ano_publicacao': ANO_PUB, 'ano_janela': 'MEDIA_5A', 'janela_inicio': '',
    'janela_fim': '', 'n_dias_pregao': '', 'n_vencimentos_distintos': '',
    'rf_anual_decimal': rf_final, 'rf_anual_pct': rf_final * 100,
})
pd.DataFrame(rf_rows).to_csv(OUT / '02_rf_media_anual.csv', index=False, sep=';', decimal=',', float_format='%.6f')
print(f"   -> {len(rf_rows)} linhas  |  Rf final = {rf_final:.6%}  [ref: 5,1377%]")

# ─────────────────────────────────────────────────────────────
# 03 — ERP: série mensal completa SP500 + T-Bill + PRM_mensal
# ─────────────────────────────────────────────────────────────
print("03 ERP — série mensal 1928-2025...")
prm_raw = load_prm_sp500()
prm_df  = _preparar_prm_df(prm_raw)
prm_serie = prm_df[['data', 'sp500', 'rf_tbill', 'rm_12m', 'rf_tbill_dec', 'prm_mensal']].copy()
prm_serie.to_csv(OUT / '03_erp_serie_mensal.csv', index=False, sep=';', decimal=',', float_format='%.6f')
print(f"   -> {len(prm_serie)} linhas")

# ─────────────────────────────────────────────────────────────
# 04 — ERP: PRM acumulado até cada um dos 5 anos
# ─────────────────────────────────────────────────────────────
print("04 ERP — PRM acumulado por ano...")
erp_rows = []
for ano in range(ANO_PUB - 5, ANO_PUB):
    sub = prm_df[prm_df['data'].dt.year <= ano].dropna(subset=['prm_mensal'])
    prm_ac = float(sub['prm_mensal'].mean())
    erp_rows.append({
        'ano_publicacao': ANO_PUB,
        'ano_acumulado_ate': ano,
        'n_meses': len(sub),
        'prm_acumulado_decimal': prm_ac,
        'prm_acumulado_pct': prm_ac * 100,
    })
erp_final = np.mean([r['prm_acumulado_decimal'] for r in erp_rows])
erp_rows.append({'ano_publicacao': ANO_PUB, 'ano_acumulado_ate': 'MEDIA_5A', 'n_meses': '',
                 'prm_acumulado_decimal': erp_final, 'prm_acumulado_pct': erp_final * 100})
pd.DataFrame(erp_rows).to_csv(OUT / '04_erp_prm_anual.csv', index=False, sep=';', decimal=',', float_format='%.6f')
print(f"   -> ERP final = {erp_final:.6%}  [ref: 6,8481%]")

# ─────────────────────────────────────────────────────────────
# 05 — EMBI diário janela [2016-2025]
# ─────────────────────────────────────────────────────────────
print("05 EMBI — série diária...")
embi_df = load_embi_diario()
embi_df['data'] = pd.to_datetime(embi_df['data'], errors='coerce')
embi_jan = embi_df[(embi_df['data'] >= '2016-01-01') & (embi_df['data'] <= '2025-12-31')].copy()
embi_jan.to_csv(OUT / '05_embi_diario.csv', index=False, sep=';', decimal=',', float_format='%.6f')
print(f"   -> {len(embi_jan)} linhas")

# ─────────────────────────────────────────────────────────────
# 06 — EMBI média por ano e da janela
# ─────────────────────────────────────────────────────────────
print("06 EMBI — médias anuais...")
embi_anual_rows = []
for ano in range(2016, 2026):
    sub = embi_jan[embi_jan['data'].dt.year == ano]
    if sub.empty:
        continue
    embi_anual_rows.append({
        'ano': ano,
        'n_dias': len(sub),
        'embi_media_pct': float(sub['embi_decimal'].mean()) * 100,
        'embi_media_decimal': float(sub['embi_decimal'].mean()),
        'embi_min_pct': float(sub['embi_decimal'].min()) * 100,
        'embi_max_pct': float(sub['embi_decimal'].max()) * 100,
    })
embi_media_10a = float(embi_jan['embi_decimal'].mean())
embi_anual_rows.append({'ano': 'MEDIA_10A_2016-2025', 'n_dias': len(embi_jan),
                         'embi_media_pct': embi_media_10a * 100, 'embi_media_decimal': embi_media_10a,
                         'embi_min_pct': '', 'embi_max_pct': ''})
pd.DataFrame(embi_anual_rows).to_csv(OUT / '06_embi_media_anual.csv', index=False, sep=';', decimal=',', float_format='%.6f')
print(f"   -> EMBI 10a = {embi_media_10a:.6%}  [ref: 2,765%]")

# ─────────────────────────────────────────────────────────────
# 07 — Beta histórico (fixture ANEEL, 1 linha/janela 2013-2025)
# ─────────────────────────────────────────────────────────────
print("07 Beta — histórico anual (fixture ANEEL)...")
beta_hist = load_beta_historico()
# Adicionar beta_l_brasil calculado via Hamada para conferência
beta_hist['beta_l_recalc_hamada'] = beta_hist.apply(
    lambda r: r['beta_u_eua'] * (1 + (1 - r['T_brasil']) * (r['dv_brasil'] / r['ev_brasil'])),
    axis=1
)
# Últimas 5 janelas (2021-2025) — média que entra no WACC
beta_ultimas5 = beta_hist[beta_hist['ano'].between(2021, 2025)]
beta_l_final = float(beta_ultimas5['beta_l_brasil'].mean())
beta_hist['usada_na_media_5a'] = beta_hist['ano'].between(2021, 2025)
beta_hist.to_csv(OUT / '07_beta_historico.csv', index=False, sep=';', decimal=',', float_format='%.6f')
print(f"   -> beta_l (média 5a) = {beta_l_final:.6f}  [ref: 0,769239]")

# ─────────────────────────────────────────────────────────────
# 08 + 09 — Beta C2: por empresa e retornos semanais (yfinance cache)
# ─────────────────────────────────────────────────────────────
print("08/09 Beta C2 — empresa + retornos semanais...")
CACHE_PRICES  = Path('wacc_regulatorio/data/cache/beta_prices_2019_2026.pkl')
CACHE_MKTCAP  = Path('wacc_regulatorio/data/cache/market_caps.pkl')

if CACHE_PRICES.exists() and CACHE_MKTCAP.exists():
    with open(CACHE_PRICES, 'rb') as f:
        prices_df = pickle.load(f)
    with open(CACHE_MKTCAP, 'rb') as f:
        mktcap_raw = pickle.load(f)

    # Janela Oct-Sep mais recente (2020-10-01 a 2025-09-30)
    start = pd.Timestamp('2020-10-01')
    end   = pd.Timestamp('2025-09-30')
    px = prices_df[(prices_df.index >= start) & (prices_df.index <= end)].copy()

    spxt_col = next((c for c in px.columns if 'SPXT' in c.upper() or '^GSPC' in c.upper() or 'SP500TR' in c.upper()), None)
    if spxt_col:
        rets = (px / px.shift(1)).dropna(how='all')
        tickers = [c for c in rets.columns if c != spxt_col]
        sp500_rets = rets[spxt_col]

        # Reconstrói de_map e dv_book_map
        de_map, dv_book_map = {}, {}
        if isinstance(mktcap_raw, pd.DataFrame):
            for _, row in mktcap_raw.iterrows():
                t = str(row.get('ticker', ''))
                de_map[t]      = float(row.get('de_ratio', 0))
                dv_book_map[t] = float(row.get('dv_book', 0))

        # Calcular por empresa
        empresa_rows = []
        for t in tickers:
            col = rets[[spxt_col, t]].dropna()
            if len(col) < 50:
                continue
            x = col[spxt_col].values
            y = col[t].values
            slope, intercept, rval, pval, stderr = linregress(x, y)
            cov  = float(np.cov(x, y, ddof=1)[0, 1])
            var  = float(np.var(x, ddof=1))
            de   = de_map.get(t, 0.6605)
            dv_b = dv_book_map.get(t, 0.0)
            bu   = _hamada_unlever(slope, de, T_IRPJ_CSLL)
            empresa_rows.append({
                'ticker': t,
                'janela_inicio': str(start.date()),
                'janela_fim': str(end.date()),
                'n_semanas': len(col),
                'beta_l_ols': round(slope, 6),
                'alpha_ols': round(intercept, 6),
                'r_squared': round(rval**2, 6),
                'p_value': round(pval, 6),
                'stderr': round(stderr, 6),
                'cov_sp500_semanal': round(cov, 8),
                'var_sp500_semanal': round(var, 8),
                'de_ratio_mktcap': round(de, 6),
                'dv_book': round(dv_b, 6),
                'beta_u_hamada': round(bu, 6),
            })

        # Pesos D/V book (metodologia ANEEL confirmada)
        total_dv = sum(r['dv_book'] for r in empresa_rows)
        for r in empresa_rows:
            r['peso_dv_book_bruto'] = round(r['dv_book'] / total_dv, 6) if total_dv > 0 else 0

        # Cap 50%
        cap = 0.50
        excesso = sum(max(0, r['peso_dv_book_bruto'] - cap) for r in empresa_rows)
        n_abaixo = sum(1 for r in empresa_rows if r['peso_dv_book_bruto'] < cap)
        for r in empresa_rows:
            raw_w = r['peso_dv_book_bruto']
            if raw_w >= cap:
                r['peso_dv_book_final'] = round(cap, 6)
            else:
                r['peso_dv_book_final'] = round(raw_w + (excesso / n_abaixo if n_abaixo > 0 else 0), 6)
        soma = sum(r['peso_dv_book_final'] for r in empresa_rows)
        for r in empresa_rows:
            r['peso_dv_book_final'] = round(r['peso_dv_book_final'] / soma, 6)
            r['contribuicao_beta_u'] = round(r['peso_dv_book_final'] * r['beta_u_hamada'], 6)

        beta_u_c2 = sum(r['contribuicao_beta_u'] for r in empresa_rows)
        empresa_rows.append({
            'ticker': 'TOTAL_PONDERADO', 'janela_inicio': str(start.date()),
            'janela_fim': str(end.date()), 'n_semanas': '', 'beta_l_ols': '',
            'alpha_ols': '', 'r_squared': '', 'p_value': '', 'stderr': '',
            'cov_sp500_semanal': '', 'var_sp500_semanal': '',
            'de_ratio_mktcap': '', 'dv_book': '', 'beta_u_hamada': '',
            'peso_dv_book_bruto': '', 'peso_dv_book_final': round(1.0, 6),
            'contribuicao_beta_u': round(beta_u_c2, 6),
        })

        pd.DataFrame(empresa_rows).to_csv(
            OUT / '08_beta_c2_por_empresa.csv', index=False, sep=';', decimal=',')
        print(f"   -> {len(empresa_rows)-1} empresas  |  beta_u C2 = {beta_u_c2:.6f}  [ref ANEEL: 0,293106]")

        # Retornos semanais por ticker
        rets_out = rets[[spxt_col] + [r['ticker'] for r in empresa_rows if r['ticker'] != 'TOTAL_PONDERADO']].copy()
        rets_out.index.name = 'data'
        rets_out.reset_index().to_csv(
            OUT / '09_beta_c2_retornos_semanais.csv', index=False, sep=';', decimal=',', float_format='%.8f')
        print(f"   -> {len(rets_out)} semanas × {len(rets_out.columns)} colunas")
    else:
        print("   -> spxt_col nao encontrado no cache de precos — 08/09 ignorados")
else:
    print(f"   -> Cache nao encontrado ({CACHE_PRICES}) — 08/09 ignorados")

# ─────────────────────────────────────────────────────────────
# 10 — Kd: 192 debêntures transmissão
# ─────────────────────────────────────────────────────────────
print("10 Kd — debêntures transmissão [2016-2025]...")
deb = load_debentures()
deb['data_emissao'] = pd.to_datetime(deb['data_emissao'], errors='coerce')
deb['data_vencimento'] = pd.to_datetime(deb['data_vencimento'], errors='coerce')
deb_t = deb[
    (deb['area'] == 'T') &
    (deb['data_emissao'] >= '2016-01-01') &
    (deb['data_emissao'] <= '2025-12-31') &
    (deb['taxa_real'].notna())
].copy().sort_values('data_emissao')

deb_t['prazo_anos'] = (deb_t['data_vencimento'] - deb_t['data_emissao']).dt.days / 365.25
deb_t['taxa_real_pct'] = deb_t['taxa_real'] * 100
kd_media = float(deb_t['taxa_real'].mean())
deb_t['zscore'] = (deb_t['taxa_real'] - kd_media) / deb_t['taxa_real'].std()
deb_t.to_csv(OUT / '10_kd_debentures.csv', index=False, sep=';', decimal=',', float_format='%.6f')
print(f"   -> n={len(deb_t)}  Kd_deb = {kd_media:.6%}  [ref: 6,0685%]")

# ─────────────────────────────────────────────────────────────
# 11 — Kd: custo emissão por título individual
# ─────────────────────────────────────────────────────────────
print("11 Kd — custo emissão individual...")
custo_df = load_custo_emissao()
custo_df.to_csv(OUT / '11_kd_custo_emissao.csv', index=False, sep=';', decimal=',', float_format='%.6f')
print(f"   -> {len(custo_df)} linhas")

# ─────────────────────────────────────────────────────────────
# 12 — Kd: custo emissão agregado por período (fixture ANEEL)
# ─────────────────────────────────────────────────────────────
print("12 Kd — custo emissão agregado por período...")
periodos_df = load_custo_emissao_periodos()
periodos_df.to_csv(OUT / '12_kd_custo_emissao_periodos.csv', index=False, sep=';', decimal=',', float_format='%.6f')
custo_2016_2025 = float(periodos_df[periodos_df['periodo'] == '2016-2025']['custo_emissao_agregado'].iloc[0])
kd_ai = kd_media + custo_2016_2025
print(f"   -> Custo emissão [2016-2025] = {custo_2016_2025:.6%}  Kd_ai = {kd_ai:.6%}  [ref: 6,5866%]")

# ─────────────────────────────────────────────────────────────
# 13 — WACC: componentes finais
# ─────────────────────────────────────────────────────────────
print("13 WACC — componentes finais...")
T = T_IRPJ_CSLL

# Pega a linha mais recente do beta_hist para E/V e D/V
beta_ultimas5 = beta_hist[beta_hist['ano'].between(2021, 2025)]
beta_l  = float(beta_ultimas5['beta_l_brasil'].mean())
beta_u  = float(beta_ultimas5['beta_u_eua'].mean())
linha_2025 = beta_hist[beta_hist['ano'] == 2025].iloc[0]
ev = float(linha_2025['ev_brasil'])
dv = float(linha_2025['dv_brasil'])

embi_medias = load_embi_medias()
embi_row = embi_medias[embi_medias['ano_wacc'] == ANO_PUB]
# Prefere valor pré-computado ANEEL (fixtures embi_medias) — mesmo caminho da C1
embi = float(embi_row['embi_media_10a'].iloc[0]) if not embi_row.empty else float(embi_jan['embi_decimal'].mean())

ke_di    = rf_final + beta_l * erp_final
kd_di    = kd_ai * (1 - T)
wacc_di  = ke_di * ev + kd_di * dv
wacc_ai  = wacc_di / (1 - T)

wacc_row = {
    'ano_publicacao': ANO_PUB,
    'rf_decimal': round(rf_final, 6),
    'rf_pct': round(rf_final * 100, 4),
    'erp_decimal': round(erp_final, 6),
    'erp_pct': round(erp_final * 100, 4),
    'embi_decimal': round(embi, 6),
    'embi_pct': round(embi * 100, 4),
    'beta_u': round(beta_u, 6),
    'beta_l': round(beta_l, 6),
    'ev': round(ev, 6),
    'dv': round(dv, 6),
    'de_ratio_br': round(dv / ev, 6),
    'T_irpj_csll': round(T, 4),
    'ke_real_di_decimal': round(ke_di, 6),
    'ke_real_di_pct': round(ke_di * 100, 4),
    'kd_debentures_decimal': round(kd_media, 6),
    'kd_debentures_pct': round(kd_media * 100, 4),
    'kd_custo_emissao_decimal': round(custo_2016_2025, 6),
    'kd_custo_emissao_pct': round(custo_2016_2025 * 100, 4),
    'kd_real_ai_decimal': round(kd_ai, 6),
    'kd_real_ai_pct': round(kd_ai * 100, 4),
    'kd_real_di_decimal': round(kd_di, 6),
    'kd_real_di_pct': round(kd_di * 100, 4),
    'wacc_real_di_decimal': round(wacc_di, 6),
    'wacc_real_di_pct': round(wacc_di * 100, 4),
    'wacc_real_ai_decimal': round(wacc_ai, 6),
    'wacc_real_ai_pct': round(wacc_ai * 100, 4),
    'ref_wacc_ai_pct': 12.1150,
    'delta_wacc_ai_bp': round((wacc_ai - 0.121150) * 10000, 2),
}
pd.DataFrame([wacc_row]).to_csv(OUT / '13_wacc_componentes.csv', index=False, sep=';', decimal=',')
print(f"   -> WACC_ai = {wacc_ai:.4%}  delta = {wacc_row['delta_wacc_ai_bp']:.1f}bp  [ref: 12,1150%]")

# ─────────────────────────────────────────────────────────────
# Sumário
# ─────────────────────────────────────────────────────────────
print()
print("=== Arquivos gerados em data/trilha_calculo/ ===")
for f in sorted(OUT.glob('*.csv')):
    size_kb = f.stat().st_size / 1024
    print(f"  {f.name:<45}  {size_kb:>7.1f} KB")
