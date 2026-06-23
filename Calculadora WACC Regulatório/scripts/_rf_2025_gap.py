"""
Investiga o gap de -0.75bp no rf_2025 (janela [2016-2025]).
Hipóteses:
  H1 — Vencimentos existentes na janela incluindo os que expiraram em 2025
  H2 — Fixture com Dec 31, 2025 (feriado bancário BR, mas ANEEL pode ter incluso)
  H3 — Vencimento 2060 puxa média para baixo vs ANEEL que não o inclui
"""
import sys; sys.path.insert(0, '.')
import warnings; warnings.filterwarnings('ignore')
import pandas as pd
from wacc_regulatorio.data.fixtures import load_ntnb

ntnb = load_ntnb()
ntnb['data'] = pd.to_datetime(ntnb['data'], errors='coerce')
ntnb['vencimento'] = pd.to_datetime(ntnb['vencimento'], errors='coerce')
ntnb['taxa_compra_manha'] = pd.to_numeric(ntnb['taxa_compra_manha'], errors='coerce')
ntnb['taxa_venda_manha']  = pd.to_numeric(ntnb['taxa_venda_manha'],  errors='coerce')

# Todos os vencimentos distintos no fixture
todos_vctos = ntnb['vencimento'].dropna().dt.date.unique()
todos_vctos_sorted = sorted(todos_vctos)
print(f"Todos os vencimentos no fixture ({len(todos_vctos)}):")
for v in todos_vctos_sorted:
    print(f"  {v}")

print()

# H1: há NTN-B que venceu em 2025 (jan-ago)? — esses teriam sido negociados em 2025 no fixture
vctos_2025 = [v for v in todos_vctos_sorted if str(v).startswith('2025')]
print(f"Vencimentos em 2025: {vctos_2025 or 'nenhum'}")

# H3: impacto do NTN-B 2060-08-15 na média 2025
# Cálculo sem 2060
inicio = pd.Timestamp('2016-01-01')
fim = pd.Timestamp('2025-12-31')

df = ntnb[(ntnb['data'] >= inicio) & (ntnb['data'] <= fim)].copy()
df = df[df['vencimento'] > df['data']]
df = df[df['taxa_compra_manha'].notna() & (df['taxa_compra_manha'] <= 0.25)]
df['taxa_media'] = df[['taxa_compra_manha', 'taxa_venda_manha']].mean(axis=1)

rf_com_2060 = df.groupby('data')['taxa_media'].mean().mean()

df_sem2060 = df[df['vencimento'] != pd.Timestamp('2060-08-15')]
rf_sem_2060 = df_sem2060.groupby('data')['taxa_media'].mean().mean()

print(f"\nH3: impacto do NTN-B 2060 na rf_2025 (janela 2016-2025):")
print(f"  Com 2060:   {rf_com_2060:.6%}")
print(f"  Sem 2060:   {rf_sem_2060:.6%}")
print(f"  Delta:      {(rf_sem_2060 - rf_com_2060)*10000:+.2f}bp")

# Quando o 2060 entrou na série
entrada_2060 = ntnb[ntnb['vencimento'] == pd.Timestamp('2060-08-15')]['data'].min()
print(f"  NTN-B 2060 entrou no fixture em: {entrada_2060.date() if pd.notna(entrada_2060) else 'não encontrado'}")

# H2: testar com Dec 31 (caso ANEEL tenha incluso)
print(f"\nH2: fixture tem Dec 31, 2025? {ntnb[ntnb['data'] == pd.Timestamp('2025-12-31')].shape[0]} linhas")

# Comparar quais anos da janela [2016-2025] têm o NTN-B 2060
print(f"\nAnos em que NTN-B 2060 aparece:")
df_2060 = ntnb[ntnb['vencimento'] == pd.Timestamp('2060-08-15')]
for ano_v, grp in df_2060.groupby(df_2060['data'].dt.year):
    print(f"  {ano_v}: {len(grp)} linhas, media={grp['taxa_compra_manha'].mean():.4%}")
