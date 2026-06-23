import sys; sys.path.insert(0,'.')
import warnings; warnings.filterwarnings('ignore')
from wacc_regulatorio.camada2_corrente import executar_camada2

r = executar_camada2()
w = r.wacc
sp = r.snapshot_params

# Kd result vem do kd_cenarios["base"] se existir, senão do snapshot
kr = r.kd_cenarios.get('base') if r.kd_cenarios else None

kd_deb   = kr.kd_debentures if kr else w.kd_real_ai
kd_custo = kr.custo_emissao  if kr else 0.0

print(f"rf={w.rf:.6f}")
print(f"erp={w.erp:.6f}")
print(f"embi={w.embi:.6f}")
print(f"beta_u={w.beta_u:.6f}")
print(f"beta_l={w.beta_l:.6f}")
print(f"ev={w.ev:.6f}")
print(f"dv={w.dv:.6f}")
print(f"ke_real_di={w.ke_real_di:.6f}")
print(f"kd_deb={kd_deb:.6f}")
print(f"kd_custo={kd_custo:.6f}")
print(f"kd_real_ai={w.kd_real_ai:.6f}")
print(f"wacc_di={w.wacc_real_depois_impostos:.6f}")
print(f"wacc_ai={w.wacc_real_antes_impostos:.6f}")
print(f"fonte_kd={sp.get('kd_fonte','?')}")
print(f"fonte_rf={sp.get('rf_fonte','?')}")
print(f"fonte_erp={sp.get('erp_fonte','?')}")
print(f"fonte_embi={sp.get('embi_fonte','?')}")
print(f"fonte_beta={sp.get('beta_fonte','?')}")
