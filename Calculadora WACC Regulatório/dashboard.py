"""
Dashboard WACC Regulatório ANEEL — Despacho 675/2026
=====================================================
Execução:
    streamlit run dashboard.py
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ──────────────────────────────────────────────────────────────────────────────
# Configuração da página
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="WACC Regulatório ANEEL",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilo global
st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 16px 20px;
        border-left: 4px solid #1f77b4;
    }
    .pass-badge {
        background: #d4edda; color: #155724;
        padding: 4px 14px; border-radius: 20px;
        font-weight: bold; font-size: 1.1em;
    }
    .fail-badge {
        background: #f8d7da; color: #721c24;
        padding: 4px 14px; border-radius: 20px;
        font-weight: bold; font-size: 1.1em;
    }
    .warn-tag { color: #856404; font-weight: bold; }
    .ok-tag   { color: #155724; font-weight: bold; }
    div[data-testid="stMetric"] { background: #f8f9fa; border-radius: 8px; padding: 12px; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar — controles
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("WACC Regulatório")
    st.caption("ANEEL · Despacho 675/2026 · Transmissão")
    st.divider()

    st.subheader("Camada 3 — Vetor")
    horizonte = st.slider("Horizonte (anos)", min_value=5, max_value=30, value=30, step=5)
    kd_spec = "simples"  # EMBI implícito no beta — Kd~Rf sem componente EMBI explícito

    st.subheader("Rf spot projetado")
    st.caption("Taxa anual NTN-B que entra na janela rolante nos anos futuros")
    rf_proj_pct = st.slider(
        "Rf spot futuro (%)", min_value=3.0, max_value=12.0, value=7.6, step=0.1,
        help="Cenário base = média atual dos NTN-B (~7.6%). Pessimista = mantém alta. Otimista = normalização."
    )
    rf_spot_projetado = rf_proj_pct / 100.0
    embi_delta = {}

    st.divider()
    st.caption("Fontes: ANEEL · Tesouro Nacional · IPEADATA · ANBIMA")

# ──────────────────────────────────────────────────────────────────────────────
# Cache dos cálculos
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Calculando Camada 1...")
def get_camada1():
    from wacc_regulatorio.camada1_replicacao import executar_camada1
    from wacc_regulatorio.validator import validar, VALORES_REFERENCIA, TOL_OVERRIDE, TOL_PARAMETRO, TOL_WACC
    result = executar_camada1(verbose=False)

    refs = VALORES_REFERENCIA["transmissao"]
    result_map = {
        "rf":         result.rf,
        "erp":        result.erp,
        "beta_l":     result.beta_l,
        "beta_u":     result.beta_u,
        "ev":         result.ev,
        "dv":         result.dv,
        "ke_real_di": result.ke_real_di,
        "kd_real_ai": result.kd_real_ai,
        "wacc_di":    result.wacc_real_depois_impostos,
        "wacc_ai":    result.wacc_real_antes_impostos,
    }

    rows = []
    wacc_ok = True
    for key, (ref_val, label) in refs.items():
        calc = result_map.get(key)
        if calc is None:
            continue
        delta_bp = (calc - ref_val) * 10000
        tol = TOL_OVERRIDE.get(key, TOL_PARAMETRO)
        if key in ("wacc_di", "wacc_ai"):
            tol = TOL_WACC
        ok = abs(calc - ref_val) <= tol
        if key in ("wacc_di", "wacc_ai") and not ok:
            wacc_ok = False
        nota = ""
        if key == "beta_u":
            nota = "re-alav D/E EUA"
        rows.append({
            "Parâmetro": label,
            "Referência": ref_val,
            "Calculado": calc,
            "Delta (bp)": round(delta_bp, 2),
            "Tol (bp)": round(tol * 10000, 1),
            "Status": "OK" if ok else "WARN",
            "Nota": nota,
        })

    return result, pd.DataFrame(rows), wacc_ok


@st.cache_data(ttl=3600, show_spinner="Buscando dados ao vivo...")
def get_camada2(overrides_frozen: tuple = ()):
    from wacc_regulatorio.camada2_corrente import executar_camada2
    return executar_camada2(verbose=False, overrides=list(overrides_frozen))


@st.cache_data(ttl=3600, show_spinner="Calculando trilhas...")
def get_comparativo_trilhas():
    import pandas as pd
    from datetime import datetime
    from wacc_regulatorio.config import T_IRPJ_CSLL, JANELA_ANOS
    import numpy as np
    from wacc_regulatorio.data.fixtures import (
        load_ntnb, load_prm_sp500, load_embi_diario, load_embi_medias,
        load_debentures, load_custo_emissao, load_custo_emissao_periodos,
        load_beta_historico,
    )
    from wacc_regulatorio.data.fetchers import (
        fetch_beta_prices, fetch_market_caps, fetch_prm_sp500tr_incremento,
    )
    from wacc_regulatorio.params.rf   import calcular_rf_media_5a
    from wacc_regulatorio.params.erp  import calcular_prm
    from wacc_regulatorio.params.embi import calcular_embi_historico
    from wacc_regulatorio.params.beta import calcular_beta_janelas_anuais
    from wacc_regulatorio.params.kd   import calcular_kd_com_custo_emissao
    from wacc_regulatorio.camada2_corrente import executar_camada2
    from wacc_regulatorio.wacc_calc   import calcular_wacc

    T = T_IRPJ_CSLL
    ANO_PUB = 2026
    ANO_BASE = 2025

    REF = {
        "rf": 0.051377, "erp": 0.068481, "embi": 0.027650,
        "beta_u": 0.502950, "beta_l": 0.769239,
        "ev": 0.602261, "dv": 0.397739,
        "ke_real_di": 0.104055,
        "kd_deb": 0.060685, "kd_custo": 0.005181, "kd_ai": 0.065866,
        "wacc_di": 0.079959, "wacc_ai": 0.121150,
    }

    ntnb_hist    = load_ntnb()
    prm_base     = load_prm_sp500()
    embi_hist    = load_embi_diario()
    embi_medias  = load_embi_medias()
    deb_df       = load_debentures()
    custo_df     = load_custo_emissao()
    periodos_df  = load_custo_emissao_periodos()
    beta_hist_df = load_beta_historico()
    prm_df_ext   = fetch_prm_sp500tr_incremento(prm_base)
    prices_all   = fetch_beta_prices()
    mktcap_df    = fetch_market_caps()

    spxt_col = next(
        (c for c in prices_all.columns if "SP500TR" in c.upper() or "SPXT" in c.upper()), None
    )

    # C1 Público — mesma janela 2016-2025, fontes públicas
    ntnb_2025   = ntnb_hist[pd.to_datetime(ntnb_hist["data"], errors="coerce") <= "2025-12-31"].copy()
    prm_2025    = prm_df_ext[pd.to_datetime(prm_df_ext["data"], errors="coerce") <= "2025-12-31"].copy()
    prices_2025 = prices_all[prices_all.index <= "2025-09-30"].copy()

    rf_pub, _  = calcular_rf_media_5a(ANO_PUB, ntnb_2025)
    erp_pub, _ = calcular_prm(ANO_PUB, prm_2025)
    embi_pub   = calcular_embi_historico(ANO_BASE, embi_df=embi_hist, embi_medias_df=embi_medias)

    # Beta 4+1: 4 janelas Bloomberg (fixture xlsx ANEEL 2021-2024) + 1 janela yfinance (2025)
    _beta_2025_yf   = calcular_beta_janelas_anuais(
        prices_2025, mktcap_df, beta_hist_df, spxt_col=spxt_col, anos=[2025]
    )
    _hist_2021_2024 = beta_hist_df[beta_hist_df["ano"].isin([2021, 2022, 2023, 2024])].sort_values("ano")
    _bl_janelas     = list(_hist_2021_2024["beta_l_brasil"]) + [_beta_2025_yf.beta_l]
    _bu_janelas     = list(_hist_2021_2024["beta_u_eua"])  + [_beta_2025_yf.beta_u]
    beta_l_pub      = float(np.mean(_bl_janelas))
    beta_u_pub      = float(np.mean(_bu_janelas))
    _row_2025       = beta_hist_df[beta_hist_df["ano"] == 2025].iloc[0]
    EV_REG          = float(_row_2025["ev_brasil"])
    DV_REG          = float(_row_2025["dv_brasil"])

    kd_pub  = calcular_kd_com_custo_emissao(ano=ANO_BASE, debentures_df=deb_df,
                  custo_emissao_df=custo_df, periodos_df=periodos_df,
                  segmento="transmissao", T=T)
    wacc_pub = calcular_wacc(rf=rf_pub, erp=erp_pub, embi=embi_pub,
                  beta_l=beta_l_pub, beta_u=beta_u_pub, ev=EV_REG, dv=DV_REG,
                  kd_real_ai=kd_pub.kd_real_ai, T=T)

    c1pub = {
        "rf": rf_pub, "erp": erp_pub, "embi": embi_pub,
        "beta_u": beta_u_pub, "beta_l": beta_l_pub,
        "ev": EV_REG, "dv": DV_REG, "ke_real_di": wacc_pub.ke_real_di,
        "kd_deb": kd_pub.kd_debentures, "kd_custo": kd_pub.custo_emissao,
        "kd_ai": kd_pub.kd_real_ai,
        "wacc_di": wacc_pub.wacc_real_depois_impostos,
        "wacc_ai": wacc_pub.wacc_real_antes_impostos,
    }

    # C2 YTD: executar_camada2() — 4 Bloomberg + 1 yfinance + solver D/V
    c2_result = executar_camada2(verbose=False)
    w2  = c2_result.wacc
    sp2 = c2_result.snapshot_params
    kr2 = c2_result.kd_cenarios.get("base")

    c2ytd = {
        "rf":         sp2.get("rf", w2.rf),
        "erp":        sp2.get("prm", w2.erp),
        "embi":       sp2.get("embi", w2.embi),
        "beta_u":     sp2.get("beta_u", w2.beta_u),
        "beta_l":     sp2.get("beta_l", w2.beta_l),
        "ev":         sp2.get("ev", w2.ev),
        "dv":         sp2.get("dv", w2.dv),
        "ke_real_di": w2.ke_real_di,
        "kd_deb":     kr2.kd_debentures if kr2 else sp2.get("kd_debentures", 0),
        "kd_custo":   kr2.custo_emissao  if kr2 else sp2.get("kd_custo_emissao", 0),
        "kd_ai":      w2.kd_real_ai,
        "wacc_di":    w2.wacc_real_depois_impostos,
        "wacc_ai":    w2.wacc_real_antes_impostos,
    }

    return REF, c1pub, c2ytd


@st.cache_data(show_spinner="Projetando vetor calculadora...")
def _get_vetor_calculadora(rf, bl4_tuple, bl_user, hz):
    import numpy as np
    from wacc_regulatorio.camada3_vetor import projetar_vetor_wacc
    bl4 = list(bl4_tuple)
    beta_override = {}
    for t in range(hz):
        jan = bl4 + [bl_user] * (t + 1)
        beta_override[2026 + t] = float(np.mean(jan[-5:]))
    return projetar_vetor_wacc(
        horizonte_anos=hz, rf_spot_projetado=rf,
        beta_override=beta_override, kd_spec="simples", modo="base", verbose=False,
    )


@st.cache_data(show_spinner="Projetando vetor WACC...")
def get_camada3(horizonte, embi_delta_frozen, kd_spec, rf_spot_proj):
    from wacc_regulatorio.camada3_vetor import projetar_vetor_wacc
    embi_delta = dict(embi_delta_frozen) if embi_delta_frozen else None
    return projetar_vetor_wacc(
        horizonte_anos=horizonte,
        embi_delta=embi_delta,
        kd_spec=kd_spec,
        rf_spot_projetado=rf_spot_proj,
        verbose=False,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Abas
# ──────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab_calc, tab5 = st.tabs([
    "📋 Validação ANEEL (Camada 1)",
    "📡 WACC Corrente (Camada 2)",
    "📈 Vetor 30 anos (Camada 3)",
    "🔬 Comparativo de Trilhas",
    "🧮 Calculadora",
    "📖 Metodologia",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Camada 1
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Replicação do Despacho ANEEL 675/2026 — Transmissão")
    st.caption("Zero chamadas externas · Parâmetros calculados de fixtures brutos (NTN-B, SP500, debêntures)")

    try:
        result_c1, df_val, wacc_ok = get_camada1()

        # Métricas principais
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("WACC real a.i.", f"{result_c1.wacc_real_antes_impostos:.3%}",
                    delta=f"{(result_c1.wacc_real_antes_impostos - 0.121150)*10000:+.2f}bp vs ref")
        col2.metric("WACC real d.i.", f"{result_c1.wacc_real_depois_impostos:.3%}")
        col3.metric("Ke real d.i.", f"{result_c1.ke_real_di:.3%}")
        col4.metric("Kd real a.i.", f"{result_c1.kd_real_ai:.3%}")
        col5.metric("Beta_l", f"{result_c1.beta_l:.4f}")

        # Badge
        badge_html = (
            '<span class="pass-badge">PASS</span>'
            if wacc_ok else
            '<span class="fail-badge">FAIL</span>'
        )
        st.markdown(f"**Validação ANEEL:** {badge_html}  &nbsp; tolerância ±5bp WACC (±1bp parâmetros)",
                    unsafe_allow_html=True)
        st.divider()

        # Gráfico de cascata: montagem do WACC
        st.markdown("#### Decomposição do WACC")
        ke_contrib = result_c1.ke_real_di * result_c1.ev
        kd_contrib = result_c1.kd_real_di * result_c1.dv
        wacc_di = result_c1.wacc_real_depois_impostos

        rf_contrib  = result_c1.rf * result_c1.ev
        erp_contrib = (result_c1.beta_l * result_c1.erp) * result_c1.ev

        tax_grossup = result_c1.wacc_real_antes_impostos - wacc_di
        fig_wf = go.Figure(go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "total", "relative", "total", "relative"],
            x=["Rf × E/V", "β×PRM × E/V", "Ke × E/V", "Kd_di × D/V", "WACC d.i.", "÷(1-T)"],
            y=[rf_contrib, erp_contrib, 0, kd_contrib, 0, tax_grossup],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            increasing={"marker": {"color": "#1f77b4"}},
            decreasing={"marker": {"color": "#d62728"}},
            totals={"marker": {"color": "#2ca02c"}},
            text=[
                f"{rf_contrib:.2%}", f"{erp_contrib:.2%}", f"Ke={ke_contrib:.2%}",
                f"{kd_contrib:.2%}", f"WACC_di={wacc_di:.2%}",
                f"WACC_ai={result_c1.wacc_real_antes_impostos:.2%}",
            ],
            textposition="outside",
        ))
        fig_wf.update_layout(
            height=400, margin=dict(t=20, b=20),
            yaxis_tickformat=".2%", yaxis_title="Taxa real",
            showlegend=False,
        )
        st.plotly_chart(fig_wf, use_container_width=True)

        # Tabela detalhada
        st.markdown("#### Parâmetros vs referência ANEEL")

        def _style_status(val):
            if val == "OK":
                return "color: #155724; font-weight: bold"
            return "color: #856404; font-weight: bold"

        df_display = df_val.copy()
        df_display["Referência"] = df_display["Referência"].map("{:.4%}".format)
        df_display["Calculado"]  = df_display["Calculado"].map("{:.4%}".format)
        df_display["Delta (bp)"] = df_display["Delta (bp)"].map("{:+.2f}".format)

        styled = (
            df_display[["Parâmetro", "Referência", "Calculado", "Delta (bp)", "Tol (bp)", "Status", "Nota"]]
            .style
            .map(_style_status, subset=["Status"])
            .set_properties(**{"text-align": "right"}, subset=["Referência", "Calculado", "Delta (bp)", "Tol (bp)"])
            .set_properties(**{"text-align": "left"}, subset=["Parâmetro", "Status", "Nota"])
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # ── Trilha de Cálculo Completa ─────────────────────────────────────
        st.divider()
        with st.expander("📂 Trilha de Cálculo Completa — 13 CSVs + fluxo input→output", expanded=False):
            st.markdown("""
