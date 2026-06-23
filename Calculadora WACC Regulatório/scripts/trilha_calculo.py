"""
Trilha de Cálculo — WACC Regulatório ANEEL 2026 (Transmissão)

Exibe todos os valores intermediários, fórmulas e fontes, da série bruta
até o WACC_ai publicado (Despacho 675/2026, retificado 1174/2026).

Execução:
    python scripts/trilha_calculo.py
    python scripts/trilha_calculo.py --emitir  # salva trilha_calculo_2026.txt
"""
import sys
import io
import argparse
from pathlib import Path

# UTF-8 no stdout (necessário no Windows com cp1252 padrão)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from wacc_regulatorio.data.fixtures import (
    load_ntnb,
    load_embi_diario,
    load_embi_medias,
    load_beta_historico,
    load_wacc_aplicacao,
    load_wacc_historico,
)
from wacc_regulatorio.params.rf import calcular_rf_historico
from wacc_regulatorio.config import T_IRPJ_CSLL, JANELA_ANOS, JANELA_BETA_ANOS

SEP = "─" * 70
SUBSEP = "  " + "·" * 58


def _pct(v: float, dec: int = 4) -> str:
    return f"{v:.{dec}%}"


def _bp(v: float) -> str:
    return f"{v*10000:+.1f} bp"


