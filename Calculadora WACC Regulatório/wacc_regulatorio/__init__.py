"""
wacc_regulatorio — Calculadora WACC Regulatório ANEEL (PRORET).

Três camadas funcionais:
    Camada 1: Replicação histórica (âncora de validação)
    Camada 2: WACC corrente implícito (radar de mercado)
    Camada 3: Vetor projetado (horizonte até 30 anos)

Uso rápido:
    from wacc_regulatorio.camada1_replicacao import executar_camada1
    result = executar_camada1()
    print(result)

    from wacc_regulatorio.camada3_vetor import projetar_vetor_wacc
    df = projetar_vetor_wacc(horizonte_anos=30)
"""
from wacc_regulatorio.wacc_calc import WACCResult, calcular_wacc

__all__ = ["WACCResult", "calcular_wacc"]
