"""Diagnóstico: vencimentos NTN-B em 2025 e última data do fixture."""
import sys; sys.path.insert(0, '.')
import warnings; warnings.filterwarnings('ignore')
import pandas as pd

from wacc_regulatorio.data.fixtures import load_ntnb

ntnb = load_ntnb()
ntnb['data'] = pd.to_datetime(ntnb['data'], errors='coerce')
ntnb['vencimento'] = pd.to_datetime(ntnb['vencimento'], errors='coerce')
ntnb['taxa_compra_manha'] = pd.to_numeric(ntnb['taxa_compra_manha'], errors='coerce')
ntnb['taxa_venda_manha']  = pd.to_numeric(ntnb['taxa_venda_manha'],  errors='coerce')

print(f"Fixture: {ntnb['data'].min().date()} .. {ntnb['data'].max().date()}")
print(f"Total linhas: {len(ntnb)}")
print()

# Vencimentos negociados em 2025 (data em 2025, vencimento > data, filtro ANEEL)
df25 = ntnb[ntnb['data'].dt.year == 2025].copy()
df25 = df25[df25['vencimento'] > df25['data']]
df25 = df25[df25['taxa_compra_manha'].notna() & (df25['taxa_compra_manha'] <= 0.25)]

vctos = (
    df25.groupby('vencimento')
    .agg(
        n_dias=('data', 'count'),
        media_compra=('taxa_compra_manha', 'mean'),
        media_venda=('taxa_venda_manha', 'mean'),
        primeiro=('data', 'min'),
        ultimo=('data', 'max'),
    )
    .reset_index()
    .sort_values('vencimento')
)

print("Vencimentos NTN-B ativos em 2025 no fixture:")
print(f"  {'Vencimento':<12}  {'n_dias':>6}  {'media%':>8}  {'Inicio':>10}  {'Fim':>10}")
for _, r in vctos.iterrows():
    venc = str(r['vencimento'])[:10]
    media = r['media_compra']
    n = int(r['n_dias'])
    p = str(r['primeiro'])[:10]
    u = str(r['ultimo'])[:10]
    print(f"  {venc:<12}  {n:>6}  {media:>8.4%}  {p:>10}  {u:>10}")

# Últimos dias do fixture — quantos dias de pregão em dez/2025
df_dez = ntnb[(ntnb['data'].dt.year == 2025) & (ntnb['data'].dt.month == 12)]
print(f"\nDias de pregão dez/2025 no fixture: {df_dez['data'].nunique()}")
print(f"Ultimo dia: {df_dez['data'].max().date() if not df_dez.empty else 'N/A'}")

# Verificar se existem dias de 2025 com taxa negativa (que a ANEEL inclui mas filtro antigo excluia)
df_neg = ntnb[(ntnb['data'].dt.year.between(2016, 2025)) & (ntnb['taxa_compra_manha'] < 0)]
print(f"\nLinhas com taxa_compra < 0 em 2016-2025: {len(df_neg)}")
if not df_neg.empty:
    print(df_neg[['data','vencimento','taxa_compra_manha']].sort_values('taxa_compra_manha').head(10).to_string(index=False))

# Comparar rf_2025 calculado vs referencia ANEEL por sub-janela de ano de dados
print("\n--- rf por ano de dados dentro da janela 2025 (janela [2016-2025]) ---")
for ano_data in range(2016, 2026):
    sub = ntnb[ntnb['data'].dt.year == ano_data].copy()
    sub = sub[sub['vencimento'] > sub['data']]
    sub = sub[sub['taxa_compra_manha'].notna() & (sub['taxa_compra_manha'] <= 0.25)]
    if sub.empty:
        print(f"  {ano_data}: sem dados")
        continue
    sub['taxa_media'] = sub[['taxa_compra_manha', 'taxa_venda_manha']].mean(axis=1)
    daily = sub.groupby('data')['taxa_media'].mean()
    n_vctos = sub['vencimento'].nunique()
    print(f"  {ano_data}: n_dias={len(daily):>4}  n_vctos={n_vctos:>2}  media={daily.mean():.4%}")