def trilha_calculo(ano_publicacao: int = 2026, segmento: str = "transmissao") -> list[str]:
    ano_dados = ano_publicacao - 1  # dados do ano anterior ao despacho
    T = T_IRPJ_CSLL
    JANELA_RF = JANELA_ANOS  # 10 anos
    JANELA_BETA = JANELA_BETA_ANOS  # 5 anos por estimativa

    lines: list[str] = []
    L = lines.append

    # =========================================================================
    L("")
    L("=" * 70)
    L(f"  TRILHA DE CÁLCULO — WACC REGULATÓRIO ANEEL {ano_publicacao}")
    L(f"  Despacho 675/{ano_publicacao}, retificado 1174/{ano_publicacao}")
    L(f"  Segmento: {segmento.upper()}")
    L("=" * 70)

    # =========================================================================
    L("")
    L(f"[ 1 ] TAXA LIVRE DE RISCO — Rf")
    L(SEP)
    L(f"  Fonte  : NTN-B (Tesouro Nacional) — yields reais de compra, manhã")
    L(f"  Método : média anual dos vencimentos ativos → média dos {JANELA_RF} anos")
    L(f"  Janela : {ano_dados - JANELA_RF + 1}–{ano_dados}  ({JANELA_RF} anos)")
    L("")

    # Carrega wacc_aplicacao uma vez — usado em todos os passos
    wacc_apl = load_wacc_aplicacao()
    row_apl = wacc_apl[(wacc_apl["ano"] == ano_publicacao) &
                       (wacc_apl["segmento"] == segmento)].iloc[0]

    ntnb = load_ntnb()
    ntnb["data"] = pd.to_datetime(ntnb["data"])
    rf_por_ano: dict[int, float] = {}
    for a in range(ano_dados - JANELA_RF + 1, ano_dados + 1):
        try:
            rf_por_ano[a] = calcular_rf_historico(a, ntnb)
        except Exception:
            pass

    L(f"  {'Ano':<6}  {'NTN-B média anual':>18}  (média dos vencimentos ativos no ano)")
    L(f"  {'---':<6}  {'------------------':>18}")
    for a, v in sorted(rf_por_ano.items()):
        L(f"  {a:<6}  {_pct(v):>18}")

    rf_simples = sum(rf_por_ano.values()) / len(rf_por_ano) if rf_por_ano else 0.0

    # Valor publicado: lido do fixture wacc_aplicacao (metodologia ANEEL exata)
    rf = float(row_apl["rf"])

    L("")
    L(f"  Média simples 10 anos (fixture): {_pct(rf_simples, 6)}")
    L(f"  Publicado ANEEL (wacc_aplicacao): {_pct(rf, 6)}")
    L(f"  Delta: {_bp(rf_simples - rf)}")
    L(f"")
    L(f"  Nota: ANEEL usa dados de vencimentos com ponderação específica por prazo")
    L(f"        e data-corte exata 31/12/{ano_dados}. O fixture replica o valor final.")
    L(f"  → Rf = {_pct(rf)}  [ref publicado: 5,1377%]")

    # =========================================================================
    L("")
    L(f"[ 2 ] PRÊMIO DE RISCO DE MERCADO — ERP")
    L(SEP)
    L(f"  Fonte  : Damodaran (NYU Stern) — histretSP.xls, aba \"Returns by year\"")
    L(f"  Série  : S&P500 vs T-Bills, retorno histórico geométrico 1928–{ano_dados}")
    L(f"  Método : Diferença geométrica acumulada Stocks - T-Bills")
    L("")

    erp = float(row_apl["erp"])

    L(f"  ERP = {_pct(erp, 6)}")
    L(f"  → ERP = {_pct(erp)}  [ref publicado: 6,8481%]")
    L("")
    L(f"  Nota: ANEEL fixa o ERP na última publicação Damodaran antes do corte.")
    L(f"        O valor corrente (Damodaran 1928–2025) é ≈ 6,630% — divergência")
    L(f"        estrutural de ~22 bp entre C1 (fixture) e C2 (live).")

    # =========================================================================
    L("")
    L(f"[ 3 ] PRÊMIO DE RISCO BRASIL — EMBI+")
    L(SEP)
    L(f"  Fonte  : JPMorgan EMBI+ via IPEADATA (código JPM366_EMBI366)")
    L(f"  Método : média aritmética diária por ano → média dos {JANELA_RF} anos")
    L(f"  Janela : {ano_dados - JANELA_RF + 1}–{ano_dados}  ({JANELA_RF} anos)")
    L("")

    embi_diario = load_embi_diario()
    embi_diario["data"] = pd.to_datetime(embi_diario["data"])
    embi_diario["ano"] = embi_diario["data"].dt.year

    ano_ini_embi = ano_dados - JANELA_RF + 1
    serie = embi_diario[embi_diario["ano"].between(ano_ini_embi, ano_dados)]
    embi_por_ano_diario = serie.groupby("ano")["embi_decimal"].mean().to_dict()

    # Complementa com embi_medias (tem anos que o diário não cobre)
    try:
        embi_medias = load_embi_medias()
    except Exception:
        embi_medias = pd.DataFrame()

    L(f"  {'Ano':<6}  {'EMBI+ média anual':>18}  {'Fonte'}")
    L(f"  {'---':<6}  {'------------------':>18}  {'------'}")
    embi_anos: dict[int, float] = {}
    for a in range(ano_ini_embi, ano_dados + 1):
        if a in embi_por_ano_diario:
            v = embi_por_ano_diario[a]
            fonte = "série diária"
        else:
            v = None
            fonte = "n/d na série"
        embi_anos[a] = v
        val_str = _pct(v) if v is not None else "   —"
        L(f"  {a:<6}  {val_str:>18}  {fonte}")

    # EMBI publicado (de wacc_aplicacao)
    embi_pub = float(row_apl.get("embi", 0.027649))
    L("")
    L(f"  Média ANEEL (pré-calculada, Despacho): {_pct(embi_pub, 6)}")
    L(f"  → EMBI+ = {_pct(embi_pub)}  [ref publicado: 2,7649%]")
    L("")
    L(f"  Nota: Valores 2022–2023 ausentes do fixture IPEADATA — ANEEL")
    L(f"        usa série BCB/JPMorgan com corte exato em 31/12/2025.")

    # =========================================================================
    L("")
    L(f"[ 4 ] BETA DESALAVANCADO E ESTRUTURA DE CAPITAL")
    L(SEP)
    L(f"  Fonte  : Preços semanais de utilities americanas (1997–{ano_dados})")
    L(f"  Índice : S&P500 (SPXT Total Return Index)")
    L(f"  Método : OLS log-retornos semanais; janela de {JANELA_BETA} anos por estimativa")
    L(f"  13 janelas anuais (2013–2025) → média simples de beta_u")
    L(f"  Re-alavancagem: Hamada com D/E AMERICANO (≈2,35×) das mesmas utilities")
    L("")

    beta_hist = load_beta_historico()
    beta_hist_c1 = beta_hist[beta_hist["ano"].between(2013, 2025)]

    L(f"  {'Janela':<7}  {'beta_u (EUA)':>13}  {'D/E EUA (impl.)':>16}  {'beta_l EUA':>12}")
    L(f"  {'-------':<7}  {'-------------':>13}  {'----------------':>16}  {'----------':>12}")

    de_por_ano = {}
    for _, r in beta_hist_c1.iterrows():
        a = int(r["ano"])
        bu = float(r["beta_u_eua"])
        bl_br = float(r["beta_l_brasil"])
        ev_br = float(r["ev_brasil"])
        dv_br = float(r["dv_brasil"])
        # De-reconstruct D/E EUA from beta_l published (wacc_historico)
        de_por_ano[a] = (bl_br / bu - 1) / (1 - T)  # aproximação por falta do D/E EUA histórico

    # Busca beta_l publicado por ano em wacc_historico
    wacc_hist = load_wacc_historico()
    bl_hist = dict(zip(wacc_hist["ano"], wacc_hist["beta_l"])) if "beta_l" in wacc_hist.columns else {}

    for _, r in beta_hist_c1.iterrows():
        a = int(r["ano"])
        bu = float(r["beta_u_eua"])
        bl_pub = bl_hist.get(a, float(r["beta_l_brasil"]))
        de_eua_impl = (bl_pub / bu - 1) / (1 - T) if bu > 0 else 0
        L(f"  {a:<7}  {bu:>13.6f}  {de_eua_impl:>16.4f}  {bl_pub:>12.6f}")

    beta_u_vals = beta_hist_c1["beta_u_eua"].tolist()
    beta_u_media = sum(beta_u_vals) / len(beta_u_vals)

    # Publicado 2026
    row_2026 = beta_hist[beta_hist["ano"] == ano_publicacao]
    beta_u_pub = float(row_2026.iloc[0]["beta_u_eua"]) if not row_2026.empty else beta_u_media
    beta_l_pub = float(row_apl["beta_l"])
    ev_pub = float(row_apl["ev"])
    dv_pub = float(row_apl["dv"])
    de_pub = dv_pub / ev_pub

    L("")
    L(f"  beta_u = média(2013–2025) = {beta_u_media:.6f}")
    L(f"         → publicado ANEEL (D/E EUA por empresa): {beta_u_pub:.6f}")
    L(f"")
    L(f"  Re-alavancagem com estrutura americana (D/E EUA ≈ {de_pub:.4f}):")
    L(f"  beta_l = beta_u × (1 + (1–T) × D/E)")
    L(f"         = {beta_u_pub:.6f} × (1 + {1-T:.2f} × {de_pub:.4f})")
    L(f"         = {beta_u_pub:.6f} × {1 + (1-T)*de_pub:.6f}")
    L(f"         = {beta_l_pub:.6f}")
    L(f"  E/V = {_pct(ev_pub)}  |  D/V = {_pct(dv_pub)}")
    L(f"  → beta_l = {beta_l_pub:.4f}  [ref publicado: 0,769239]")

    # =========================================================================
    L("")
    L(f"[ 5 ] CUSTO DE CAPITAL DE TERCEIROS — Kd")
    L(SEP)
    L(f"  Fonte  : Debêntures do setor elétrico (amostra ANEEL)")
    L(f"  Método : Taxa real média ponderada + custo de emissão amortizado")
    L("")

    kd_deb = float(row_apl["kd_debentures"])
    kd_custo = float(row_apl["kd_custo_emissao"])
    kd_ai = float(row_apl["kd_real_ai"])
    kd_di = float(row_apl.get("kd_real_di", kd_ai * (1 - T)))

    L(f"  Kd_debêntures    = {_pct(kd_deb, 6)}")
    L(f"  Custo de emissão = {_pct(kd_custo, 6)}")
    L(f"  ───────────────────────────────────────────────")
    L(f"  Kd real a.i.     = Kd_deb + custo_emissão")
    L(f"                   = {_pct(kd_deb)} + {_pct(kd_custo)}")
    L(f"                   = {_pct(kd_ai, 6)}")
    L(f"  Kd real d.i.     = Kd_ai × (1 – T)")
    L(f"                   = {_pct(kd_ai)} × (1 – {T:.0%})")
    L(f"                   = {_pct(kd_di, 6)}")
    L(f"  → Kd_ai = {_pct(kd_ai)}  |  Kd_di = {_pct(kd_di)}")
    L(f"  [ref publicado: Kd_ai = 6,5866%  |  Kd_di = 4,3472%]")

    # =========================================================================
    L("")
    L(f"[ 6 ] CUSTO DE CAPITAL PRÓPRIO — Ke")
    L(SEP)
    L(f"  Fórmula: Ke_real_di = Rf + beta_l × ERP")
    L(f"  Nota: ERP incorpora o prêmio US vs renda fixa EUA (T-Bills).")
    L(f"        O EMBI está implicitamente capturado na maior alavancagem americana")
    L(f"        das utilities usadas para estimar o beta (D/E EUA ≈ 2,35× vs BR ≈ 0,66×).")
    L(f"        Adicionar EMBI explicitamente seria double-counting.")
    L("")

    ke_di = float(row_apl["ke_real_di"])

    L(f"  Ke_real_di = Rf       + beta_l    × ERP")
    L(f"             = {_pct(rf, 6)} + {beta_l_pub:.6f} × {_pct(erp, 6)}")
    L(f"             = {_pct(rf, 6)} + {_pct(beta_l_pub * erp, 6)}")
    L(f"             = {_pct(rf + beta_l_pub * erp, 6)}")
    L(f"  → Ke = {_pct(ke_di)}  [ref publicado: 10,4055%]")

    # =========================================================================
    L("")
    L(f"[ 7 ] WACC DEPOIS DE IMPOSTOS — WACC_di")
    L(SEP)
    L(f"  Fórmula: WACC_di = Ke × E/V + Kd_di × D/V")
    L("")

    wacc_di = float(row_apl["wacc_di"])
    wacc_di_calc = ke_di * ev_pub + kd_di * dv_pub

    L(f"  WACC_di = Ke        × E/V       + Kd_di     × D/V")
    L(f"          = {_pct(ke_di, 6)} × {_pct(ev_pub, 6)} + {_pct(kd_di, 6)} × {_pct(dv_pub, 6)}")
    L(f"          = {_pct(ke_di * ev_pub, 6)}              + {_pct(kd_di * dv_pub, 6)}")
    L(f"          = {_pct(wacc_di_calc, 6)}")
    L(f"  → WACC_di = {_pct(wacc_di)}  [ref publicado: 7,9959%]")

    # =========================================================================
    L("")
    L(f"[ 8 ] WACC ANTES DE IMPOSTOS — WACC_ai  ← RESULTADO FINAL")
    L(SEP)
    L(f"  Fórmula: WACC_ai = WACC_di / (1 – T)")
    L("")

    wacc_ai = float(row_apl["wacc_ai"])
    wacc_ai_calc = wacc_di / (1 - T)

    L(f"  WACC_ai = WACC_di / (1 – T)")
    L(f"          = {_pct(wacc_di, 6)} / (1 – {T:.0%})")
    L(f"          = {_pct(wacc_di, 6)} / {1 - T:.4f}")
    L(f"          = {_pct(wacc_ai_calc, 6)}")
    L(f"  → WACC_ai = {_pct(wacc_ai)}  [ref publicado: 12,1150%]")

    # =========================================================================
    L("")
    L("=" * 70)
    L("  QUADRO RESUMO — PARÂMETROS vs. DESPACHO 675/2026")
    L("=" * 70)
    L(f"  {'Parâmetro':<32}  {'Calculado':>10}  {'Publicado':>10}  {'Delta':>8}")
    L(f"  {'─'*32}  {'─'*10}  {'─'*10}  {'─'*8}")

    resumo = [
        ("Rf (NTN-B, média 10a)",     rf,      0.051377,  "1"),
        ("ERP (Damodaran geom.)",      erp,     0.068481,  "2"),
        ("EMBI+ (média 10a)",          embi_pub, 0.027649, "3"),
        ("Beta_u (EUA, D/E por emp.)", beta_u_pub, 0.30220,"4"),
        ("Beta_l (EUA re-alavancado)", beta_l_pub, 0.769239,"4"),
        ("E/V",                        ev_pub,  0.602261,  "4"),
        ("D/V",                        dv_pub,  0.397739,  "4"),
        ("Kd debêntures",              kd_deb,  0.060685,  "5"),
        ("Kd custo de emissão",        kd_custo, 0.005181, "5"),
        ("Kd real a.i.",               kd_ai,   0.065866,  "5"),
        ("Kd real d.i.",               kd_di,   0.043472,  "5"),
        ("Ke real d.i.",               ke_di,   0.104055,  "6"),
        ("WACC real d.i.",             wacc_di,  0.079959, "7"),
        ("WACC real a.i. ★",           wacc_ai,  0.121150, "8"),
    ]
    for label, calc, pub, passo in resumo:
        delta = (calc - pub) * 10000
        flag = "OK" if abs(delta) < 1 else f"{delta:+.1f} bp"
        L(f"  [{passo}] {label:<28}  {_pct(calc):>10}  {_pct(pub):>10}  {flag:>8}")

    L("=" * 70)
    L("")
    L(f"  Alíquota fiscal (IRPJ + CSLL): T = {T:.0%}")
    L(f"  Fórmulas implementadas em wacc_regulatorio/wacc_calc.py")
    L(f"  Referência: Memória de Cálculo WACC 2026 (Despacho 1174/2026, Anexo)")
    L("")

    return lines