**Fluxo de cálculo:** cada CSV é um estágio intermediário. A conta completa é:

| # | Arquivo | Conteúdo | Input de | Output para |
|---|---------|----------|----------|-------------|
| 01 | `rf_ntnb_filtrado` | NTN-B diário após filtros ANEEL | Fixture ANEEL | 02 |
| 02 | `rf_media_anual` | Rf rolling 10a por janela (5 linhas) | 01 | Rf = média(02) = **5,14%** → 13 |
| 03 | `erp_serie_mensal` | S&P500 + T-Bill mensal desde 1928 | Fixture ANEEL | 04 |
| 04 | `erp_prm_anual` | PRM acumulado por ano (5 linhas) | 03 | ERP = média(04) = **6,85%** → 13 |
| 05 | `embi_diario` | EMBI+ diário janela 2016–2025 | IPEADATA | 06 |
| 06 | `embi_media_anual` | Média EMBI por ano | 05 | EMBI = média(06) = **2,76%** → 13 |
| 07 | `beta_historico` | β_u e β_l por janela anual 2013–2025 | Fixture ANEEL | β_l = média 5a = **0,7692** → 13 |
| 08 | `beta_c2_por_empresa` | OLS + Hamada por empresa (C2 yfinance) | 09 | β_l C2 = **0,668** (contexto) |
| 09 | `beta_c2_retornos_semanais` | Retornos semanais simples por ticker | yfinance | 08 |
| 10 | `kd_debentures` | 192 debêntures transmissão janela 10a | Fixture ANEEL | Kd_deb = **6,07%** → 13 |
| 11 | `kd_custo_emissao` | Custo emissão por título (Res. CVM 160) | Fixture ANEEL | 12 |
| 12 | `kd_custo_emissao_periodos` | Custo emissão IPCA+DI agregado | 11 | custo = **0,518%** → Kd_ai → 13 |
| 13 | `wacc_componentes` | **Todos os parâmetros + WACC final** | 02,04,06,07,10,12 | **WACC_ai = 12,11%** |

