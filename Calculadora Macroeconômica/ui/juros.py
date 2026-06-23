"""
Aba Curva de Juros:
  · DI Futuro B3 (preços de mercado dos contratos DI1)
  · SELIC Focus por reunião COPOM (consensus survey ~150 instituições)
  · Curva PRE zero-coupon ANBIMA (bootstrapped de DI + LTN/NTN-F)
  · Taxa real implícita (SELIC Focus vs BEI ANBIMA)
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from collectors.focus_selic import fetch_selic_curve
from collectors.anbima_ettj import AnbimaETTJError, fetch_ettj
from collectors.b3_di1 import B3DI1Unavailable, fetch_di1_curve


_FONT = "#1a1a2e"
_GRID = "rgba(150,150,170,0.30)"
_BG   = "rgba(245,245,250,1)"


def render_juros_tab() -> None:
    st.header("Curva de Juros")
    st.caption(
        "**DI Futuro B3** (preços de mercado, intraday) · "
        "**SELIC Focus** por reunião COPOM (consensus ~150 instituições) · "
        "**PRE ANBIMA** zero-coupon (bootstrapped de DI + LTN/NTN-F)"
    )

    col_btn, _ = st.columns([1, 5])
    with col_btn:
        force = st.button("🔄 Atualizar", use_container_width=True, key="juros_refresh")

    with st.spinner("Buscando dados..."):
        try:
            df_selic = fetch_selic_curve(force_refresh=force)
        except Exception as e:
            st.error(f"**Focus indisponível:** {e}")
            return

        try:
            df_ettj, ettj_date = fetch_ettj(force_refresh=force)
        except AnbimaETTJError:
            df_ettj, ettj_date = pd.DataFrame(), None

        try:
            df_di1, di1_date, di1_fonte = fetch_di1_curve(force_refresh=force)
        except B3DI1Unavailable:
            df_di1, di1_date, di1_fonte = pd.DataFrame(), None, None

    if df_selic.empty:
        st.warning("Sem dados de expectativa SELIC disponíveis.")
        return

    survey_date = df_selic["data_survey"].iloc[0]
    partes = [f"Focus: **{pd.Timestamp(survey_date).strftime('%d/%m/%Y')}**"]
    if ettj_date:
        partes.append(f"ETTJ: **{ettj_date.strftime('%d/%m/%Y')}**")
    if di1_date:
        tag = "intraday" if di1_fonte == "intraday" else f"histórico {di1_date.strftime('%d/%m/%Y')}"
        partes.append(f"DI1 B3: **{tag}**")
    st.caption(" · ".join(partes))

    if di1_fonte == "historico_pyield":
        st.warning(
            f"⚠️ DI Futuro: usando dado histórico de **{di1_date.strftime('%d/%m/%Y')}** "
            "(API intraday B3 indisponível). Preços podem diferir do mercado atual.",
            icon="📅",
        )

    _render_summary_metrics(df_selic, df_ettj)

    st.divider()
    _render_chart(df_selic, df_ettj, df_di1)
    st.divider()

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        with st.expander("Dados Focus por reunião", expanded=False):
            _render_table(df_selic)
    with col_exp2:
        with st.expander("Dados DI Futuro B3", expanded=False):
            _render_di1_table(df_di1)


# ---------------------------------------------------------------------------
# Métricas de resumo
# ---------------------------------------------------------------------------

def _render_summary_metrics(df: pd.DataFrame, ettj: pd.DataFrame) -> None:
    next_meeting = df.iloc[0]
    last_meeting = df.iloc[-1]

    selic_next  = next_meeting["mediana"]
    selic_last  = last_meeting["mediana"]
    horizonte   = last_meeting["reuniao"]

    # Taxa real: SELIC next meeting vs BEI ETTJ no mesmo horizonte
    real_rate_str = "—"
    if not ettj.empty:
        bei_df = ettj.dropna(subset=["bei_pct"])
        if not bei_df.empty:
            du = int(next_meeting["du_ahead"])
            idx = (bei_df["vertice_du"] - du).abs().idxmin()
            bei = float(bei_df.loc[idx, "bei_pct"])
            rr  = (1 + selic_next / 100) / (1 + bei / 100) - 1
            real_rate_str = f"{rr * 100:.2f}%"

    cols = st.columns(4)
    cols[0].metric("Próxima reunião", next_meeting["reuniao"],
                   help=f"Data estimada: {pd.Timestamp(next_meeting['data_reuniao']).strftime('%d/%m/%Y')}")
    cols[1].metric("SELIC esperada (próxima)", f"{selic_next:.2f}%")
    cols[2].metric(f"SELIC em {horizonte}", f"{selic_last:.2f}%",
                   delta=f"{selic_last - selic_next:+.2f} p.p. vs próxima")
    cols[3].metric("Juro real implícito (próx.)", real_rate_str,
                   help="(1 + SELIC Focus) / (1 + BEI ANBIMA) − 1, no mesmo prazo")


# ---------------------------------------------------------------------------
# Gráfico principal (2 painéis)
# ---------------------------------------------------------------------------

def _render_chart(df_selic: pd.DataFrame, df_ettj: pd.DataFrame, df_di1: pd.DataFrame) -> None:
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=False,
        row_heights=[0.55, 0.45],
        vertical_spacing=0.12,
    )

    # ── Painel 1: Curva SELIC por reunião ──────────────────────────────────
    x_dates = [pd.Timestamp(d) for d in df_selic["data_reuniao"]]

    # DI Futuro B3 — pontos de mercado (taxa de ajuste por vencimento)
    if not df_di1.empty:
        di1_x = [pd.Timestamp(d) for d in df_di1["expiration_date"]]
        fig.add_trace(go.Scatter(
            x=di1_x,
            y=df_di1["taxa_aa"],
            mode="markers",
            name="DI Futuro B3 (ajuste)",
            marker=dict(
                size=7, symbol="circle",
                color="#555577",
                opacity=0.75,
                line=dict(width=1, color="white"),
            ),
            hovertemplate="<b>%{customdata}</b><br>DI1: %{y:.3f}% a.a.<extra></extra>",
            customdata=df_di1["symb"],
        ), row=1, col=1)

    # Faixa min-máx como área
    fig.add_trace(go.Scatter(
        x=x_dates + x_dates[::-1],
        y=list(df_selic["maximo"]) + list(df_selic["minimo"])[::-1],
        fill="toself",
        fillcolor="rgba(41,128,185,0.10)",
        line=dict(width=0),
        showlegend=True,
        name="Intervalo (mín–máx)",
        hoverinfo="skip",
    ), row=1, col=1)

    # Linha mediana SELIC
    fig.add_trace(go.Scatter(
        x=x_dates,
        y=df_selic["mediana"],
        mode="lines+markers",
        name="SELIC esperada (mediana Focus)",
        line=dict(color="#1a6faf", width=3),
        marker=dict(size=9, symbol="circle", color="#1a6faf",
                    line=dict(width=2, color="white")),
        hovertemplate="<b>%{customdata}</b><br>SELIC: %{y:.2f}% a.a.<extra></extra>",
        customdata=df_selic["reuniao"],
    ), row=1, col=1)

    # Curva PRE ANBIMA overlay (se disponível)
    if not df_ettj.empty:
        pre_df = df_ettj.dropna(subset=["pre_pct"])
        if not pre_df.empty:
            today_ts = pd.Timestamp(date.today())
            pre_x = [today_ts + pd.Timedelta(days=round(a * 365.25))
                     for a in pre_df["vertice_anos"]]
            fig.add_trace(go.Scatter(
                x=pre_x,
                y=pre_df["pre_pct"],
                mode="lines",
                name="PRE zero-coupon ANBIMA",
                line=dict(color="#2980b9", width=1.5, dash="dot"),
                hovertemplate="PRE %{y:.2f}% a.a.<extra></extra>",
            ), row=1, col=1)

    # ── Painel 2: Taxa real implícita ──────────────────────────────────────
    if not df_ettj.empty:
        bei_df = df_ettj.dropna(subset=["bei_pct"])
        if not bei_df.empty:
            real_rates, bei_used = [], []
            for _, row in df_selic.iterrows():
                du = int(row["du_ahead"])
                idx = (bei_df["vertice_du"] - du).abs().idxmin()
                bei = float(bei_df.loc[idx, "bei_pct"])
                rr  = (1 + row["mediana"] / 100) / (1 + bei / 100) - 1
                real_rates.append(rr * 100)
                bei_used.append(bei)

            # Juro real implícito
            fig.add_trace(go.Scatter(
                x=x_dates,
                y=real_rates,
                mode="lines+markers",
                name="Juro real implícito (SELIC Focus − BEI ANBIMA)",
                line=dict(color="#27ae60", width=3),
                marker=dict(size=8, symbol="circle", color="#27ae60",
                            line=dict(width=2, color="white")),
                hovertemplate="<b>%{customdata}</b><br>Real: %{y:.2f}% a.a.<extra></extra>",
                customdata=df_selic["reuniao"],
            ), row=2, col=1)

            # IPCA+ ANBIMA para comparação
            ipca_df = df_ettj.dropna(subset=["ipca_pct"])
            if not ipca_df.empty:
                today_ts = pd.Timestamp(date.today())
                ipca_x = [today_ts + pd.Timedelta(days=round(a * 365.25))
                          for a in ipca_df["vertice_anos"]]
                fig.add_trace(go.Scatter(
                    x=ipca_x,
                    y=ipca_df["ipca_pct"],
                    mode="lines",
                    name="IPCA+ ANBIMA (juro real via bonds)",
                    line=dict(color="#27ae60", width=1.5, dash="dot"),
                    hovertemplate="IPCA+ %{y:.2f}% a.a.<extra></extra>",
                ), row=2, col=1)

    # ── Eixos e layout ──────────────────────────────────────────────────────
    _axis_style = dict(
        color=_FONT, tickfont=dict(color=_FONT, size=12),
        linecolor=_FONT, showgrid=True, gridcolor=_GRID,
    )

    fig.update_xaxes(**_axis_style, tickformat="%b/%Y", row=1, col=1)
    fig.update_xaxes(**_axis_style, tickformat="%b/%Y", title_text="Reunião COPOM", row=2, col=1)

    selic_vals = list(df_selic["maximo"]) + list(df_selic["minimo"])
    fig.update_yaxes(**_axis_style, title_text="% a.a.", tickformat=".1f", ticksuffix="%",
                     range=[min(selic_vals) - 0.5, max(selic_vals) + 0.5], row=1, col=1)

    if not df_ettj.empty and "real_rates" in dir():
        pass  # real_rates computed above
    fig.update_yaxes(**_axis_style, title_text="% a.a.", tickformat=".1f", ticksuffix="%",
                     row=2, col=1)

    fig.update_layout(
        hovermode="x unified",
        font=dict(color=_FONT, family="sans-serif"),
        legend=dict(
            orientation="h", yanchor="top", y=-0.08, xanchor="left", x=0,
            font=dict(size=12, color=_FONT),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="rgba(150,150,150,0.4)", borderwidth=1,
        ),
        margin=dict(l=10, r=30, t=40, b=80),
        height=580,
        plot_bgcolor=_BG,
        paper_bgcolor="white",
    )

    _ann = dict(xref="paper", yref="paper", showarrow=False,
                font=dict(color=_FONT, size=13), xanchor="center")
    fig.add_annotation(**_ann, text="SELIC esperada por reunião COPOM (Focus)", x=0.5, y=1.02)
    fig.add_annotation(**_ann, text="Juro Real Implícito (SELIC Focus vs BEI ANBIMA)", x=0.5, y=0.42)

    st.plotly_chart(fig, use_container_width=True)

    st.info(
        "**Como ler:** "
        "Pontos cinza = **DI Futuro B3** (taxa de ajuste por vencimento do contrato, preço de mercado). "
        "Linha azul = **SELIC Focus** (mediana de ~150 instituições por reunião COPOM). "
        "Pontilhado azul = **PRE ANBIMA** zero-coupon (bootstrapped de DI + LTN/NTN-F). "
        "Quando DI Futuro e SELIC Focus divergem, existe discrepância entre mercado e survey. "
        "Painel inferior: juro real = `(1 + SELIC) / (1 + BEI ANBIMA) − 1`.",
        icon="ℹ️",
    )


# ---------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------

def _render_di1_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Dados DI1 B3 não disponíveis.")
        return
    display = df[["symb", "expiration_date", "anos", "taxa_aa", "open_contracts"]].copy()
    display.columns = ["Contrato", "Vencimento", "Anos", "Taxa (% a.a.)", "Contratos abertos"]
    display["Vencimento"] = display["Vencimento"].apply(
        lambda d: pd.Timestamp(d).strftime("%d/%m/%Y"))
    st.dataframe(
        display, use_container_width=True, hide_index=True,
        column_config={
            "Anos":             st.column_config.NumberColumn(format="%.2f"),
            "Taxa (% a.a.)":    st.column_config.NumberColumn(format="%.3f"),
            "Contratos abertos": st.column_config.NumberColumn(format="%d"),
        },
    )
    csv = display.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button("⬇️ CSV", data=csv,
                       file_name=f"di1_{date.today().strftime('%Y%m%d')}.csv",
                       mime="text/csv")


def _render_table(df: pd.DataFrame) -> None:
    display = df.copy()
    display["Reunião"]     = display["reuniao"]
    display["Data est."]   = display["data_reuniao"].apply(
        lambda d: pd.Timestamp(d).strftime("%d/%m/%Y"))
    display["Anos"]        = display["anos_ahead"]
    display["Mediana (%)"] = display["mediana"]
    display["Mín (%)"]     = display["minimo"]
    display["Máx (%)"]     = display["maximo"]
    display["Respondentes"] = display["n_respondentes"]

    cols = ["Reunião", "Data est.", "Anos", "Mediana (%)", "Mín (%)", "Máx (%)", "Respondentes"]
    st.dataframe(
        display[cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Anos":         st.column_config.NumberColumn(format="%.2f"),
            "Mediana (%)":  st.column_config.NumberColumn(format="%.2f"),
            "Mín (%)":      st.column_config.NumberColumn(format="%.2f"),
            "Máx (%)":      st.column_config.NumberColumn(format="%.2f"),
            "Respondentes": st.column_config.NumberColumn(format="%d"),
        },
    )

    csv = display[cols].to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button("⬇️ CSV", data=csv,
                       file_name=f"selic_copom_{date.today().strftime('%Y%m%d')}.csv",
                       mime="text/csv")