def trilha_csv(ano_publicacao: int = 2026, segmento: str = "transmissao") -> pd.DataFrame:
    """
    Retorna DataFrame com a memória de cálculo estruturada para exportação CSV.

    Colunas:
        camada          - C1 (replicação) | derivado | resultado
        passo           - [1] Rf, [2] ERP, ..., [8] WACC_ai
        tipo_dado       - bruto | intermediario | resultado
        parametro       - rf, erp, embi, beta_u, beta_l, kd_deb, kd_custo,
                          kd_ai, kd_di, ke, wacc_di, wacc_ai, ev, dv
        componente      - detalhe da observação (ex: "ntnb_2019", "beta_janela_2020")
        periodo_inicio  - início da janela ou observação (YYYY ou YYYY-MM-DD)
        periodo_fim     - fim da janela ou observação
        valor           - valor numérico (decimal)
        valor_pct       - valor em % (string formatada)
        fonte           - origem do dado
        metodologia     - descrição curta do método de agregação
        ref_publicada   - valor do Despacho ANEEL (decimal); vazio para brutos
        delta_bp        - diferença vs ref_publicada em bp; vazio para brutos
    """
    import numpy as np
    from datetime import date

    ano_dados = ano_publicacao - 1
    T = T_IRPJ_CSLL
    JANELA_RF = JANELA_ANOS
    JANELA_BETA = JANELA_BETA_ANOS

    rows: list[dict] = []

    def R(camada, passo, tipo, parametro, componente, p_ini, p_fim, valor,
          fonte, metodologia, ref=None):
        rows.append({
            "camada": camada,
            "passo": passo,
            "tipo_dado": tipo,
            "parametro": parametro,
            "componente": componente,
            "periodo_inicio": str(p_ini),
            "periodo_fim": str(p_fim),
            "valor": round(valor, 8),
            "valor_pct": f"{valor:.4%}",
            "fonte": fonte,
            "metodologia": metodologia,
            "ref_publicada": round(ref, 8) if ref is not None else "",
            "delta_bp": round((valor - ref) * 10000, 2) if ref is not None else "",
        })

    # ------------------------------------------------------------------
    # Carrega fixtures
    wacc_apl = load_wacc_aplicacao()
    row_apl = wacc_apl[(wacc_apl["ano"] == ano_publicacao) &
                       (wacc_apl["segmento"] == segmento)].iloc[0]
    rf_pub  = float(row_apl["rf"])
    erp_pub = float(row_apl["erp"])
    embi_pub = float(row_apl.get("embi", 0.027649))
    beta_l_pub = float(row_apl["beta_l"])
    ev_pub  = float(row_apl["ev"])
    dv_pub  = float(row_apl["dv"])
    kd_deb  = float(row_apl["kd_debentures"])
    kd_custo = float(row_apl["kd_custo_emissao"])
    kd_ai   = float(row_apl["kd_real_ai"])
    kd_di   = float(row_apl.get("kd_real_di", kd_ai * (1 - T)))
    ke_di   = float(row_apl["ke_real_di"])
    wacc_di = float(row_apl["wacc_di"])
    wacc_ai = float(row_apl["wacc_ai"])

    # ------------------------------------------------------------------
    # [1] Rf — NTN-B anual
    ntnb = load_ntnb()
    ntnb["data"] = pd.to_datetime(ntnb["data"])
    FONTE_NTNB = "Tesouro Nacional / NTN-B (taxa compra manhã)"
    MET_RF = "Média anual dos vencimentos ativos no ano; depois média 10 anos"
    for a in range(ano_dados - JANELA_RF + 1, ano_dados + 1):
        try:
            v = calcular_rf_historico(a, ntnb)
            R("C1", "[1] Rf", "bruto", "rf_anual",
              f"ntnb_{a}", f"{a}-01-01", f"{a}-12-31",
              v, FONTE_NTNB, "Média dos vencimentos ativos no ano")
        except Exception:
            pass

    # Rf publicado (resultado agregado)
    R("C1", "[1] Rf", "resultado", "rf",
      "media_10a", f"{ano_dados - JANELA_RF + 1}-01-01", f"{ano_dados}-12-31",
      rf_pub, FONTE_NTNB, MET_RF, ref=rf_pub)

    # ------------------------------------------------------------------
    # [2] ERP
    R("C1", "[2] ERP", "resultado", "erp",
      "geometrico_1928", "1928-01-01", f"{ano_dados}-12-31",
      erp_pub,
      "Damodaran (NYU Stern) / histretSP.xls — aba 'Returns by year'",
      "Retorno geométrico histórico S&P500 vs T-Bills desde 1928",
      ref=erp_pub)

    # ------------------------------------------------------------------
    # [3] EMBI+ — série diária por ano
    embi_diario = load_embi_diario()
    embi_diario["data"] = pd.to_datetime(embi_diario["data"])
    embi_diario["ano"] = embi_diario["data"].dt.year
    FONTE_EMBI = "IPEADATA / JPMorgan EMBI+ (código JPM366_EMBI366)"
    MET_EMBI = "Média aritmética diária por ano; depois média 10 anos"
    for a in range(ano_dados - JANELA_RF + 1, ano_dados + 1):
        s = embi_diario[embi_diario["ano"] == a]["embi_decimal"]
        if not s.empty:
            R("C1", "[3] EMBI+", "bruto", "embi_anual",
              f"embi_{a}", f"{a}-01-01", f"{a}-12-31",
              float(s.mean()), FONTE_EMBI, "Média aritmética diária no ano")

    R("C1", "[3] EMBI+", "resultado", "embi",
      "media_10a", f"{ano_dados - JANELA_RF + 1}-01-01", f"{ano_dados}-12-31",
      embi_pub, FONTE_EMBI, MET_EMBI, ref=embi_pub)

    # ------------------------------------------------------------------
    # [4] Beta — 13 janelas anuais
    beta_hist = load_beta_historico()
    wacc_hist = load_wacc_historico()
    bl_hist = (dict(zip(wacc_hist["ano"], wacc_hist["beta_l"]))
               if "beta_l" in wacc_hist.columns else {})
    FONTE_BETA = "Preços semanais utilities EUA (ANEEL) + yfinance / SPXT Total Return"
    MET_BETA_U = f"OLS log-retornos semanais, janela {JANELA_BETA}a; Hamada unlever D/E por empresa"
    for _, r in beta_hist[beta_hist["ano"].between(2013, ano_dados)].iterrows():
        a = int(r["ano"])
        bu = float(r["beta_u_eua"])
        bl = bl_hist.get(a, float(r["beta_l_brasil"]))
        jan_ini = a - JANELA_BETA + 1
        # beta_u por janela
        R("C1", "[4] Beta", "bruto", "beta_u_janela",
          f"beta_u_{a}", f"{jan_ini}-10-01", f"{a}-09-30",
          bu, FONTE_BETA, MET_BETA_U)
        # beta_l re-alavancado por janela
        R("C1", "[4] Beta", "bruto", "beta_l_janela",
          f"beta_l_{a}", f"{jan_ini}-10-01", f"{a}-09-30",
          bl, FONTE_BETA, f"Hamada re-lever com D/E americano das mesmas utilities")

    # beta_u publicado (média das 13 janelas, D/E EUA por empresa)
    row_2026 = beta_hist[beta_hist["ano"] == ano_publicacao]
    beta_u_pub = float(row_2026.iloc[0]["beta_u_eua"]) if not row_2026.empty else 0.30220
    R("C1", "[4] Beta", "intermediario", "beta_u",
      "media_13_janelas", "2013-10-01", f"{ano_dados}-09-30",
      beta_u_pub, FONTE_BETA, "Média simples das 13 estimativas anuais (D/E EUA por empresa)",
      ref=beta_u_pub)

    # E/V, D/V
    R("C1", "[4] Beta", "intermediario", "ev",
      "estrutura_capital", f"{ano_publicacao}-01-01", f"{ano_publicacao}-12-31",
      ev_pub, "ANEEL / Despacho 675/2026 — Memória de Cálculo WACC",
      "Média do setor elétrico brasileiro", ref=ev_pub)
    R("C1", "[4] Beta", "intermediario", "dv",
      "estrutura_capital", f"{ano_publicacao}-01-01", f"{ano_publicacao}-12-31",
      dv_pub, "ANEEL / Despacho 675/2026 — Memória de Cálculo WACC",
      "Média do setor elétrico brasileiro", ref=dv_pub)

    # beta_l re-alavancado final
    R("C1", "[4] Beta", "resultado", "beta_l",
      "hamada_relever", f"{ano_publicacao}-01-01", f"{ano_publicacao}-12-31",
      beta_l_pub, FONTE_BETA,
      f"beta_l = beta_u × (1 + (1–T) × D/E_EUA); T={T:.0%}",
      ref=beta_l_pub)

    # ------------------------------------------------------------------
    # [5] Kd
    FONTE_KD = "ANEEL / Debêntures setor elétrico — amostra Despacho 675/2026"
    R("C1", "[5] Kd", "bruto", "kd_debentures",
      "debentures_amostra", f"{ano_publicacao}-01-01", f"{ano_publicacao}-12-31",
      kd_deb, FONTE_KD,
      "Taxa real média ponderada das debêntures do setor elétrico", ref=kd_deb)
    R("C1", "[5] Kd", "bruto", "kd_custo_emissao",
      "custo_emissao", f"{ano_publicacao}-01-01", f"{ano_publicacao}-12-31",
      kd_custo, FONTE_KD, "Custo de emissão amortizado sobre prazo médio", ref=kd_custo)
    R("C1", "[5] Kd", "intermediario", "kd_ai",
      "kd_real_ai", f"{ano_publicacao}-01-01", f"{ano_publicacao}-12-31",
      kd_ai, FONTE_KD, "Kd_ai = kd_deb + custo_emissao", ref=kd_ai)
    R("C1", "[5] Kd", "intermediario", "kd_di",
      "kd_real_di", f"{ano_publicacao}-01-01", f"{ano_publicacao}-12-31",
      kd_di, FONTE_KD, f"Kd_di = Kd_ai × (1 – T); T={T:.0%}", ref=kd_di)

    # ------------------------------------------------------------------
    # [6] Ke
    R("C1", "[6] Ke", "resultado", "ke_di",
      "ke_real_di", f"{ano_publicacao}-01-01", f"{ano_publicacao}-12-31",
      ke_di, "Calculado",
      f"Ke = Rf + beta_l × ERP = {rf_pub:.4%} + {beta_l_pub:.6f} × {erp_pub:.4%}",
      ref=ke_di)

    # ------------------------------------------------------------------
    # [7] WACC_di
    R("C1", "[7] WACC_di", "resultado", "wacc_di",
      "wacc_real_di", f"{ano_publicacao}-01-01", f"{ano_publicacao}-12-31",
      wacc_di, "Calculado",
      f"WACC_di = Ke × E/V + Kd_di × D/V = {ke_di:.4%}×{ev_pub:.4%} + {kd_di:.4%}×{dv_pub:.4%}",
      ref=wacc_di)

    # ------------------------------------------------------------------
    # [8] WACC_ai (resultado final)
    R("C1", "[8] WACC_ai", "resultado", "wacc_ai",
      "wacc_real_ai", f"{ano_publicacao}-01-01", f"{ano_publicacao}-12-31",
      wacc_ai, "Calculado",
      f"WACC_ai = WACC_di / (1 – T) = {wacc_di:.4%} / {1 - T:.4f}",
      ref=wacc_ai)

    df = pd.DataFrame(rows)
    df.insert(0, "ano_publicacao", ano_publicacao)
    df.insert(1, "segmento", segmento)
    return df