**Fórmulas encadeadas:**
- `Ke = Rf + β_l × ERP` = 5,14% + 0,7692 × 6,85% = **10,41%**
- `Kd_ai = Kd_deb + custo_emissao` = 6,07% + 0,518% = **6,59%**
- `Kd_di = Kd_ai × (1 − T)` = 6,59% × 0,66 = **4,35%**
- `WACC_di = Ke × E/V + Kd_di × D/V` = 10,41% × 60,23% + 4,35% × 39,77% = **7,99%**
- `WACC_ai = WACC_di ÷ (1 − T)` = 7,99% ÷ 0,66 = **12,11%**
""")

            st.markdown("#### Downloads individuais")
            _trilha_dir = Path(__file__).parent / "data" / "trilha_calculo"
            _trilha_meta = [
                ("01", "rf_ntnb_filtrado",          "NTN-B diário filtrado (input Rf)"),
                ("02", "rf_media_anual",             "Rf rolling 10a por janela → Rf = 5,14%"),
                ("03", "erp_serie_mensal",           "S&P500 + T-Bill mensal 1928–hoje"),
                ("04", "erp_prm_anual",              "PRM acumulado por ano → ERP = 6,85%"),
                ("05", "embi_diario",                "EMBI+ diário 2016–2025"),
                ("06", "embi_media_anual",           "Média EMBI por ano → EMBI = 2,76%"),
                ("07", "beta_historico",             "β_l por janela anual → β_l = 0,7692"),
                ("08", "beta_c2_por_empresa",        "OLS + Hamada por empresa (C2 yfinance)"),
                ("09", "beta_c2_retornos_semanais",  "Retornos semanais simples por ticker"),
                ("10", "kd_debentures",              "192 debêntures transmissão → Kd_deb = 6,07%"),
                ("11", "kd_custo_emissao",           "Custo emissão por título (Res. CVM 160)"),
                ("12", "kd_custo_emissao_periodos",  "Custo emissão IPCA+DI agregado → 0,518%"),
                ("13", "wacc_componentes",           "RESULTADO: todos os parâmetros + WACC_ai = 12,11%"),
            ]

            # Linha de 4 colunas, repetida
            for i in range(0, len(_trilha_meta), 4):
                cols = st.columns(4)
                for j, (num, nome, desc) in enumerate(_trilha_meta[i:i+4]):
                    _path = _trilha_dir / f"{num}_{nome}.csv"
                    if _path.exists():
                        _data = _path.read_bytes()
                        cols[j].download_button(
                            f"⬇ {num} · {nome.replace('_', ' ')}",
                            data=_data,
                            file_name=f"wacc_{num}_{nome}.csv",
                            mime="text/csv",
                            help=desc,
                            key=f"dl_trilha_{num}",
                        )
                    else:
                        cols[j].caption(f"❌ {num}_{nome}.csv não encontrado")

            # ZIP com todos os 13
            import zipfile, io as _io
            _zip_buf = _io.BytesIO()
            with zipfile.ZipFile(_zip_buf, "w", zipfile.ZIP_DEFLATED) as _zf:
                for num, nome, _ in _trilha_meta:
                    _p = _trilha_dir / f"{num}_{nome}.csv"
                    if _p.exists():
                        _zf.write(_p, f"{num}_{nome}.csv")
            st.download_button(
                "⬇ Download ZIP — todos os 13 CSVs",
                data=_zip_buf.getvalue(),
                file_name="wacc_trilha_calculo_completa.zip",
                mime="application/zip",
            )

    except Exception as e:
        st.error(f"Erro ao executar Camada 1: {e}")
        st.info("Verifique se os fixtures foram extraídos: `python scripts/extrair_fixtures.py`")
        st.exception(e)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Camada 2
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("WACC Corrente Implícito — Radar de Mercado")
    st.caption("Dados ao vivo: Tesouro Nacional · IPEADATA · Fixtures históricas · Cache TTL 1h")

    col_btn, col_info = st.columns([1, 4])
    if col_btn.button("Atualizar dados", icon="🔄"):
        get_camada2.clear()
        st.rerun()
    col_info.caption("Os dados ao vivo têm cache de 1 hora. Clique para forçar atualização.")

    with st.expander("Adicionar debêntures/emissoras ao basket (override manual)", expanded=False):
        st.caption(
            "Adiciona casos específicos ao cenário **custom** — não altera o cenário base nem o WACC publicado. "
            "Um item por linha: código CETIP (ex: TAEE22) ou substring do nome da empresa."
        )
        overrides_raw = st.text_area(
            "Overrides",
            label_visibility="collapsed",
            placeholder="TAEE22\nNOVA TRANSMISSORA S.A.",
            height=100,
            key="kd_overrides",
        )
    overrides_frozen = tuple(x.strip() for x in overrides_raw.splitlines() if x.strip())

    try:
        c2 = get_camada2(overrides_frozen)

        # Direção
        DIRECAO_ICON = {"subindo": "↑", "caindo": "↓", "estavel": "→"}
        DIRECAO_COLOR = {"subindo": "#d62728", "caindo": "#2ca02c", "estavel": "#7f7f7f"}
        icone = DIRECAO_ICON.get(c2.direcao, "?")
        cor = DIRECAO_COLOR.get(c2.direcao, "gray")
        delta_bp = c2.delta_vs_publicado * 10000
        sinal = "+" if delta_bp >= 0 else ""

        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            "WACC atual (a.i.)",
            f"{c2.wacc.wacc_real_antes_impostos:.3%}",
            delta=f"{sinal}{delta_bp:.1f}bp vs publicado",
            delta_color="normal" if c2.direcao == "caindo" else "inverse",
        )
        col2.metric("Rf (NTN-B)", f"{c2.wacc.rf:.3%}",
                    help="Média taxa compra manhã YTD ou último ano completo")
        col3.metric("EMBI+ (10a, embutido no β)", f"{c2.wacc.embi:.3%}")
        col4.metric("Tendência próximo despacho",
                    f"{icone} {c2.direcao.upper()}",
                    help="Comparado ao Despacho 675/2026 (12,11%)")

        st.divider()

        # Comparação: publicado vs corrente
        st.markdown("#### Publicado (675/2026) vs Corrente")
        params_comp = {
            "Rf":       (0.051377, c2.wacc.rf),
            "PRM":      (0.068481, c2.wacc.erp),
            "Beta_l":   (0.769239, c2.wacc.beta_l),
            "E/V":      (0.602261, c2.wacc.ev),
            "Ke d.i.":  (0.104055, c2.wacc.ke_real_di),
            "Kd a.i.":  (0.065866, c2.wacc.kd_real_ai),
            "WACC d.i.":(0.079959, c2.wacc.wacc_real_depois_impostos),
            "WACC a.i.":(0.121150, c2.wacc.wacc_real_antes_impostos),
        }
        st.caption("EMBI+ (2,76% publicado) não aparece na comparação — está implícito no Beta_l via re-alavancagem com D/E americano.")

        nomes = list(params_comp.keys())
        publicados = [v[0] * 100 for v in params_comp.values()]
        correntes  = [v[1] * 100 for v in params_comp.values()]

        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(
            name="Publicado 675/2026", x=nomes, y=publicados,
            marker_color="#aec7e8", text=[f"{v:.2f}%" for v in publicados],
            textposition="outside",
        ))
        fig_comp.add_trace(go.Bar(
            name="Corrente (implícito)", x=nomes, y=correntes,
            marker_color="#1f77b4", text=[f"{v:.2f}%" for v in correntes],
            textposition="outside",
        ))
        fig_comp.update_layout(
            barmode="group", height=400,
            margin=dict(t=20, b=20),
            yaxis_title="Taxa (%)", legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig_comp, use_container_width=True)

        # Build-up Ke e Kd (stacked)
        st.markdown("#### Build-up do WACC corrente")
        ke_contrib  = c2.wacc.ke_real_di * c2.wacc.ev
        kd_di_contrib = c2.wacc.kd_real_di * c2.wacc.dv
        rf_ev  = c2.wacc.rf * c2.wacc.ev
        erp_ev = c2.wacc.beta_l * c2.wacc.erp * c2.wacc.ev

        tax_grossup2 = c2.wacc.wacc_real_antes_impostos - c2.wacc.wacc_real_depois_impostos
        fig_bu = go.Figure(go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "total", "relative", "total", "relative"],
            x=["Rf×E/V", "β×PRM×E/V", "Ke×E/V", "Kd_di×D/V", "WACC d.i.", "÷(1-T)"],
            y=[rf_ev, erp_ev, 0, kd_di_contrib, 0, tax_grossup2],
            connector={"line": {"color": "rgb(63,63,63)"}},
            increasing={"marker": {"color": "#1f77b4"}},
            decreasing={"marker": {"color": "#d62728"}},
            totals={"marker": {"color": "#2ca02c"}},
            text=[
                f"{rf_ev:.2%}", f"{erp_ev:.2%}", f"Ke={ke_contrib:.2%}",
                f"{kd_di_contrib:.2%}", f"WACC_di={c2.wacc.wacc_real_depois_impostos:.2%}",
                f"WACC_ai={c2.wacc.wacc_real_antes_impostos:.2%}",
            ],
            textposition="outside",
        ))
        fig_bu.update_layout(
            height=380, margin=dict(t=20, b=20),
            yaxis_tickformat=".2%", showlegend=False,
        )
        st.plotly_chart(fig_bu, use_container_width=True)

        # ── Trilha de Cálculo ──────────────────────────────────────────────
        sp = c2.snapshot_params
        st.divider()
        with st.expander("🔍 Trilha de Cálculo — dados puxados e intermediários", expanded=False):

            # ── Rf ──────────────────────────────────────────────────────────
            st.markdown("##### Rf — Taxa Livre de Risco (NTN-B)")
            st.caption(
                "Rf ANEEL = média das 5 médias anuais rolling 10 anos [P-5, P-1]. "
                "Cada valor anual = média diária de todas as NTN-B no dia, janela de 10 anos."
            )
            rf_det = sp.get("rf_detalhes", [])
            if rf_det:
                df_rf = pd.DataFrame(rf_det, columns=["Ano", "Rf rolling 10a"])
                df_rf["Rf rolling 10a (%)"] = df_rf["Rf rolling 10a"].map("{:.4%}".format)
                df_rf["Ref. ANEEL"] = ["5,138%" if i == len(df_rf) - 1 else "" for i in range(len(df_rf))]
                st.dataframe(
                    df_rf[["Ano", "Rf rolling 10a (%)"]],
                    hide_index=True, use_container_width=True,
                )
                rf_media = sum(v for _, v in rf_det) / len(rf_det)
                st.markdown(
                    f"**Média das {len(rf_det)} estimativas = {rf_media:.4%}** "
                    f"&nbsp;|&nbsp; ANEEL publicado = 5,138%"
                    f"&nbsp;|&nbsp; Delta = {(rf_media - 0.051377)*10000:+.1f}bp"
                )
            else:
                st.info("rf_detalhes não disponível.")

            st.divider()

            # ── PRM ─────────────────────────────────────────────────────────
            st.markdown("##### PRM — Prêmio de Risco de Mercado (S&P 500 vs T-Bill)")
            st.caption(
                "PRM ANEEL = média dos 5 PRM acumulados [P-5, P-1]. "
                "Cada PRM anual X = média de todos os PRM mensais desde 1928 até dez/X. "
                f"Fonte: {sp.get('prm_fonte', 'N/D')}"
            )
            prm_det = sp.get("prm_detalhes", [])
            if prm_det:
                df_prm = pd.DataFrame(prm_det, columns=["Ano", "PRM acumulado 1928"])
                df_prm["PRM (%)"] = df_prm["PRM acumulado 1928"].map("{:.4%}".format)
                st.dataframe(df_prm[["Ano", "PRM (%)"]], hide_index=True, use_container_width=True)
                prm_media = sum(v for _, v in prm_det) / len(prm_det)
                st.markdown(
                    f"**Média das {len(prm_det)} estimativas = {prm_media:.4%}** "
                    f"&nbsp;|&nbsp; ANEEL publicado = 6,848%"
                    f"&nbsp;|&nbsp; Delta = {(prm_media - 0.068481)*10000:+.1f}bp"
                )
            else:
                st.info("prm_detalhes não disponível.")

            st.divider()

            # ── EMBI ────────────────────────────────────────────────────────
            st.markdown("##### EMBI+ (embutido no β — não entra na fórmula do Ke)")
            embi_val = sp.get("embi", c2.wacc.embi)
            st.markdown(
                f"**Valor calculado:** {embi_val:.4%} &nbsp;|&nbsp; "
                f"ANEEL publicado = 2,765% &nbsp;|&nbsp; "
                f"Delta = {(embi_val - 0.027649)*10000:+.1f}bp"
            )
            st.caption(
                "Fonte: IPEADATA (série JPM366_EMBI366) + fixture histórico. "
                "Janela: média 10 anos YTD. "
                "O EMBI não entra diretamente na fórmula Ke = Rf + β×PRM — "
                "está capturado implicitamente via re-alavancagem do beta com D/E americano (~2,35×)."
            )

            st.divider()

            # ── Beta ────────────────────────────────────────────────────────
            st.markdown("##### Beta e Estrutura de Capital")
            beta_fonte = sp.get("beta_fonte", "N/D")
            st.markdown(
                f"**β_l = {c2.wacc.beta_l:.4f}** &nbsp;|&nbsp; "
                f"β_u = {c2.wacc.beta_u:.4f} &nbsp;|&nbsp; "
                f"E/V = {c2.wacc.ev:.4%} &nbsp;|&nbsp; "
                f"D/V = {c2.wacc.dv:.4%}"
            )
            st.caption(
                f"Fonte: **{beta_fonte}**. "
                "Metodologia 4+1 híbrido: 4 janelas Bloomberg do fixture ANEEL (anos N-4 a N-1) "
                "+ 1 janela yfinance ao vivo (ano N). "
                "β_l final = média das 5 β_l_brasil. "
                "Ponderação por D/V contábil (cap 50%), Hamada por empresa vs ^SP500TR."
            )
            beta_janelas = sp.get("beta_janelas", [])
            if beta_janelas:
                df_bj = pd.DataFrame(beta_janelas)
                df_bj = df_bj[["ano", "beta_u_eua", "beta_l_brasil", "dv_brasil", "fonte"]].copy()
                df_bj.columns = ["Janela", "β_u EUA", "β_l Brasil", "D/V Brasil", "Fonte"]
                df_bj["β_u EUA"]    = df_bj["β_u EUA"].map("{:.4f}".format)
                df_bj["β_l Brasil"] = df_bj["β_l Brasil"].map("{:.4f}".format)
                df_bj["D/V Brasil"] = df_bj["D/V Brasil"].map("{:.4%}".format)
                df_bj["Janela"] = df_bj["Janela"].astype(int)
                media_bl = sum(float(r["beta_l_brasil"]) for r in beta_janelas) / len(beta_janelas)
                st.dataframe(df_bj, hide_index=True, use_container_width=True)
                st.markdown(
                    f"**Média das {len(beta_janelas)} janelas β_l = {media_bl:.4f}** "
                    f"&nbsp;|&nbsp; ANEEL publicado = 0,7692 "
                    f"&nbsp;|&nbsp; Delta = {(media_bl - 0.7692)*10000:+.1f}bp"
                )

            st.divider()

            # ── Kd ──────────────────────────────────────────────────────────
            st.markdown("##### Kd — Custo de Capital de Terceiros")
            kd_fonte = sp.get("kd_fonte", "N/D")
            kd_deb = sp.get("kd_debentures", c2.wacc.kd_real_ai)
            kd_custo = sp.get("kd_custo_emissao", 0.0)
            kd_n = sp.get("kd_n_deb", 0)
            st.markdown(
                f"**Kd_deb = {kd_deb:.4%}** &nbsp;|&nbsp; "
                f"Custo emissão = {kd_custo:.4%} &nbsp;|&nbsp; "
                f"**Kd_ai = {c2.wacc.kd_real_ai:.4%}** &nbsp;|&nbsp; "
                f"n = {kd_n} debêntures"
            )
            kd_label = {
                "anbima_live": "Basket inference ANBIMA ao vivo (universo secundário)",
                "ettj_atualizado": "Kd-mid: amostra ANEEL + BEI atualizado via ETTJ (sem credenciais ANBIMA)",
            }.get(kd_fonte, kd_fonte)
            st.caption(f"Método: **{kd_label}**. Janela: 10 anos, área T (Transmissão).")

            st.divider()

            # ── Montagem WACC ────────────────────────────────────────────────
            st.markdown("##### Montagem do WACC")
            ke = c2.wacc.ke_real_di
            kd_di = c2.wacc.kd_real_di
            wacc_di = c2.wacc.wacc_real_depois_impostos
            wacc_ai = c2.wacc.wacc_real_antes_impostos
            ev = c2.wacc.ev
            dv = c2.wacc.dv
            T_val = c2.wacc.T
            beta_l = c2.wacc.beta_l
            rf_v = c2.wacc.rf
            prm_v = c2.wacc.erp

            rows_wacc = [
                ("Ke = Rf + β×PRM",
                 f"{rf_v:.4%} + {beta_l:.4f}×{prm_v:.4%}",
                 f"= **{ke:.4%}**"),
                ("Kd_di = Kd_ai × (1–T)",
                 f"{c2.wacc.kd_real_ai:.4%} × (1–{T_val:.0%})",
                 f"= **{kd_di:.4%}**"),
                ("WACC_di = Ke×E/V + Kd_di×D/V",
                 f"{ke:.4%}×{ev:.4%} + {kd_di:.4%}×{dv:.4%}",
                 f"= **{wacc_di:.4%}**"),
                ("WACC_ai = WACC_di / (1–T)",
                 f"{wacc_di:.4%} / (1–{T_val:.0%})",
                 f"= **{wacc_ai:.4%}**"),
            ]
            df_wacc = pd.DataFrame(rows_wacc, columns=["Fórmula", "Valores", "Resultado"])
            st.dataframe(df_wacc, hide_index=True, use_container_width=True)

        # ── Sensibilidade da cesta Kd ──────────────────────────────────────
        st.divider()
        st.markdown("#### Sensibilidade da Cesta Kd")
        st.caption(
            "**Base** (A): transmissoras confirmadas no fixture ANEEL.  "
            "**Amplo** (A+B): inclui candidatas com keywords de transmissão.  "
            "**Custom** (A+C): base + overrides inseridos acima."
        )

        kd_base   = sp.get("kd_ai",    c2.wacc.kd_real_ai)
        kd_amplo  = sp.get("kd_amplo",  kd_base)
        kd_custom = sp.get("kd_custom", kd_base)
        n_A = sp.get("kd_n_A") or sp.get("kd_n_deb") or 0
        n_B = sp.get("kd_n_B") or 0
        n_C = sp.get("kd_n_C") or 0
        delta_amplo_bp  = (kd_amplo  - kd_base) * 10000
        delta_custom_bp = (kd_custom - kd_base) * 10000

        ck1, ck2, ck3 = st.columns(3)
        ck1.metric(
            "Kd base (ANEEL)",
            f"{kd_base:.4%}",
            f"n={n_A} transmissoras",
            delta_color="off",
        )
        ck2.metric(
            "Kd amplo (+limítrofes)",
            f"{kd_amplo:.4%}",
            f"Δ {delta_amplo_bp:+.1f}bp | n={n_A+n_B}",
            delta_color="off",
        )
        ck3.metric(
            "Kd custom (+override)",
            f"{kd_custom:.4%}",
            f"Δ {delta_custom_bp:+.1f}bp | n={n_A+n_C}",
            delta_color="off",
        )

        # Tabela auditável da cesta por categoria
        if c2.kd_cesta_df is not None:
            with st.expander("Cesta inferida por categoria (auditoria)", expanded=False):
                df_audit = c2.kd_cesta_df.copy()
                cols_show = [c for c in ["codigo", "empresa", "categoria", "area",
                                          "indice", "data_emissao", "taxa_real"]
                             if c in df_audit.columns]
                df_audit = df_audit[cols_show]

                # Filtro por categoria
                cats_sel = st.multiselect(
                    "Filtrar categorias",
                    options=["A", "B", "C", "X"],
                    default=["A", "B", "C"],
                    key="kd_cat_filter",
                )
                df_show_audit = df_audit[df_audit["categoria"].isin(cats_sel)]

                if "taxa_real" in df_show_audit.columns:
                    df_show_audit = df_show_audit.copy()
                    df_show_audit["taxa_real"] = df_show_audit["taxa_real"].map(
                        lambda x: f"{x:.4%}" if pd.notna(x) else ""
                    )
                st.dataframe(df_show_audit, hide_index=True, use_container_width=True)

                # Overrides resolvidos
                if overrides_frozen:
                    from wacc_regulatorio.params.kd_cesta import resolver_overrides
                    msgs = resolver_overrides(
                        list(overrides_frozen),
                        c2.kd_cesta_df if c2.kd_cesta_df is not None else pd.DataFrame(),
                    )
                    st.markdown("**Overrides:**")
                    for m in msgs:
                        st.markdown(f"- {m}")

        st.caption(f"Referência de dados: {c2.data_referencia}")

    except RuntimeError as e:
        st.error(str(e))
        st.info(
            "Configure `ANBIMA_CLIENT_ID` e `ANBIMA_CLIENT_SECRET` como variáveis de ambiente "
            "e reinicie o Streamlit:\n\n"
            "```bash\nexport ANBIMA_CLIENT_ID=seu_id\n"
            "export ANBIMA_CLIENT_SECRET=seu_secret\n"
            "streamlit run dashboard.py\n```"
        )
    except Exception as e:
        st.error(f"Erro ao executar Camada 2: {e}")
        st.info("A Camada 2 requer acesso à internet. Verifique a conexão e os fixtures.")
        st.exception(e)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Camada 3
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader(f"Vetor WACC — {horizonte} anos  |  Kd: {kd_spec}")
    col_c3a, col_c3b = st.columns([1, 4])
    if col_c3a.button("Recalcular vetor", icon="🔄"):
        get_camada3.clear()
        st.rerun()
    col_c3b.caption("EMBI implícito no β — Kd projetado via regressão Kd ~ Rf")

    st.info(
        "**Por que C3 começa em ~12,1% (C1) e não no nível corrente de C2?** "
        "C3 ano 1 replica o WACC publicado porque ambos usam a **média histórica de 5 médias "
        "rolantes de 10 anos de Rf** (janela 2016–2025). "
        "C2 usa a taxa spot YTD dos NTN-B e parâmetros de mercado correntes (beta ao vivo) "
        "— valores que ainda **não entraram** na janela rolante regulatória. "
        "O gap entre C1 e C2 é a elevação (ou queda) já represada no mercado — incorporada "
        "gradualmente à medida que cada ano novo entra na janela e um ano antigo sai. "
        "O EMBI está implícito no β via re-alavancagem com D/E americano — não é parâmetro "
        "explícito do Ke nem da projeção C3.",
        icon="ℹ️",
    )

    try:
        embi_frozen = tuple(sorted(embi_delta.items())) if embi_delta else ()
        df3 = get_camada3(horizonte, embi_frozen, kd_spec, rf_spot_projetado)

        anos = [str(p) for p in df3.index]

        # Paleta por zona fonte_rf
        ZONA_COR = {
            "ettj":          "#2ca02c",   # verde
            "ettj_extrapol": "#ff7f0e",   # laranja
            "extrapol_longo":"#d62728",   # vermelho
        }

        # ── Gráfico principal: WACC_ai ao longo do tempo ──────────────────
        fig_main = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[0.65, 0.35],
            vertical_spacing=0.08,
            subplot_titles=("WACC real a.i. — ancorado em C2 (%)", "Componentes de taxa (%)"),
        )

        # Obtém C2 como ponto zero de referência
        wacc_ini = df3["WACC_antes_impostos"].iloc[0]
        rf_c2 = None
        wacc_c2 = None
        try:
            c2_ref = get_camada2()
            rf_c2  = c2_ref.wacc.rf
            wacc_c2 = c2_ref.wacc.wacc_real_antes_impostos
        except Exception:
            pass

        # Série ancorada: C2 como ponto zero, mesma trajetória de δ da média móvel
        # wacc_ancorado[t] = C2 + (C3[t] - C3[0])
        # Leitura: "partindo do mercado hoje (C2), se o Rf spot projetado persistir,
        # como o WACC regulatório evolui à medida que anos entram/saem da janela rolling?"
        if wacc_c2 is not None:
            delta_ancora = wacc_c2 - wacc_ini
            wacc_ancorado = df3["WACC_antes_impostos"] + delta_ancora
        else:
            delta_ancora = 0.0
            wacc_ancorado = df3["WACC_antes_impostos"]

        # Linha principal: trajetória ancorada em C2
        fig_main.add_trace(go.Scatter(
            x=anos,
            y=wacc_ancorado * 100,
            mode="lines+markers",
            name="WACC a.i. (base C2)",
            line=dict(color="#1f77b4", width=2.5),
            marker=dict(
                color=[ZONA_COR.get(z, "#7f7f7f") for z in df3["fonte_rf"]],
                size=7, line=dict(width=1, color="white"),
            ),
            hovertemplate="%{x}: %{y:.2f}%<extra></extra>",
        ), row=1, col=1)

        # Linha secundária: trajetória regulatória bruta (base C1) — referência
        fig_main.add_trace(go.Scatter(
            x=anos,
            y=df3["WACC_antes_impostos"] * 100,
            mode="lines",
            name="WACC a.i. (base C1, ref.)",
            line=dict(color="#aec7e8", width=1.2, dash="dot"),
            hovertemplate="%{x}: %{y:.2f}% (base C1)<extra></extra>",
        ), row=1, col=1)

        # Linha de referência ANEEL publicado (C1)
        fig_main.add_hline(
            y=12.115, line_dash="dash", line_color="gray",
            annotation_text="C1 publicado 675/2026 (12,115%)",
            annotation_position="top right",
            row=1, col=1,
        )

        # Ponto de partida C2 (ano 0)
        if wacc_c2 is not None:
            fig_main.add_hline(
                y=wacc_c2 * 100, line_dash="dot", line_color="#d62728",
                annotation_text=f"C2 hoje — ponto zero ({wacc_c2:.2%})",
                annotation_position="bottom right",
                row=1, col=1,
            )

        # Anotação de equilíbrio (último ano da série ancorada)
        wacc_equil = float(wacc_ancorado.iloc[-1])
        ano_equil  = str(df3.index[-1])
        fig_main.add_annotation(
            x=ano_equil, y=wacc_equil * 100,
            text=f"Equilíbrio {ano_equil}: {wacc_equil:.2%}",
            showarrow=True, arrowhead=2, arrowcolor="#1f77b4",
            arrowwidth=1.5, ax=-60, ay=-25,
            font=dict(color="#1f77b4", size=11),
            row=1, col=1,
        )

        # Área sombreada por zona (na série ancorada)
        for zona, cor in ZONA_COR.items():
            mask = df3["fonte_rf"] == zona
            if mask.any():
                anos_zona = [str(p) for p in df3[mask].index]
                vals_zona = wacc_ancorado[mask] * 100
                fig_main.add_trace(go.Scatter(
                    x=anos_zona, y=vals_zona,
                    mode="markers",
                    marker=dict(color=cor, size=9, symbol="circle"),
                    name=zona, showlegend=True,
                    hoverinfo="skip",
                ), row=1, col=1)

        # Painel inferior: Rf do vetor + linha Rf C2 para comparação
        fig_main.add_trace(go.Scatter(
            x=anos, y=df3["Rf"] * 100,
            name="Rf (curva a termo)", line=dict(color="#9467bd", dash="dot"), mode="lines",
        ), row=2, col=1)
        if rf_c2 is not None:
            fig_main.add_hline(
                y=rf_c2 * 100, line_dash="dash", line_color="#9467bd",
                annotation_text=f"Rf C2 media venc. ({rf_c2:.2%})",
                annotation_position="top left",
                row=2, col=1,
            )
        fig_main.add_trace(go.Scatter(
            x=anos, y=df3["EMBI"] * 100,
            name="EMBI (insumo Kd)", line=dict(color="#8c564b", dash="dot"), mode="lines",
        ), row=2, col=1)
        fig_main.add_trace(go.Scatter(
            x=anos, y=df3["Kd_real_ai"] * 100,
            name="Kd a.i.", line=dict(color="#e377c2", dash="dot"), mode="lines",
        ), row=2, col=1)

        fig_main.update_layout(
            height=620,
            margin=dict(t=40, b=20),
            legend=dict(orientation="h", y=1.05, x=0),
            hovermode="x unified",
        )
        fig_main.update_yaxes(ticksuffix="%")
        st.plotly_chart(fig_main, use_container_width=True)

        # Legenda de zonas
        c_leg1, c_leg2, c_leg3 = st.columns(3)
        c_leg1.markdown("🟢 **ettj** — dentro da curva ANBIMA")
        c_leg2.markdown("🟠 **ettj_extrapol** — além do último vértice")
        c_leg3.markdown("🔴 **extrapol_longo** — após 2060 ⚠️")

        st.divider()

        # ── Painel de convergência C1 → C2 → C3 ──────────────────────────
        st.markdown("#### Relação C1 · C2 · C3")
        wacc_ini = df3["WACC_antes_impostos"].iloc[0]
        wacc_fim = df3["WACC_antes_impostos"].iloc[-1]
        wacc_med = df3["WACC_antes_impostos"].mean()
        WACC_C1 = 0.121150  # publicado Despacho 675/2026

        # Métricas sobre a série ancorada em C2
        wacc_ancorado_ini = float(wacc_ancorado.iloc[0])   # = wacc_c2
        wacc_ancorado_fim = float(wacc_ancorado.iloc[-1])  # equilíbrio no horizonte

        pc1, pc2, pc3, pc4, pc5 = st.columns(5)
        pc1.metric(
            "C1 Publicado",
            f"{WACC_C1:.3%}",
            help="Despacho ANEEL 675/2026 — média de 5 médias rolantes de 10a",
        )
        pc2.metric(
            "C2 Hoje (ponto zero)",
            f"{wacc_ancorado_ini:.3%}",
            delta=f"{(wacc_ancorado_ini - WACC_C1)*10000:+.1f}bp vs C1",
            delta_color="off",
            help="Snapshot de mercado hoje — base da projeção C3 ancorada",
        )
        delta_trajetoria_bp = (wacc_ancorado_fim - wacc_ancorado_ini) * 10000
        pc3.metric(
            f"Equilíbrio ({horizonte}a)",
            f"{wacc_ancorado_fim:.3%}",
            delta=f"{delta_trajetoria_bp:+.0f}bp vs hoje",
            delta_color="inverse" if delta_trajetoria_bp > 0 else "normal",
            help=f"WACC quando todos os {horizonte} anos da janela tiverem Rf = {rf_spot_projetado:.1%}",
        )
        pc4.metric(
            "Δ Trajetória",
            f"{delta_trajetoria_bp:+.0f}bp",
            help="Variação total do WACC de hoje até o equilíbrio (efeito puro da média móvel do Rf)",
        )
        pc5.metric(
            "Rf spot projetado",
            f"{rf_spot_projetado:.2%}",
            help="Taxa que entra na janela rolling a cada ano futuro (ajuste no slider)",
        )

        # Tabela completa (colapsável)
        with st.expander("Tabela completa do vetor", expanded=False):
            anos_str = [str(p) for p in df3.index]
            df_show = df3.copy().reset_index(drop=True)
            df_show.insert(0, "Ano", anos_str)
            fmt_pct = {c: "{:.4%}".format
                       for c in ["Rf", "ERP", "EMBI", "Ke_real_di", "Kd_real_ai",
                                  "Kd_real_di", "WACC_depois_impostos", "WACC_antes_impostos"]}
            fmt_dec = {"Beta_l": "{:.4f}".format, "Beta_u": "{:.4f}".format,
                       "EV": "{:.2%}".format, "DV": "{:.2%}".format}

            def fmt_row(row):
                for col, fn in {**fmt_pct, **fmt_dec}.items():
                    if col in row.index:
                        row[col] = fn(row[col])
                return row

            df_show = df_show.apply(fmt_row, axis=1)
            colunas = ["Ano", "Rf", "ERP", "EMBI", "Beta_l", "Ke_real_di",
                       "Kd_real_ai", "WACC_depois_impostos", "WACC_antes_impostos", "fonte_rf"]
            st.dataframe(
                df_show[[c for c in colunas if c in df_show.columns]],
                hide_index=True,
                use_container_width=True,
            )

        # Download CSV
        csv = df3.reset_index().to_csv(index=False, sep=";", decimal=",")
        st.download_button(
            label="Download vetor CSV",
            data=csv.encode("utf-8-sig"),
            file_name=f"wacc_vetor_{horizonte}a.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"Erro ao projetar Camada 3: {e}")
        st.exception(e)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Metodologia
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def _load_whitepaper() -> str:
    wp = Path(__file__).parent / "WACC_Regulatorio_Whitepaper.md"
    if wp.exists():
        return wp.read_text(encoding="utf-8")
    return ""


def _extract_section(text: str, start: str, stop: str | None = None) -> str:
    idx = text.find(start)
    if idx == -1:
        return f"*Seção '{start}' não encontrada no whitepaper.*"
    if stop:
        end = text.find(stop, idx + len(start))
        return text[idx:end] if end != -1 else text[idx:]
    return text[idx:]


with tab4:
    st.subheader("Comparativo de Trilhas — Isolamento de Base de Dados vs. Movimento de Mercado")
    st.caption(
        "**C1 ANEEL** (Bloomberg) vs **C1 Público** (4+1 híbrido: 4 janelas Bloomberg do xlsx ANEEL + 1 janela yfinance 2025) — "
        "isola gap de base de dados restrito à janela corrente (−9,6bp em β_l, −6bp no WACC). "
        "**C2 YTD** usa janela atualizada + solver D/V endógeno — reflete movimento puro de mercado."
    )

    col_btn4, _ = st.columns([1, 4])
    if col_btn4.button("Recalcular trilhas", icon="🔄"):
        get_comparativo_trilhas.clear()
        st.rerun()

    try:
        REF, c1pub, c2ytd = get_comparativo_trilhas()

        def _bp(v, ref): return (v - ref) * 10000

        # ── Métricas-resumo ─────────────────────────────────────────────────
        st.markdown("#### Resultado por trilha — WACC real antes de impostos")
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("C1 ANEEL (Bloomberg)", f"{REF['wacc_ai']:.3%}", "referência")
        mc2.metric(
            "C1 Público (mesma janela)",
            f"{c1pub['wacc_ai']:.3%}",
            delta=f"{_bp(c1pub['wacc_ai'], REF['wacc_ai']):+.0f}bp gap de BD",
            delta_color="off",
        )
        mc3.metric(
            "C2 YTD (mercado atual)",
            f"{c2ytd['wacc_ai']:.3%}",
            delta=f"{_bp(c2ytd['wacc_ai'], c1pub['wacc_ai']):+.1f}bp mvmt mercado",
            delta_color="inverse" if c2ytd['wacc_ai'] < c1pub['wacc_ai'] else "normal",
        )

        st.divider()

        # ── Tabela detalhada ─────────────────────────────────────────────────
        st.markdown("#### Tabela parâmetro a parâmetro")
        st.caption(
            "**gap BD** = diferença de base de dados (yfinance vs Bloomberg, mesma janela). "
            "C1 Público usa 4 janelas Bloomberg (xlsx ANEEL) + 1 janela yfinance 2025 — gap residual de −48bp/janela ÷ 5 = −9,6bp em β_l.  "
            "**mvmt mercado** = diferença de período (janela histórica 2021–2025 vs janela corrente 2022–2026).  "
            "Beta (β) é adimensional — delta em unidade absoluta, não bp."
        )

        PARAMS = [
            ("Rf — Taxa Livre de Risco",  "rf",         True),
            ("ERP — Prêmio de Risco",      "erp",        True),
            ("EMBI — Risco Brasil",         "embi",       True),
            ("β_u — Beta Desalavancado",    "beta_u",     False),
            ("β_l — Beta Alavancado (BR)",  "beta_l",     False),
            ("E/V",                         "ev",         True),
            ("D/V",                         "dv",         True),
            ("Ke_di — Custo do Equity",     "ke_real_di", True),
            ("Kd_deb — Debêntures",         "kd_deb",     True),
            ("Custo de emissão",            "kd_custo",   True),
            ("Kd_ai — Custo Dívida AI",     "kd_ai",      True),
            ("WACC_di — Real d.i.",         "wacc_di",    True),
            ("WACC_ai — Real a.i. ★",       "wacc_ai",    True),
        ]

        rows_comp = []
        for nome, key, pct in PARAMS:
            v_ref  = REF[key]
            v_pub  = c1pub[key]
            v_ytd  = c2ytd[key]
            gap_bd = _bp(v_pub, v_ref)
            mvmt   = _bp(v_ytd, v_pub)
            fmt = ".4%" if pct else ".4f"
            rows_comp.append({
                "Parâmetro": nome,
                "C1 ANEEL": format(v_ref, fmt),
                "C1 Público": format(v_pub, fmt),
                "gap BD (bp)": f"{gap_bd:+.1f}" if pct else f"{v_pub - v_ref:+.4f}",
                "C2 YTD": format(v_ytd, fmt),
                "mvmt mercado (bp)": f"{mvmt:+.1f}" if pct else f"{v_ytd - v_pub:+.4f}",
            })

        df_comp = pd.DataFrame(rows_comp)

        def _color_bd(val):
            try:
                f = float(val)
                if abs(f) < 1:   return "color: #155724"
                if abs(f) < 20:  return "color: #856404"
                return "color: #721c24; font-weight: bold"
            except Exception:
                return ""

        styled_comp = (
            df_comp.style
            .map(_color_bd, subset=["gap BD (bp)", "mvmt mercado (bp)"])
            .set_properties(**{"text-align": "right"}, subset=["C1 ANEEL", "C1 Público", "gap BD (bp)", "C2 YTD", "mvmt mercado (bp)"])
            .set_properties(**{"text-align": "left"}, subset=["Parâmetro"])
        )
        st.dataframe(styled_comp, use_container_width=True, hide_index=True)

        # ── Downloads CSV ────────────────────────────────────────────────────
        st.markdown("**Downloads**")

        # Linha 1 — resumos por trilha
        dl1, dl2, dl3, dl4 = st.columns(4)
        dl1.download_button(
            "⬇ Comparativo trilhas",
            data=df_comp.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
            file_name="wacc_comparativo_trilhas.csv", mime="text/csv",
        )
        dl2.download_button(
            "⬇ C1 ANEEL (resumo)",
            data=pd.DataFrame([{"parametro": k, "valor": v} for k, v in REF.items()])
                .to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
            file_name="wacc_c1_aneel.csv", mime="text/csv",
        )
        dl3.download_button(
            "⬇ C1 Público (resumo)",
            data=pd.DataFrame([{"parametro": k, "valor": v} for k, v in c1pub.items()])
                .to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
            file_name="wacc_c1_publico.csv", mime="text/csv",
        )
        dl4.download_button(
            "⬇ C2 YTD (resumo)",
            data=pd.DataFrame([{"parametro": k, "valor": v} for k, v in c2ytd.items()])
                .to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
            file_name="wacc_c2_ytd.csv", mime="text/csv",
        )

        # Linha 2 — dados intermediários exaustivos (busca do objeto C2 e C3 em cache)
        _c2_full = get_camada2()
        _sp = _c2_full.snapshot_params

        dl5, dl6, dl7, dl8, dl9 = st.columns(5)

        # Rf por ano (NTN-B rolling 10a)
        _rf_det = _sp.get("rf_detalhes", [])
        if _rf_det:
            dl5.download_button(
                "⬇ Rf por ano",
                data=pd.DataFrame(_rf_det, columns=["ano", "rf_rolling_10a"])
                    .to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                file_name="wacc_rf_por_ano.csv", mime="text/csv",
            )

        # PRM por ano (S&P500 acumulado desde 1928)
        _prm_det = _sp.get("prm_detalhes", [])
        if _prm_det:
            dl6.download_button(
                "⬇ PRM por ano",
                data=pd.DataFrame(_prm_det, columns=["ano", "prm_acumulado_1928"])
                    .to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                file_name="wacc_prm_por_ano.csv", mime="text/csv",
            )

        # Beta por janela (4 Bloomberg + 1 yfinance)
        _bj = _sp.get("beta_janelas", [])
        if _bj:
            dl7.download_button(
                "⬇ Beta por janela",
                data=pd.DataFrame(_bj)
                    .to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                file_name="wacc_beta_por_janela.csv", mime="text/csv",
            )

        # Cesta de debêntures (classificação A/B/C/X)
        if _c2_full.kd_cesta_df is not None and not _c2_full.kd_cesta_df.empty:
            dl8.download_button(
                "⬇ Cesta debêntures",
                data=_c2_full.kd_cesta_df
                    .to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                file_name="wacc_cesta_debentures.csv", mime="text/csv",
            )

        # Vetor C3 completo
        _df3_exp = get_camada3(horizonte, (), kd_spec, rf_spot_projetado)
        dl9.download_button(
            "⬇ Vetor C3",
            data=_df3_exp.reset_index()
                .to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
            file_name="wacc_vetor_c3.csv", mime="text/csv",
        )

        st.divider()

        # ── Gráfico de barras agrupadas ──────────────────────────────────────
        st.markdown("#### Comparativo visual — taxas percentuais")
        PARAMS_PCT = [(n, k) for n, k, pct in PARAMS if pct and k not in ("ev", "dv")]
        nomes_g = [n for n, _ in PARAMS_PCT]
        keys_g  = [k for _, k in PARAMS_PCT]

        fig_trilhas = go.Figure()
        fig_trilhas.add_trace(go.Bar(
            name="C1 ANEEL (Bloomberg)",
            x=nomes_g, y=[REF[k] * 100 for k in keys_g],
            marker_color="#aec7e8",
            text=[f"{REF[k]:.2%}" for k in keys_g], textposition="outside",
        ))
        fig_trilhas.add_trace(go.Bar(
            name="C1 Público (mesma janela)",
            x=nomes_g, y=[c1pub[k] * 100 for k in keys_g],
            marker_color="#1f77b4",
            text=[f"{c1pub[k]:.2%}" for k in keys_g], textposition="outside",
        ))
        fig_trilhas.add_trace(go.Bar(
            name="C2 YTD (mercado atual)",
            x=nomes_g, y=[c2ytd[k] * 100 for k in keys_g],
            marker_color="#d62728",
            text=[f"{c2ytd[k]:.2%}" for k in keys_g], textposition="outside",
        ))
        fig_trilhas.update_layout(
            barmode="group", height=440,
            margin=dict(t=20, b=80),
            yaxis_title="Taxa (%)",
            legend=dict(orientation="h", y=1.05),
            xaxis_tickangle=-30,
        )
        st.plotly_chart(fig_trilhas, use_container_width=True)

        # ── Nota explicativa ─────────────────────────────────────────────────
        st.info(
            "**Por que o beta domina o gap de base de dados?**  \n"
            "O Bloomberg aplica ajustes proprietários a preços históricos (dividendos, splits, horário de fechamento de múltiplas bolsas) "
            "que o yfinance não replica com precisão. Para as utilities americanas usadas pela ANEEL, "
            "isso gera uma diferença de β_u ≈ −0,19 (yfinance subestima o risco relativo). "
            "Rf, ERP e EMBI são replicáveis com precisão ≤ 1bp via fontes públicas.  \n"
            "**Implicação:** a calculadora pública é válida para analisar movimento de mercado (C2), "
            "mas não pode replicar exatamente o beta do próximo despacho ANEEL sem Bloomberg.",
            icon="ℹ️",
        )

    except Exception as e:
        st.error(f"Erro ao calcular comparativo de trilhas: {e}")
        st.exception(e)

# ══════════════════════════════════════════════════════════════════════════════
# TAB CALC — Calculadora
# ══════════════════════════════════════════════════════════════════════════════
with tab_calc:
    import numpy as _np
    from wacc_regulatorio.wacc_calc import calcular_wacc as _calcular_wacc
    from wacc_regulatorio.data.fixtures import load_beta_historico as _load_beta_hist

    st.subheader("Calculadora WACC — Simulador de Parâmetros")
    st.caption(
        "Insira novos valores e veja: **instantâneo** (sem suavização das médias) e "
        "**regulatório** (convergência via médias móveis 5a/10a)"
    )

    # ── Defaults C1 ────────────────────────────────────────────────────────
    try:
        _r1c, _, _ = get_camada1()
        _RF0c, _ERP0c, _EMBI0c = _r1c.rf, _r1c.erp, _r1c.embi
        _BL0c, _BU0c = _r1c.beta_l, _r1c.beta_u
        _KD0c, _EV0c, _T0c, _W0c = _r1c.kd_real_ai, _r1c.ev, _r1c.T, _r1c.wacc_real_antes_impostos
    except Exception:
        _RF0c, _ERP0c, _EMBI0c = 0.05138, 0.06848, 0.02765
        _BL0c, _BU0c = 0.7692, 0.5030
        _KD0c, _EV0c, _T0c, _W0c = 0.06587, 0.6023, 0.34, 0.12115

    # ── Layout: inputs esquerda, métricas + cascata direita ────────────────
    col_i, col_o = st.columns([4, 7])

    with col_i:
        st.markdown("##### Parâmetros")
        rf_pct_c  = st.slider("Rf spot projetado (%)", 1.0, 12.0, round(_RF0c * 100, 1), 0.1,
                               key="calc_rf",
                               help="Taxa NTN-B para todos os anos futuros · entra na janela rolling 10a")
        erp_pct_c = st.slider("ERP — Prêmio de Risco (%)", 3.0, 12.0, round(_ERP0c * 100, 2), 0.05,
                               key="calc_erp")
        bl_c      = st.slider("Beta_l (alavancado)", 0.20, 1.50, round(_BL0c, 3), 0.001,
                               format="%.3f", key="calc_bl",
                               help="Converge via média móvel 5a: 4 janelas históricas + valor inserido")
        _kd_modo_c = st.radio("Modo Kd a.i.", ["Regressão (Kd ~ Rf)", "Manual"],
                               horizontal=True, key="calc_kd_modo")
        kd_pct_c  = st.slider("Kd a.i. (%)", 2.0, 15.0, round(_KD0c * 100, 2), 0.05,
                               disabled=(_kd_modo_c == "Regressão (Kd ~ Rf)"), key="calc_kd")
        ev_pct_c  = st.slider("E/V — Equity/Ativo (%)", 40.0, 70.0, round(_EV0c * 100, 2), 0.01,
                               key="calc_ev")
        hz_c      = st.slider("Horizonte (anos)", 5, 30, 20, 5, key="calc_hz")
        st.caption("ℹ️ EMBI implícito no beta. ERP congelado no despacho dentro do vetor.")

    # ── Conversão de unidades ─────────────────────────────────────────────
    rf_c  = rf_pct_c  / 100.0
    erp_c = erp_pct_c / 100.0
    ev_c  = ev_pct_c  / 100.0
    dv_c  = 1.0 - ev_c

    kd_c = (max(0.02, min(0.20, 0.03327 + 0.621 * rf_c))
            if _kd_modo_c == "Regressão (Kd ~ Rf)" else kd_pct_c / 100.0)

    # ── WACC instantâneo (sem suavização das médias) ──────────────────────
    _wi = _calcular_wacc(
        rf=rf_c, erp=erp_c, embi=_EMBI0c,
        beta_l=bl_c, beta_u=_BU0c,
        ev=ev_c, dv=dv_c, kd_real_ai=kd_c, T=_T0c,
    )
    _wacc_inst = _wi.wacc_real_antes_impostos
    _d_bp = (_wacc_inst - _W0c) * 10000

    # ── Beta histórico para construir a média móvel 5a no vetor ───────────
    try:
        _bl4 = tuple(_load_beta_hist().sort_values("ano").tail(4)["beta_l_brasil"].tolist())
    except Exception:
        _bl4 = (_BL0c,) * 4

    # ── Vetor de convergência (cacheado por parâmetros) ───────────────────
    try:
        _df_c   = _get_vetor_calculadora(rf_c, _bl4, bl_c, hz_c)
        _anos_c = [str(p) for p in _df_c.index]
        _wv     = _df_c["WACC_antes_impostos"].values
        _wv_eq  = float(_wv[-1])
        _conv_i = next((i for i, v in enumerate(_wv) if abs(v - _wv_eq) < 0.0005), hz_c)
        _vec_ok = True
    except Exception as _ve:
        st.error(f"Erro ao projetar vetor: {_ve}")
        _vec_ok = False

    # ── Métricas e cascata (coluna direita) ───────────────────────────────
    with col_o:
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("WACC_ai instantâneo", f"{_wacc_inst:.3%}",
                   delta=f"{_d_bp:+.1f}bp vs C1 pub",
                   delta_color="normal" if _d_bp < 0 else "inverse")
        mc2.metric("Δ vs C1 publicado", f"{_d_bp:+.0f}bp", delta_color="off")
        if _vec_ok:
            mc3.metric("WACC equilíbrio", f"{_wv_eq:.3%}",
                       delta=f"{(_wv_eq - _W0c)*10000:+.0f}bp vs C1", delta_color="off")
            mc4.metric("Anos p/ convergência", f"~{_conv_i}a",
                       help="|WACC_t − equilíbrio| < 5bp")

        # ── Cascata de contribuições ───────────────────────────────────────
        st.markdown("##### Cascata — C1 publicado → Calculadora")
        st.caption(
            "Efeito isolado de cada parâmetro, mantendo os demais no valor C1. "
            "Ordem: Rf → ERP → β_l → Kd → E/V."
        )

        def _ws(**kw):
            p = dict(rf=_RF0c, erp=_ERP0c, bl=_BL0c, kd=_KD0c, ev=_EV0c)
            p.update(kw)
            ev_ = p["ev"]
            return _calcular_wacc(
                rf=p["rf"], erp=p["erp"], embi=_EMBI0c,
                beta_l=p["bl"], beta_u=_BU0c,
                ev=ev_, dv=1 - ev_, kd_real_ai=p["kd"], T=_T0c,
            ).wacc_real_antes_impostos

        _s = [
            _W0c,
            _ws(rf=rf_c),
            _ws(rf=rf_c, erp=erp_c),
            _ws(rf=rf_c, erp=erp_c, bl=bl_c),
            _ws(rf=rf_c, erp=erp_c, bl=bl_c, kd=kd_c),
            _ws(rf=rf_c, erp=erp_c, bl=bl_c, kd=kd_c, ev=ev_c),
        ]
        _wf_x = ["C1 pub.", "ΔRf", "ΔERP", "ΔBeta_l", "ΔKd_ai", "ΔE/V", "Calc."]
        _wf_y = [_s[0]] + [_s[i] - _s[i-1] for i in range(1, 6)] + [0]
        _wf_t = [f"{_s[0]:.2%}"] + [f"{(_s[i]-_s[i-1])*10000:+.0f}bp" for i in range(1,6)] + [f"{_s[-1]:.2%}"]

        _fig_wf = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute","relative","relative","relative","relative","relative","total"],
            x=_wf_x, y=[v * 100 for v in _wf_y],
            connector={"line": {"color": "rgb(63,63,63)"}},
            increasing={"marker": {"color": "#d62728"}},
            decreasing={"marker": {"color": "#2ca02c"}},
            totals={"marker": {"color": "#1f77b4"}},
            text=_wf_t, textposition="outside",
        ))
        _fig_wf.update_layout(
            height=360, margin=dict(t=20, b=20),
            yaxis_tickformat=".2f", yaxis_title="WACC a.i. (%)",
            showlegend=False,
        )
        st.plotly_chart(_fig_wf, use_container_width=True)

    # ── Vetor de convergência (largura total) ─────────────────────────────
    if _vec_ok:
        st.divider()
        st.markdown("##### Vetor de convergência regulatória")
        st.info(
            "**Ponto de partida (2026):** sempre próximo ao C1 publicado (12,11%) — a janela rolling "
            "ainda está preenchida com dados históricos. O vetor converge ao equilíbrio à medida que "
            "os novos valores entram: **β_l em ~5 anos** (média móvel 5a) e **Rf em ~10 anos** "
            "(média móvel 10a).  \n"
            "**⭐ laranja** = WACC instantâneo com seus parâmetros, sem suavização regulatória.",
            icon="ℹ️",
        )

        _fig_v = go.Figure()

        # Linha do vetor calculadora
        _fig_v.add_trace(go.Scatter(
            x=_anos_c, y=_wv * 100, mode="lines+markers",
            name="Vetor calculadora",
            line=dict(color="#1f77b4", width=2.5), marker=dict(size=5),
            hovertemplate="%{x}: %{y:.2f}%<extra>Vetor</extra>",
        ))

        # Linha de referência C1 publicado
        _fig_v.add_hline(
            y=_W0c * 100, line_dash="dash", line_color="gray",
            annotation_text=f"C1 publicado ({_W0c:.3%})",
            annotation_position="top right",
        )

        # Ponto instantâneo (antes da suavização)
        _fig_v.add_trace(go.Scatter(
            x=[_anos_c[0]], y=[_wacc_inst * 100], mode="markers",
            name=f"Instantâneo ({_wacc_inst:.2%})",
            marker=dict(color="#ff7f0e", size=16, symbol="star"),
            hovertemplate=f"WACC instantâneo: {_wacc_inst:.3%}<extra></extra>",
        ))

        # Linhas de convergência
        _ib = min(4, len(_anos_c) - 1)
        _ir = min(10, len(_anos_c) - 1)
        _fig_v.add_vline(x=_anos_c[_ib], line_dash="dot", line_color="#9467bd",
                         annotation_text="β converge (~5a)", annotation_position="top left")
        if _ir < len(_anos_c):
            _fig_v.add_vline(x=_anos_c[_ir], line_dash="dot", line_color="#8c564b",
                             annotation_text="Rf converge (~10a)", annotation_position="top left")

        # Anotação de equilíbrio
        _fig_v.add_annotation(
            x=_anos_c[-1], y=_wv_eq * 100,
            text=f"Equilíbrio: {_wv_eq:.2%}",
            showarrow=True, arrowhead=2, arrowcolor="#1f77b4",
            font=dict(color="#1f77b4", size=11), ax=-70, ay=-30,
        )

        _fig_v.update_layout(
            height=440, margin=dict(t=40, b=20),
            yaxis_ticksuffix="%", yaxis_title="WACC a.i. (%)",
            legend=dict(orientation="h", y=1.05),
            hovermode="x unified",
        )
        st.plotly_chart(_fig_v, use_container_width=True)

        # Tabela do vetor
        with st.expander("Tabela do vetor", expanded=False):
            _df_disp = _df_c.reset_index(drop=True).copy()
            _df_disp.insert(0, "Ano", _anos_c)
            for _c in ["Rf", "ERP", "Ke_real_di", "Kd_real_ai",
                        "WACC_depois_impostos", "WACC_antes_impostos"]:
                if _c in _df_disp.columns:
                    _df_disp[_c] = _df_disp[_c].map("{:.4%}".format)
            if "Beta_l" in _df_disp.columns:
                _df_disp["Beta_l"] = _df_disp["Beta_l"].map("{:.4f}".format)
            _show = [c for c in ["Ano", "Rf", "Beta_l", "Ke_real_di", "Kd_real_ai",
                                   "WACC_depois_impostos", "WACC_antes_impostos"]
                     if c in _df_disp.columns]
            st.dataframe(_df_disp[_show], hide_index=True, use_container_width=True)

        st.download_button(
            "⬇ Download vetor CSV",
            data=_df_c.reset_index().to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
            file_name="wacc_calculadora_vetor.csv", mime="text/csv",
        )


with tab5:
    st.subheader("Metodologia — Despacho ANEEL 675/2026")
    st.caption("Fonte: WACC_Regulatorio_Whitepaper.md · Atualizado automaticamente")

    wp_text = _load_whitepaper()

    if not wp_text:
        st.warning("Whitepaper não encontrado. Certifique-se de que `WACC_Regulatorio_Whitepaper.md` está na mesma pasta que `dashboard.py`.")
    else:
        m1, m2, m3, m4 = st.tabs([
            "C1 — Replicação ANEEL",
            "C2 — WACC Corrente",
            "C3 — Vetor 30 anos",
            "Referências",
        ])

        with m1:
            st.markdown("### Contexto regulatório e parâmetros")
            # Seções 1, 2 e 3 (contexto, metodologia por parâmetro, montagem do WACC)
            sec1 = _extract_section(wp_text, "## 1. Contexto Regulatório", "## 4. Arquitetura")
            st.markdown(sec1)

        with m2:
            st.markdown("### Camada 2 — WACC Corrente Implícito")
            # Descrição C2 da seção 4.1
            c2_desc = _extract_section(wp_text, "Camada 2 — WACC corrente implícito", "Camada 3 — Vetor projetado")
            st.markdown(f"```\n{c2_desc.strip()}\n```")
            st.divider()
            st.markdown("### Limitações da Camada 2")
            lim_prm = _extract_section(wp_text, "### 7.3 PRM", "### 7.4")
            lim_beta = _extract_section(wp_text, "### 7.4 Beta C2", "### 7.5")
            st.markdown(lim_prm)
            st.markdown(lim_beta)
            st.info(
                "**Beta C2:** ponderação por **D/V contábil** (dívida/(dívida+PL contábil), cap 50%) — "
                "metodologia ANEEL confirmada via leitura direta da aba Beta do xlsx (coluna 'Ponderado 50%'). "
                "Prova: pesos D/V do xlsx + betas do xlsx → beta_u = 0,293106 (0,0bp). "
                "C2 usa metodologia **4+1 híbrido**: 4 janelas Bloomberg do xlsx ANEEL (2022–2025) + 1 janela yfinance ao vivo (2026). "
                "Gap BD residual: apenas janela 2026 (yfinance vs Bloomberg ≈ −48bp/janela ÷ 5 = −9,6bp em β_l, −6bp no WACC_ai). "
                "β_l C1 ANEEL (0,7692) vem de `calcular_beta_from_historico()` → média das 5 janelas mais recentes de β_l_brasil (xlsx ANEEL).",
                icon="ℹ️",
            )

        with m3:
            st.markdown("### Arquitetura das três camadas")
            arq = _extract_section(wp_text, "### 4.1 Três camadas funcionais", "### 4.2")
            st.markdown(arq)
            st.divider()
            st.markdown("### Relação C1 · C2 · C3 e convergência")
            rel = _extract_section(wp_text, "### 4.2 Relação C1 · C2 · C3", "### 4.3")
            st.markdown(rel)
            st.divider()
            st.markdown("### Rf na Camada 3 — dupla suavização projetada")
            rf_c3 = _extract_section(wp_text, "### 4.3 Rf na Camada 3", "### 4.4")
            st.markdown(rf_c3)
            st.divider()
            st.markdown("### Janela rolante e incerteza crescente")
            lim_jan = _extract_section(wp_text, "### 7.1 Janela rolante", "### 7.2")
            lim_rf  = _extract_section(wp_text, "### 7.2 rf_spot_projetado", "### 7.3")
            st.markdown(lim_jan)
            st.markdown(lim_rf)

        with m4:
            refs = _extract_section(wp_text, "## 8. Referências")
            st.markdown(refs)
