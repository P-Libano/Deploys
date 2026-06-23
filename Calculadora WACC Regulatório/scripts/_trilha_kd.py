"""Trilha de cálculo do Kd — debêntures de transmissão, janela 2016-2025."""
import sys; sys.path.insert(0, '.')
import warnings; warnings.filterwarnings('ignore')
import pandas as pd
from wacc_regulatorio.data.fixtures import load_debentures, load_custo_emissao, load_custo_emissao_periodos

deb = load_debentures()
custo = load_custo_emissao()
periodos = load_custo_emissao_periodos()

start = pd.Timestamp('2016-01-01')
end   = pd.Timestamp('2025-12-31')

deb_t = deb[
    (deb['area'] == 'T') &
    (deb['data_emissao'] >= start) &
    (deb['data_emissao'] <= end) &
    (deb['taxa_real'].notna())
].copy().sort_values('data_emissao')

print(f"=== TRILHA Kd — Transmissão, janela 2016-2025 (n={len(deb_t)}) ===\n")
print(f"{'#':<4} {'Codigo':<10} {'Empresa':<45} {'Emissao':>10}  {'Venc':>10}  {'Idx':<5}  {'Nom%':>8}  {'BEI%':>8}  {'Real%':>8}")
print("-" * 125)

for i, (_, r) in enumerate(deb_t.iterrows(), 1):
    tn = f"{r['taxa_nominal_pct']:.4f}" if pd.notna(r['taxa_nominal_pct']) else "      -"
    ii = f"{r['inflacao_implicita']:.4f}" if pd.notna(r['inflacao_implicita']) else "      -"
    emp = str(r['empresa'])[:44]
    print(f"{i:<4} {r['codigo']:<10} {emp:<45} {str(r['data_emissao'])[:10]}  {str(r['data_vencimento'])[:10]}  {r['indice']:<5}  {tn:>8}  {ii:>8}  {r['taxa_real']:>8.4%}")

print()
print(f"  Media simples (Kd_deb) = {deb_t['taxa_real'].mean():.6%}   [ref ANEEL: 6.0685%]")
print(f"  Min = {deb_t['taxa_real'].min():.4%}  |  Max = {deb_t['taxa_real'].max():.4%}  |  Std = {deb_t['taxa_real'].std():.4%}")
print()

# Custo de emissao
custo_c1 = 0.005181
print(f"  Custo emissao (IPCA+DI, periodo 2016-2025) = {custo_c1:.4%}  [ref ANEEL: 0.5181%]")
print(f"  Kd_real_ai = {deb_t['taxa_real'].mean() + custo_c1:.6%}  [ref ANEEL: 6.5866%]")
print()

# Por indice
print("=== Por indexador ===")
for idx, grp in deb_t.groupby('indice'):
    print(f"  {idx}: n={len(grp)}  media={grp['taxa_real'].mean():.4%}  min={grp['taxa_real'].min():.4%}  max={grp['taxa_real'].max():.4%}")

print()
print("=== Por ano de emissão ===")
for ano_val, grp in deb_t.groupby('ano'):
    print(f"  {ano_val}: n={len(grp):>3}  media={grp['taxa_real'].mean():.4%}  min={grp['taxa_real'].min():.4%}  max={grp['taxa_real'].max():.4%}")

# Outliers
print()
mean = deb_t['taxa_real'].mean()
std  = deb_t['taxa_real'].std()
outliers = deb_t[abs(deb_t['taxa_real'] - mean) > 2 * std]
if not outliers.empty:
    print(f"=== Outliers (|taxa_real - media| > 2σ, σ={std:.4%}) ===")
    for _, r in outliers.iterrows():
        print(f"  {r['codigo']:<10} {str(r['empresa'])[:45]:<45} {r['data_emissao'].date()}  taxa_real={r['taxa_real']:.4%}  ({(r['taxa_real']-mean)/std:+.1f}σ)")
else:
    print("  Sem outliers detectados.")