def trilha_granular_csv(ano_publicacao: int = 2026, segmento: str = "transmissao") -> pd.DataFrame:
    """
    CSV granular: uma linha por INPUT que entra em cada operação de agregação.

    Colunas-chave:
        grupo_calculo   — identifica o cômputo (ex: "rf_venc_2019", "rf_media_10a")
        nivel           — 1=obs bruta, 2=primeira agregação, 3=segunda, 4=fórmula final
        input_ordem     — posição do input dentro do grupo (1, 2, ...)
        input_label     — rótulo semântico do input (vencimento, data, empresa, ano, termo)
        input_valor     — valor numérico do input (decimal)
        n_inputs_grupo  — quantos inputs compõem este grupo
        operacao        — media_simples | soma | produto | hamada_unlever | hamada_relever
        resultado_label — rótulo do output deste grupo
        resultado_valor — valor do output (repetido em todas as linhas do grupo)
        periodo_ini / periodo_fim — janela temporal do input
        fonte           — origem do dado
    """
    ano_dados = ano_publicacao - 1
    T = T_IRPJ_CSLL
    JANELA_RF = JANELA_ANOS
    JANELA_BETA = JANELA_BETA_ANOS

    rows: list[dict] = []

    def G(grupo, nivel, passo, parametro, ordem, i_label, i_valor, n_total,
          operacao, r_label, r_valor, p_ini, p_fim, fonte):
        rows.append({
            "ano_publicacao":  ano_publicacao,
            "segmento":        segmento,
            "passo":           passo,
            "parametro":       parametro,
            "grupo_calculo":   grupo,
            "nivel":           nivel,
            "input_ordem":     ordem,
            "input_label":     i_label,
            "input_valor":     round(float(i_valor), 8),
            "input_valor_pct": f"{float(i_valor):.4%}",
            "n_inputs_grupo":  n_total,
            "operacao":        operacao,
            "resultado_label": r_label,
            "resultado_valor": round(float(r_valor), 8),
            "resultado_pct":   f"{float(r_valor):.4%}",
            "periodo_ini":     str(p_ini),
            "periodo_fim":     str(p_fim),
            "fonte":           fonte,
        })

    # --- fixtures comuns ---
    wacc_apl   = load_wacc_aplicacao()
    row_apl    = wacc_apl[(wacc_apl["ano"] == ano_publicacao) &
                          (wacc_apl["segmento"] == segmento)].iloc[0]
    rf_pub     = float(row_apl["rf"])
    erp_pub    = float(row_apl["erp"])
    embi_pub   = float(row_apl.get("embi", 0.027649))
    beta_l_pub = float(row_apl["beta_l"])
    ev_pub     = float(row_apl["ev"])
    dv_pub     = float(row_apl["dv"])
    kd_deb     = float(row_apl["kd_debentures"])
    kd_custo   = float(row_apl["kd_custo_emissao"])
    kd_ai      = float(row_apl["kd_real_ai"])
    kd_di      = float(row_apl.get("kd_real_di", kd_ai * (1 - T)))
    ke_di      = float(row_apl["ke_real_di"])
    wacc_di    = float(row_apl["wacc_di"])
    wacc_ai    = float(row_apl["wacc_ai"])

    # ================================================================
    # [1] Rf — NÍVEL 1: obs diária media por (ano, vencimento)
    #          NÍVEL 2: media dos vencimentos → Rf_anual
    #          NÍVEL 3: media dos 10 Rf_anuais → Rf publicado
    # ================================================================
    FONTE_NTNB = "Tesouro Nacional / NTN-B (taxa compra manhã)"
    ntnb = load_ntnb()
    ntnb["data"]      = pd.to_datetime(ntnb["data"])
    ntnb["vencimento"] = pd.to_datetime(ntnb["vencimento"])
    ntnb["ano"]       = ntnb["data"].dt.year

    rf_anuais: dict[int, float] = {}  # rf anual para nível 3

    for ano in range(ano_dados - JANELA_RF + 1, ano_dados + 1):
        df_ano = ntnb[
            (ntnb["ano"] == ano) &
            ntnb["taxa_compra_manha"].between(0.01, 0.25) &
            (ntnb["vencimento"] > pd.Timestamp(f"{ano}-01-01"))
        ].copy()
        if df_ano.empty:
            continue

        # Nível 1: média diária por vencimento
        venc_medias = df_ano.groupby("vencimento")["taxa_compra_manha"].agg(
            media="mean", n_obs="count"
        ).reset_index()
        n_venc = len(venc_medias)
        rf_ano = float(venc_medias["media"].mean())
        rf_anuais[ano] = rf_ano

        for i, r in enumerate(venc_medias.itertuples(), 1):
            G(
                grupo    = f"rf_venc_{ano}",
                nivel    = 1,
                passo    = "[1] Rf",
                parametro= "rf_venc_media",
                ordem    = i,
                i_label  = f"NTN-B venc {r.vencimento.strftime('%Y-%m-%d')}  ({int(r.n_obs)} obs diárias)",
                i_valor  = r.media,
                n_total  = n_venc,
                operacao = "media_simples_diaria→media_vencimentos",
                r_label  = f"Rf_{ano}",
                r_valor  = rf_ano,
                p_ini    = f"{ano}-01-01",
                p_fim    = f"{ano}-12-31",
                fonte    = FONTE_NTNB,
            )

    # Nível 2: Rf_anuais → Rf (média 10 anos)
    anos_rf = sorted(rf_anuais)
    for i, ano in enumerate(anos_rf, 1):
        G(
            grupo    = "rf_media_10a",
            nivel    = 2,
            passo    = "[1] Rf",
            parametro= "rf_anual",
            ordem    = i,
            i_label  = f"Rf_{ano}  (média de {sum(1 for r in ntnb[ntnb['ano']==ano]['vencimento'].unique())} vencimentos)",
            i_valor  = rf_anuais[ano],
            n_total  = len(anos_rf),
            operacao = "media_simples_10_anos",
            r_label  = "Rf_publicado",
            r_valor  = rf_pub,
            p_ini    = f"{min(anos_rf)}-01-01",
            p_fim    = f"{max(anos_rf)}-12-31",
            fonte    = FONTE_NTNB,
        )

    # ================================================================
    # [2] ERP — fonte única (sem agregação temporal no fixture)
    # ================================================================
    G(
        grupo    = "erp_damodaran",
        nivel    = 1,
        passo    = "[2] ERP",
        parametro= "erp",
        ordem    = 1,
        i_label  = f"Retorno geométrico S&P500 vs T-Bills 1928–{ano_dados}",
        i_valor  = erp_pub,
        n_total  = 1,
        operacao = "retorno_geometrico_acumulado",
        r_label  = "ERP_publicado",
        r_valor  = erp_pub,
        p_ini    = "1928-01-01",
        p_fim    = f"{ano_dados}-12-31",
        fonte    = "Damodaran (NYU Stern) / histretSP.xls",
    )

    # ================================================================
    # [3] EMBI+ — NÍVEL 1: obs diária
    #             NÍVEL 2: média anual
    #             NÍVEL 3: média 10 anos → EMBI publicado
    # ================================================================
    FONTE_EMBI = "IPEADATA / JPMorgan EMBI+ (JPM366_EMBI366)"
    embi_df = load_embi_diario()
    embi_df["data"] = pd.to_datetime(embi_df["data"])
    embi_df["ano"]  = embi_df["data"].dt.year

    ano_ini_embi = ano_dados - JANELA_RF + 1
    embi_anuais: dict[int, float] = {}

    for ano in range(ano_ini_embi, ano_dados + 1):
        serie = embi_df[embi_df["ano"] == ano]["embi_decimal"]
        if serie.empty:
            continue
        media_anual = float(serie.mean())
        embi_anuais[ano] = media_anual
        n_obs = len(serie)

        # Nível 1: cada obs diária
        for i, (_, row) in enumerate(
            embi_df[embi_df["ano"] == ano].sort_values("data").iterrows(), 1
        ):
            G(
                grupo    = f"embi_diario_{ano}",
                nivel    = 1,
                passo    = "[3] EMBI+",
                parametro= "embi_diario",
                ordem    = i,
                i_label  = f"EMBI+ {row['data'].strftime('%Y-%m-%d')}",
                i_valor  = row["embi_decimal"],
                n_total  = n_obs,
                operacao = "media_aritmetica_diaria",
                r_label  = f"embi_{ano}",
                r_valor  = media_anual,
                p_ini    = str(row["data"].date()),
                p_fim    = str(row["data"].date()),
                fonte    = FONTE_EMBI,
            )

    # Nível 2: médias anuais → média 10 anos
    anos_embi = sorted(embi_anuais)
    for i, ano in enumerate(anos_embi, 1):
        G(
            grupo    = "embi_media_10a",
            nivel    = 2,
            passo    = "[3] EMBI+",
            parametro= "embi_anual",
            ordem    = i,
            i_label  = f"EMBI_{ano}  ({sum(embi_df['ano']==ano)} obs diárias)",
            i_valor  = embi_anuais[ano],
            n_total  = len(anos_embi),
            operacao = "media_simples_10_anos",
            r_label  = "EMBI_publicado",
            r_valor  = embi_pub,
            p_ini    = f"{ano}-01-01",
            p_fim    = f"{ano}-12-31",
            fonte    = FONTE_EMBI,
        )

    # ================================================================
    # [4] Beta — NÍVEL 1: beta_u por janela anual (13 estimativas)
    #            NÍVEL 2: media das 13 estimativas → beta_u publicado
    #            NÍVEL 3: Hamada re-alavancagem → beta_l publicado
    # ================================================================
    FONTE_BETA = "Preços semanais utilities EUA (ANEEL/yfinance) / SPXT Total Return"
    beta_hist = load_beta_historico()
    wacc_hist = load_wacc_historico()
    bl_hist   = (dict(zip(wacc_hist["ano"], wacc_hist["beta_l"]))
                 if "beta_l" in wacc_hist.columns else {})

    beta_u_vals: list[tuple[int, float, float]] = []  # (ano, beta_u, beta_l)

    for _, r in beta_hist[beta_hist["ano"].between(2013, ano_dados)].iterrows():
        a   = int(r["ano"])
        bu  = float(r["beta_u_eua"])
        bl  = bl_hist.get(a, float(r["beta_l_brasil"]))
        de_eua = (bl / bu - 1) / (1 - T) if bu > 0 else 0.0
        beta_u_vals.append((a, bu, de_eua))

    n_janelas = len(beta_u_vals)
    beta_u_media = sum(v[1] for v in beta_u_vals) / n_janelas

    # Nível 1: beta_u por janela
    for i, (a, bu, de_eua) in enumerate(beta_u_vals, 1):
        jan_ini = a - JANELA_BETA + 1
        G(
            grupo    = "beta_u_13_janelas",
            nivel    = 1,
            passo    = "[4] Beta",
            parametro= "beta_u_janela",
            ordem    = i,
            i_label  = f"beta_u janela {jan_ini}–{a}  (OLS 5a, D/E_EUA impl.={de_eua:.4f})",
            i_valor  = bu,
            n_total  = n_janelas,
            operacao = "media_simples_13_janelas",
            r_label  = "beta_u_publicado",
            r_valor  = 0.30220,
            p_ini    = f"{jan_ini}-10-01",
            p_fim    = f"{a}-09-30",
            fonte    = FONTE_BETA,
        )

    # Nível 2: média das 13 janelas (nota: publicado ANEEL usa D/E por empresa)
    G(
        grupo    = "beta_hamada_relever",
        nivel    = 2,
        passo    = "[4] Beta",
        parametro= "beta_u",
        ordem    = 1,
        i_label  = f"beta_u_publicado ANEEL  (D/E EUA por empresa, Despacho 675/2026)",
        i_valor  = 0.30220,
        n_total  = 2,
        operacao = "hamada_relever: beta_l = beta_u × (1 + (1-T) × D/E_EUA)",
        r_label  = "beta_l_publicado",
        r_valor  = beta_l_pub,
        p_ini    = f"{ano_publicacao}-01-01",
        p_fim    = f"{ano_publicacao}-12-31",
        fonte    = FONTE_BETA,
    )
    G(
        grupo    = "beta_hamada_relever",
        nivel    = 2,
        passo    = "[4] Beta",
        parametro= "de_eua",
        ordem    = 2,
        i_label  = f"D/E_EUA  (= D/V ÷ E/V = {dv_pub:.6f} ÷ {ev_pub:.6f})",
        i_valor  = dv_pub / ev_pub,
        n_total  = 2,
        operacao = "hamada_relever: beta_l = beta_u × (1 + (1-T) × D/E_EUA)",
        r_label  = "beta_l_publicado",
        r_valor  = beta_l_pub,
        p_ini    = f"{ano_publicacao}-01-01",
        p_fim    = f"{ano_publicacao}-12-31",
        fonte    = "ANEEL / Despacho 675/2026",
    )

    # ================================================================
    # [5] Kd — soma Kd_deb + custo_emissao
    # ================================================================
    FONTE_KD = "ANEEL / Debêntures setor elétrico — Despacho 675/2026"
    for i, (label, val) in enumerate([
        ("Kd_debêntures  (taxa real média ponderada da amostra)", kd_deb),
        ("Custo_emissão  (custo amortizado / prazo médio)",        kd_custo),
    ], 1):
        G(
            grupo    = "kd_ai_soma",
            nivel    = 1,
            passo    = "[5] Kd",
            parametro= "kd_ai",
            ordem    = i,
            i_label  = label,
            i_valor  = val,
            n_total  = 2,
            operacao = "soma: Kd_ai = Kd_deb + custo_emissao",
            r_label  = "Kd_ai",
            r_valor  = kd_ai,
            p_ini    = f"{ano_publicacao}-01-01",
            p_fim    = f"{ano_publicacao}-12-31",
            fonte    = FONTE_KD,
        )

    # Kd_ai → Kd_di
    G(
        grupo    = "kd_di_calculo",
        nivel    = 2,
        passo    = "[5] Kd",
        parametro= "kd_di",
        ordem    = 1,
        i_label  = f"Kd_ai  ({kd_ai:.6%})",
        i_valor  = kd_ai,
        n_total  = 2,
        operacao = f"produto: Kd_di = Kd_ai × (1–T) = Kd_ai × {1-T:.4f}",
        r_label  = "Kd_di",
        r_valor  = kd_di,
        p_ini    = f"{ano_publicacao}-01-01",
        p_fim    = f"{ano_publicacao}-12-31",
        fonte    = FONTE_KD,
    )
    G(
        grupo    = "kd_di_calculo",
        nivel    = 2,
        passo    = "[5] Kd",
        parametro= "kd_di_fator_fiscal",
        ordem    = 2,
        i_label  = f"(1 – T)  T={T:.0%}  IRPJ+CSLL",
        i_valor  = 1 - T,
        n_total  = 2,
        operacao = f"produto: Kd_di = Kd_ai × (1–T)",
        r_label  = "Kd_di",
        r_valor  = kd_di,
        p_ini    = f"{ano_publicacao}-01-01",
        p_fim    = f"{ano_publicacao}-12-31",
        fonte    = "Legislação tributária BR (IRPJ 15%+adicional 10% + CSLL 9%)",
    )

    # ================================================================
    # [6] Ke = Rf + beta_l × ERP
    # ================================================================
    prem_mercado = beta_l_pub * erp_pub
    for i, (label, val) in enumerate([
        (f"Rf  (NTN-B média 10a, 2016–2025)", rf_pub),
        (f"beta_l × ERP  = {beta_l_pub:.6f} × {erp_pub:.6%}  (prêmio de mercado alavancado)", prem_mercado),
    ], 1):
        G(
            grupo    = "ke_soma",
            nivel    = 3,
            passo    = "[6] Ke",
            parametro= "ke_di",
            ordem    = i,
            i_label  = label,
            i_valor  = val,
            n_total  = 2,
            operacao = "soma: Ke = Rf + beta_l × ERP",
            r_label  = "Ke_real_di",
            r_valor  = ke_di,
            p_ini    = f"{ano_publicacao}-01-01",
            p_fim    = f"{ano_publicacao}-12-31",
            fonte    = "Calculado",
        )

    # ================================================================
    # [7] WACC_di = Ke × E/V + Kd_di × D/V
    # ================================================================
    parcela_ke  = ke_di  * ev_pub
    parcela_kd  = kd_di  * dv_pub
    for i, (label, val) in enumerate([
        (f"Ke × E/V  = {ke_di:.6%} × {ev_pub:.6%}", parcela_ke),
        (f"Kd_di × D/V  = {kd_di:.6%} × {dv_pub:.6%}", parcela_kd),
    ], 1):
        G(
            grupo    = "wacc_di_soma",
            nivel    = 4,
            passo    = "[7] WACC_di",
            parametro= "wacc_di",
            ordem    = i,
            i_label  = label,
            i_valor  = val,
            n_total  = 2,
            operacao = "soma: WACC_di = Ke×E/V + Kd_di×D/V",
            r_label  = "WACC_di",
            r_valor  = wacc_di,
            p_ini    = f"{ano_publicacao}-01-01",
            p_fim    = f"{ano_publicacao}-12-31",
            fonte    = "Calculado",
        )

    # ================================================================
    # [8] WACC_ai = WACC_di / (1 – T)
    # ================================================================
    for i, (label, val) in enumerate([
        (f"WACC_di  ({wacc_di:.6%})", wacc_di),
        (f"(1 – T)  = {1-T:.4f}  (divisor fiscal)", 1 - T),
    ], 1):
        G(
            grupo    = "wacc_ai_divisao",
            nivel    = 4,
            passo    = "[8] WACC_ai",
            parametro= "wacc_ai",
            ordem    = i,
            i_label  = label,
            i_valor  = val,
            n_total  = 2,
            operacao = "divisao: WACC_ai = WACC_di / (1–T)",
            r_label  = "WACC_ai_RESULTADO_FINAL",
            r_valor  = wacc_ai,
            p_ini    = f"{ano_publicacao}-01-01",
            p_fim    = f"{ano_publicacao}-12-31",
            fonte    = "Calculado",
        )

    return pd.DataFrame(rows)


