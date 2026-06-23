"""Teste integrado das Camadas 1 e 3."""
import sys

print("=== Teste Final: Camadas 1 e 3 ===\n")

# Camada 1
from wacc_regulatorio.camada1_replicacao import executar_camada1
from wacc_regulatorio.validator import validar

r1 = executar_camada1(verbose=False)
ok = validar(r1, verbose=False)
print(f"Camada 1: {'PASS' if ok else 'FAIL'}")
print(f"  WACC_ai = {r1.wacc_real_antes_impostos:.4%}")
print(f"  Ke_di   = {r1.ke_real_di:.4%}")
print(f"  WACC_di = {r1.wacc_real_depois_impostos:.4%}")

# Camada 3
from wacc_regulatorio.camada3_vetor import projetar_vetor_wacc

df = projetar_vetor_wacc(horizonte_anos=30, verbose=False)
print("\nCamada 3:")
print(f"  Linhas        : {len(df)}")
print(f"  Index freq    : {df.index.freq}")
print(f"  NaN presentes : {df.isnull().any().any()}")
print(f"  WACC_ai ano 1 : {df['WACC_antes_impostos'].iloc[0]:.4%}")
delta_bp = (df["WACC_antes_impostos"].iloc[0] - r1.wacc_real_antes_impostos) * 10000
print(f"  Delta vs C1   : {delta_bp:+.1f}bp")
print(f"  fonte_rf OK   : {'fonte_rf' in df.columns}")

# Cenario EMBI choque
print("\nCenario com choque EMBI em 2027:")
df_choque = projetar_vetor_wacc(
    horizonte_anos=5,
    embi_delta={2027: +0.015, 2028: +0.008},
    verbose=False,
)
print(df_choque[["WACC_antes_impostos", "EMBI"]].to_string())

print("\n=== TODOS OS TESTES CONCLUIDOS ===")
