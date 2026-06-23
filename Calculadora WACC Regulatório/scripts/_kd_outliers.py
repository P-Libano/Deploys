import sys; sys.path.insert(0, '.')
import warnings; warnings.filterwarnings('ignore')
import pandas as pd
from wacc_regulatorio.data.fixtures import load_debentures

deb = load_debentures()
start = pd.Timestamp('2016-01-01')
end   = pd.Timestamp('2025-12-31')

deb_t = deb[
    (deb['area'] == 'T') &
    (deb['data_emissao'] >= start) &
    (deb['data_emissao'] <= end) &
    (deb['taxa_real'].notna())
].copy()

mean = deb_t['taxa_real'].mean()
std  = deb_t['taxa_real'].std()

print(f"mean={mean:.6f}  std={std:.6f}  limites=[{mean-2*std:.4f}, {mean+2*std:.4f}]")
print()

out = deb_t[abs(deb_t['taxa_real'] - mean) > 2 * std].sort_values('taxa_real', ascending=False)
print(f"Outliers (|taxa_real - mean| > 2*std):  n={len(out)}")
print()
for _, r in out.iterrows():
    zscore = (r['taxa_real'] - mean) / std
    prazo = (r['data_vencimento'] - r['data_emissao']).days / 365.25
    cod = r['codigo']
    em = str(r['data_emissao'])[:10]
    vc = str(r['data_vencimento'])[:10]
    tr = r['taxa_real']
    emp = str(r['empresa'])[:40]
    print(f"  {cod:<10}  emissao={em}  venc={vc}  prazo={prazo:.1f}a  taxa_real={tr:.4%}  z={zscore:+.1f}")
    print(f"             empresa: {emp}")
    print()

print("=== Debêntures com prazo < 1 ano ===")
short = deb_t.copy()
short['prazo_a'] = (short['data_vencimento'] - short['data_emissao']).dt.days / 365.25
curtos = short[short['prazo_a'] < 1.0].sort_values('prazo_a')
for _, r in curtos.iterrows():
    print(f"  {r['codigo']:<10}  emissao={str(r['data_emissao'])[:10]}  venc={str(r['data_vencimento'])[:10]}  prazo={r['prazo_a']:.2f}a  taxa_real={r['taxa_real']:.4%}")