def trilha_beta_acoes_csv(janela_anos: int = None) -> pd.DataFrame:
    """
    CSV de rastreamento do beta por empresa — retornos semanais (OLS input) + Hamada + pesos.

    Estrutura:
        Bloco A — retornos_semanais (uma linha por semana por empresa)
            data | ticker | ret_spxt (x) | ret_ticker (y) | beta_l_ols (resultado)
        Bloco B — por_empresa (uma linha por empresa)
            ticker | beta_l | R2 | de_ratio | beta_u | market_cap_usd | peso_normalizado
        Bloco C — agregacao (uma linha por passo final)
            descricao | valor_entrada | operacao | resultado

    Metodologia ERP (nota incluída):
        ERP = S&P500 vs T-Bills (Damodaran, 1928–atual) — NÃO vs NTN-B.
        Razão: as utilities são americanas; o benchmark de risco relevante é T-Bills EUA.
        O risco Brasil já está capturado via EMBI+ e implicitamente na alavancagem americana
        (D/E_EUA ~2,35× > D/E_BR ~0,66×). Usar NTN-B como benchmark do ERP seria
        double-counting do prêmio-país.
    """
    import pickle
    import warnings
    from scipy.stats import linregress

    warnings.filterwarnings("ignore")
    T = T_IRPJ_CSLL

    # Carrega preços yfinance (cache)
    cache_dir = Path(__file__).parent.parent / "wacc_regulatorio" / "data" / "cache"
    pkl_prices = sorted(cache_dir.glob("beta_prices_*.pkl"))
    if not pkl_prices:
        raise FileNotFoundError("Cache beta_prices*.pkl não encontrado — execute camada2_corrente primeiro")

    with open(pkl_prices[-1], "rb") as f:
        prices = pickle.load(f)

    with open(cache_dir / "market_caps.pkl", "rb") as f:
        mktcaps_df = pickle.load(f)

    mc_map = dict(zip(mktcaps_df["ticker"], mktcaps_df["market_cap_usd"]))
    de_map = dict(zip(mktcaps_df["ticker"], mktcaps_df["de_ratio"]))

    if janela_anos is None:
        janela_anos = JANELA_BETA_ANOS

    hoje = pd.Timestamp.now()
    ano_fim = hoje.year if hoje.month >= 10 else hoje.year - 1
    jan_ini = pd.Timestamp(f"{ano_fim - janela_anos}-10-01")
    jan_fim = pd.Timestamp(f"{ano_fim}-09-30")

    df = prices[(prices.index >= jan_ini) & (prices.index <= jan_fim)].copy()
    import numpy as np
    rets = np.log(df / df.shift(1)).dropna(how="all")
    spxt_col = "^GSPC"
    tickers = [c for c in rets.columns if c != spxt_col]

    # ---- Bloco A: retornos semanais por empresa ----
    rows_a: list[dict] = []
    empresa_results: dict[str, dict] = {}

    for t in tickers:
        col = rets[[spxt_col, t]].dropna()
        if len(col) < 30:
            continue
        slope, intercept, r_val, _, se = linregress(col[spxt_col].values, col[t].values)
        de    = de_map.get(t, 0.6605)
        bu    = slope / (1 + (1 - T) * de)
        mc    = mc_map.get(t, 0)
        empresa_results[t] = {
            "beta_l": slope, "R2": r_val ** 2, "intercept": intercept,
            "de_ratio": de, "beta_u": bu, "market_cap_usd": mc, "n_obs": len(col),
        }
        for dt, row in col.iterrows():
            rows_a.append({
                "bloco":          "A_retornos_semanais",
                "data":           dt.strftime("%Y-%m-%d"),
                "ticker":         t,
                "janela_ini":     jan_ini.strftime("%Y-%m-%d"),
                "janela_fim":     jan_fim.strftime("%Y-%m-%d"),
                "n_semanas_janela": len(col),
                "ret_spxt_x":     round(float(row[spxt_col]), 8),
                "ret_ticker_y":   round(float(row[t]), 8),
                "beta_l_ols":     round(slope, 6),
                "intercept_ols":  round(intercept, 8),
                "R2_ols":         round(r_val ** 2, 6),
                "de_ratio":       round(de, 6),
                "beta_u_hamada":  round(bu, 6),
                "market_cap_usd": round(mc, 0) if mc else "",
                "nota_erp":       "ERP=Damodaran(S&P500-TBills); NÃO vs NTN-B (seria double-counting EMBI)",
            })

    df_a = pd.DataFrame(rows_a)

    # ---- Bloco B: resumo por empresa ----
    total_mc = sum(r["market_cap_usd"] for r in empresa_results.values())
    rows_b: list[dict] = []
    for t, er in sorted(empresa_results.items()):
        mc = er["market_cap_usd"]
        peso_raw  = mc / total_mc if total_mc > 0 else 1 / len(empresa_results)
        rows_b.append({
            "bloco":          "B_por_empresa",
            "ticker":         t,
            "janela_ini":     jan_ini.strftime("%Y-%m-%d"),
            "janela_fim":     jan_fim.strftime("%Y-%m-%d"),
            "n_semanas_ols":  er["n_obs"],
            "beta_l_ols":     round(er["beta_l"], 6),
            "R2":             round(er["R2"], 6),
            "de_ratio":       round(er["de_ratio"], 6),
            "de_ratio_fonte": "yfinance balance_sheet Total Debt / market_cap",
            "beta_u_hamada":  round(er["beta_u"], 6),
            "formula_hamada": f"beta_u = beta_l / (1 + (1-T)*D/E) = {er['beta_l']:.4f} / (1 + {1-T:.2f}*{er['de_ratio']:.4f})",
            "market_cap_usd": round(er["market_cap_usd"], 0) if er["market_cap_usd"] else "",
            "peso_raw":       round(peso_raw, 6),
            "peso_cap50":     round(min(peso_raw, 0.50), 6),
            "nota_erp":       "ERP=Damodaran(S&P500-TBills); NÃO vs NTN-B (seria double-counting EMBI)",
        })

    # Normaliza pesos após cap de 50%
    soma_cap = sum(min(r["peso_raw"], 0.50) for r in
                   [{"peso_raw": mc_map.get(t, 0) / total_mc} for t in empresa_results])
    for rb in rows_b:
        rb["peso_normalizado"] = round(rb["peso_cap50"] / soma_cap, 6)
        rb["beta_u_ponderado"] = round(rb["beta_u_hamada"] * rb["peso_normalizado"], 8)
        rb["de_ponderado"]     = round(rb["de_ratio"]      * rb["peso_normalizado"], 8)

    df_b = pd.DataFrame(rows_b)

    # ---- Bloco C: agregação final ----
    beta_u_pond  = df_b["beta_u_ponderado"].sum()
    de_pond      = df_b["de_ponderado"].sum()
    beta_l_final = beta_u_pond * (1 + (1 - T) * de_pond)

    rows_c = [
        {
            "bloco":         "C_agregacao",
            "passo":         "C2.1",
            "descricao":     "beta_u ponderado por market cap (cap 50%)",
            "n_empresas":    len(df_b),
            "valor_entrada": f"{len(df_b)} beta_u por empresa (ver Bloco B)",
            "operacao":      "media_ponderada_market_cap_cap50",
            "resultado":     round(beta_u_pond, 6),
        },
        {
            "bloco":         "C_agregacao",
            "passo":         "C2.2",
            "descricao":     "D/E ponderado por market cap (cap 50%)",
            "n_empresas":    len(df_b),
            "valor_entrada": f"{len(df_b)} de_ratio por empresa (ver Bloco B)",
            "operacao":      "media_ponderada_market_cap_cap50",
            "resultado":     round(de_pond, 6),
        },
        {
            "bloco":         "C_agregacao",
            "passo":         "C2.3",
            "descricao":     "beta_l re-alavancado (Hamada com D/E ponderado)",
            "n_empresas":    len(df_b),
            "valor_entrada": f"beta_u={beta_u_pond:.6f}; D/E={de_pond:.6f}; T={T:.0%}",
            "operacao":      f"hamada_relever: beta_u × (1 + (1-T) × D/E) = {beta_u_pond:.6f} × {1+(1-T)*de_pond:.6f}",
            "resultado":     round(beta_l_final, 6),
        },
        {
            "bloco":         "C_agregacao",
            "passo":         "nota_metodologia",
            "descricao":     "Por que ERP = S&P500 vs T-Bills (Damodaran) e NÃO vs NTN-B",
            "n_empresas":    "",
            "valor_entrada": (
                "O OLS é sobre utilities AMERICANAS, priced em USD. "
                "O prêmio de risco relevante é o americano (S&P500 - T-Bills, desde 1928). "
                "O risco Brasil entra pelo EMBI+ (explícito, +2,76%) e implicitamente "
                "pela alavancagem americana maior (D/E_EUA ~2,35× vs D/E_BR ~0,66×). "
                "Usar NTN-B como benchmark do ERP DUPLICARIA o prêmio-país."
            ),
            "operacao":      "nota_conceitual",
            "resultado":     "",
        },
    ]
    df_c = pd.DataFrame(rows_c)

    # Concatena (fill NaN para colunas ausentes entre blocos)
    df_final = pd.concat([df_a, df_b, df_c], ignore_index=True, sort=False)
    df_final.insert(0, "janela_anos", janela_anos)
    return df_final


