"""
Montagem final: Ke + Kd → WACC por segmento.

Fórmula implementada (fiel à planilha ANEEL Despacho 675/2026):
    beta_l  = beta_l_us  (re-alavancado com D/E americano, ver params/beta.py)
    ke_di   = Rf + beta_l * ERP
    kd_di   = Kd_real_ai * (1 - T)
    WACC_di = ke_di * E/V + kd_di * D/V
    WACC_ai = WACC_di / (1 - T)

Nota: O EMBI está implicitamente capturado no beta_l (alavancado com D/E americano
maior). O parâmetro embi é mantido no WACCResult para transparência e uso em Camada 3.
"""
from dataclasses import dataclass


@dataclass
class WACCResult:
    wacc_real_antes_impostos: float
    wacc_real_depois_impostos: float
    ke_real_di: float
    kd_real_ai: float
    kd_real_di: float
    beta_l: float
    beta_u: float
    rf: float
    erp: float
    embi: float
    ev: float
    dv: float
    T: float

    def __str__(self) -> str:
        lines = [
            "=== WACC Regulatório ===",
            f"  Rf              : {self.rf:.4%}",
            f"  ERP             : {self.erp:.4%}",
            f"  EMBI+           : {self.embi:.4%}",
            f"  Beta_u          : {self.beta_u:.4f}",
            f"  Beta_l          : {self.beta_l:.4f}",
            f"  E/V             : {self.ev:.4%}",
            f"  D/V             : {self.dv:.4%}",
            "  ---",
            f"  Ke real d.i.    : {self.ke_real_di:.4%}",
            f"  Kd real a.i.    : {self.kd_real_ai:.4%}",
            f"  Kd real d.i.    : {self.kd_real_di:.4%}",
            "  ---",
            f"  WACC real d.i.  : {self.wacc_real_depois_impostos:.4%}",
            f"  WACC real a.i.  : {self.wacc_real_antes_impostos:.4%}",
        ]
        return "\n".join(lines)


def calcular_wacc(
    rf: float,
    erp: float,
    embi: float,
    beta_l: float,
    beta_u: float,
    ev: float,
    dv: float,
    kd_real_ai: float,
    T: float = 0.34,
) -> WACCResult:
    """
    Calcula o WACC regulatório seguindo a metodologia do Despacho ANEEL 675/2026.

    Args:
        rf: Taxa livre de risco (NTN-B yield real) — decimal
        erp: Prêmio de risco de mercado EUA — decimal
        embi: EMBI+ médio 10 anos — decimal (documentado; implícito no beta_l)
        beta_l: Beta alavancado das utilities americanas (re-alavancado com D/E EUA)
        beta_u: Beta desalavancado (referência, calculado com estrutura brasileira)
        ev: Participação de capital próprio (E/V) — decimal
        dv: Participação de capital de terceiros (D/V) — decimal
        kd_real_ai: Custo de capital de terceiros real antes de impostos — decimal
        T: Alíquota composita IRPJ + CSLL

    Returns:
        WACCResult com todos os componentes
    """
    if abs(ev + dv - 1.0) > 1e-6:
        raise ValueError(f"E/V + D/V deve ser 1.0, recebido {ev + dv:.6f}")

    # Remuneração de capital próprio real depois de impostos
    ke_di = rf + beta_l * erp

    # Remuneração de capital de terceiros real depois de impostos
    kd_di = kd_real_ai * (1.0 - T)

    # WACC depois de impostos
    wacc_di = ke_di * ev + kd_di * dv

    # WACC antes de impostos
    wacc_ai = wacc_di / (1.0 - T)

    return WACCResult(
        wacc_real_antes_impostos=wacc_ai,
        wacc_real_depois_impostos=wacc_di,
        ke_real_di=ke_di,
        kd_real_ai=kd_real_ai,
        kd_real_di=kd_di,
        beta_l=beta_l,
        beta_u=beta_u,
        rf=rf,
        erp=erp,
        embi=embi,
        ev=ev,
        dv=dv,
        T=T,
    )
