import sys; sys.path.insert(0, '.')
import warnings; warnings.filterwarnings('ignore')
from wacc_regulatorio.data.fetchers import fetch_beta_prices, fetch_market_caps
from wacc_regulatorio.params.beta import calcular_beta_mktcap_window
from wacc_regulatorio.config import TICKER_SP500
mktcaps = fetch_market_caps()
prices = fetch_beta_prices(start='2019-10-01')
result = calcular_beta_mktcap_window(prices, mktcaps, spxt_col=TICKER_SP500)

print('=== RESULTADO COM PESOS D/V CONTABIL ===')
print(f'beta_u = {result.beta_u:.6f}  (ANEEL: 0.293106)  delta={(result.beta_u-0.293106)*10000:+.0f}bp')
print(f'beta_l = {result.beta_l:.6f}  (diagnostico C2, nao entra no WACC diretamente)')
print()
print('Validando C1...')
from wacc_regulatorio.camada1_replicacao import executar_camada1
c1 = executar_camada1()
delta = abs(c1.wacc_real_antes_impostos - 0.1211) * 10000
print(f'C1 WACC_ai = {c1.wacc_real_antes_impostos*100:.4f}%  delta vs 12.11% = {delta:.1f}bp')
print('C1 validator: PASS' if delta < 5 else 'C1 validator: FAIL')