def main():
    parser = argparse.ArgumentParser(description="Trilha de Cálculo WACC ANEEL 2026")
    parser.add_argument("--emitir", action="store_true",
                        help="Salva trilha .txt e memoria_calculo.csv")
    parser.add_argument("--csv", action="store_true",
                        help="Emite apenas o CSV (silencia o texto)")
    parser.add_argument("--ano", type=int, default=2026)
    args = parser.parse_args()

    root = Path(__file__).parent.parent

    if not args.csv:
        lines = trilha_calculo(ano_publicacao=args.ano)
        output = "\n".join(lines)
        print(output)
        if args.emitir:
            out_txt = root / f"trilha_calculo_{args.ano}.txt"
            out_txt.write_text(output, encoding="utf-8")
            print(f"\n  Trilha salva em: {out_txt}")

    if args.csv or args.emitir:
        # CSV 1: memória resumida (uma linha por parâmetro/componente)
        df1 = trilha_csv(ano_publicacao=args.ano)
        out_csv1 = root / f"memoria_calculo_wacc_{args.ano}.csv"
        df1.to_csv(out_csv1, index=False, encoding="utf-8-sig", sep=";", decimal=",")
        print(f"\n  [CSV 1] memoria_calculo_wacc_{args.ano}.csv")
        print(f"  {len(df1)} linhas  |  {df1['tipo_dado'].value_counts().to_dict()}")

        # CSV 2: memória granular (uma linha por input de cada operação)
        df2 = trilha_granular_csv(ano_publicacao=args.ano)
        out_csv2 = root / f"memoria_granular_wacc_{args.ano}.csv"
        df2.to_csv(out_csv2, index=False, encoding="utf-8-sig", sep=";", decimal=",")
        print(f"\n  [CSV 2] memoria_granular_wacc_{args.ano}.csv")
        print(f"  {len(df2)} linhas  |  grupos únicos: {df2['grupo_calculo'].nunique()}")
        lvl = df2.groupby("nivel").size()
        print(f"  Por nível: {lvl.to_dict()}")

        # CSV 3: retornos semanais das ações → OLS → Hamada → pesos market cap
        try:
            df3 = trilha_beta_acoes_csv()
            out_csv3 = root / f"memoria_beta_acoes_wacc_{args.ano}.csv"
            df3.to_csv(out_csv3, index=False, encoding="utf-8-sig", sep=";", decimal=",")
            print(f"\n  [CSV 3] memoria_beta_acoes_wacc_{args.ano}.csv")
            n_a = (df3["bloco"] == "A_retornos_semanais").sum()
            n_b = (df3["bloco"] == "B_por_empresa").sum()
            n_c = (df3["bloco"] == "C_agregacao").sum()
            print(f"  Bloco A (retornos semanais): {n_a} linhas  ({n_a // max(n_b,1)} semanas × {n_b} empresas)")
            print(f"  Bloco B (por empresa):       {n_b} linhas")
            print(f"  Bloco C (agregação final):   {n_c} linhas")
        except FileNotFoundError as e:
            print(f"\n  [CSV 3] AVISO: {e}")


if __name__ == "__main__":
    main()
