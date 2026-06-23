"""Aba ETTJ — Estrutura a Termo da Taxa de Juros (ANBIMA) com inflação implícita."""
import io

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from collectors.anbima_ettj import AnbimaETTJError, fetch_ettj


_HORIZONTE_ANOS = {"5a": 5, "10a": 10, "15a": 15, "Completo": 999}


def render_ettj_tab() -> None:
    st.header("ETTJ — Estrutura a Termo / Inflação Implícita")
    st.caption(
        "Curvas zero-coupon da ANBIMA (mercado secundário). "
        "**PRE** = CDI/SELIC implícito (DI futuro / LTN / NTN-F). "
        "**IPCA+** = taxa real de juros (NTN-B). "
        "**Inflação Implícita (BEI)** = break-even PRE − IPCA+, calculado pela ANBIMA."
    )

    col_btn, col_hz, _ = st.columns([1, 2, 4])
    with col_btn:
        force_refresh = st.button("🔄 Atualizar", use_container_width=True, key="ettj_refresh")
    with col_hz:
        horizonte_label = st.radio(
            "Horizonte",
            options=list(_HORIZONTE_ANOS),
            index=1,
            horizontal=True,
            key="ettj_horizonte",
        )

    with st.spinner("Buscando dados da ANBIMA..."):
        try:
            df, ref_date = fetch_ettj(force_refresh=force_refresh)
        except AnbimaETTJError as e:
            st.error(
                f"**Dados ANBIMA indisponíveis:** {e}\n\n"
                "Verifique sua conexão e tente novamente."
            )
            return

    st.caption(f"Data de referência: **{ref_date.strftime('%d/%m/%Y')}** · Fonte: ANBIMA")

    max_anos = _HORIZONTE_ANOS[horizonte_label]
    df_view = df[df["vertice_anos"] <= max_anos].copy()

    st.divider()
    _render_chart(df_view)
    st.divider()

    with st.expander("Dados por vértice", expanded=False):
        _render_table(df, ref_date)

    with st.expander("Validação da curva de forwards", expanded=False):
        _render_forward_validation(df)


# ---------------------------------------------------------------------------
# Gráfico — dois painéis para separar escalas incompatíveis
# ---------------------------------------------------------------------------

def _render_chart(df: pd.DataFrame) -> None:
    """
    Dois subplots verticais para evitar a compressão causada pela diferença
    de escala entre PRE (~14%) e IPCA+/BEI (5-9%).

    Painel superior: PRE e BEI (ambos com dados até ~10 anos)
    Painel inferior: IPCA+ taxa real (NTN-B, curva completa)
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.5, 0.5],
        vertical_spacing=0.10,
    )

    tick_vals, tick_text = _build_x_ticks(df)

    # --- Painel 1: PRE + BEI ---
    pre_df = df.dropna(subset=["pre_pct"])
    if not pre_df.empty:
        fig.add_trace(go.Scatter(
            x=pre_df["vertice_anos"],
            y=pre_df["pre_pct"],
            mode="lines+markers",
            name="PRE / CDI implícito",
            line=dict(color="#1a6faf", width=3),
            marker=dict(size=7, symbol="circle"),
            hovertemplate="<b>PRE</b> %{x:.1f}a: %{y:.2f}% a.a.<extra></extra>",
        ), row=1, col=1)

    bei_df = df.dropna(subset=["bei_pct"])
    if not bei_df.empty:
        fig.add_trace(go.Scatter(
            x=bei_df["vertice_anos"],
            y=bei_df["bei_pct"],
            mode="lines+markers",
            name="Inflação Implícita (BEI)",
            line=dict(color="#e67e22", width=2.5, dash="dash"),
            marker=dict(size=6, symbol="diamond"),
            hovertemplate="<b>BEI</b> %{x:.1f}a: %{y:.2f}% a.a.<extra></extra>",
        ), row=1, col=1)

    # --- Painel 2: IPCA+ ---
    ipca_df = df.dropna(subset=["ipca_pct"])
    fig.add_trace(go.Scatter(
        x=ipca_df["vertice_anos"],
        y=ipca_df["ipca_pct"],
        mode="lines+markers",
        name="IPCA+ (taxa real)",
        line=dict(color="#27ae60", width=3),
        marker=dict(size=7, symbol="circle"),
        hovertemplate="<b>IPCA+</b> %{x:.1f}a: %{y:.2f}% a.a.<extra></extra>",
    ), row=2, col=1)

    _FONT_COLOR = "#1a1a2e"
    _GRID_COLOR = "rgba(150,150,170,0.35)"

    # Eixo X compartilhado
    x_range = [0, df["vertice_anos"].max() + 0.5]
    # `color` no eixo define de uma vez: linha, tick e título.
    # `titlefont` não existe nessa versão do Plotly — usar `color` + `tickfont` explícito.
    _xaxis_common = dict(
        tickvals=tick_vals,
        ticktext=tick_text,
        showgrid=True,
        gridcolor=_GRID_COLOR,
        range=x_range,
        color=_FONT_COLOR,
        tickfont=dict(color=_FONT_COLOR, size=12),
        linecolor=_FONT_COLOR,
    )
    fig.update_xaxes(**_xaxis_common, title_text="Prazo", row=2, col=1)
    fig.update_xaxes(**_xaxis_common, row=1, col=1)

    # Eixo Y — painel superior (PRE + BEI)
    all_p1 = pd.concat([
        df["pre_pct"].dropna(),
        df["bei_pct"].dropna(),
    ])
    if not all_p1.empty:
        fig.update_yaxes(
            title_text="% a.a.",
            tickformat=".1f",
            ticksuffix="%",
            showgrid=True,
            gridcolor=_GRID_COLOR,
            range=[all_p1.min() - 0.5, all_p1.max() + 0.5],
            color=_FONT_COLOR,
            tickfont=dict(color=_FONT_COLOR, size=12),
            linecolor=_FONT_COLOR,
            row=1, col=1,
        )

    # Eixo Y — painel inferior (IPCA+)
    ipca_vals = df["ipca_pct"].dropna()
    if not ipca_vals.empty:
        fig.update_yaxes(
            title_text="% a.a.",
            tickformat=".1f",
            ticksuffix="%",
            showgrid=True,
            gridcolor=_GRID_COLOR,
            range=[ipca_vals.min() - 0.3, ipca_vals.max() + 0.3],
            color=_FONT_COLOR,
            tickfont=dict(color=_FONT_COLOR, size=12),
            linecolor=_FONT_COLOR,
            row=2, col=1,
        )

    # title_font em update_layout instancia um objeto title com texto vazio,
    # que o Plotly.js serializa como "undefined". Usar apenas font= (global).
    fig.update_layout(
        hovermode="x unified",
        font=dict(color=_FONT_COLOR, family="sans-serif"),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.08,
            xanchor="left",
            x=0,
            font=dict(size=13, color=_FONT_COLOR),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="rgba(150,150,150,0.4)",
            borderwidth=1,
        ),
        margin=dict(l=10, r=30, t=40, b=70),
        height=560,
        plot_bgcolor="rgba(245,245,250,1)",
        paper_bgcolor="white",
    )

    # Títulos dos painéis — anotações manuais com estilo uniforme
    _ann = dict(
        xref="paper", yref="paper", showarrow=False,
        font=dict(color=_FONT_COLOR, size=13, family="sans-serif"),
        xanchor="center",
    )
    fig.add_annotation(**_ann, text="PRE / CDI Implícito e Inflação Implícita (BEI)", x=0.5, y=1.02)
    fig.add_annotation(**_ann, text="IPCA+ (taxa real)", x=0.5, y=0.46)

    st.plotly_chart(fig, use_container_width=True)

    # Leitura rápida das curvas no vértice mais curto e mais longo disponível
    _render_snapshot_metrics(df)


def _render_forward_validation(df: pd.DataFrame) -> None:
    """
    Tabela de decomposição da curva BEI em forwards implícitos, com verificação
    de que o acúmulo dos forwards reconstitui os spots originais (identidade aritmética).
    """
    from engine.projector import _bei_forward_intervals, _forward_for_du

    st.markdown(
        "**O que esta tabela valida:** os forwards implícitos são calculados por "
        "bootstrapping da curva BEI spot. O acúmulo desses forwards deve reconstituir "
        "exatamente os spots originais da ANBIMA — qualquer desvio indica bug no cálculo."
    )

    bei = df.dropna(subset=["bei_pct"]).sort_values("vertice_du").reset_index(drop=True)
    if bei.empty:
        st.warning("Sem dados BEI para validar.")
        return

    intervals = _bei_forward_intervals(bei)

    rows_val = []
    fator_acum = 1.0
    anos_prev  = 0.0

    for i, row in bei.iterrows():
        du   = float(row["vertice_du"])
        spot = float(row["bei_pct"])
        anos = du / 252

        lo = float(bei.loc[i - 1, "vertice_du"]) if i > 0 else 0.0
        fwd = _forward_for_du(intervals, (lo + du) / 2)

        delta = anos - anos_prev
        fator_acum *= (1 + fwd / 100) ** delta
        spot_rec = (fator_acum ** (1 / anos) - 1) * 100
        erro_bp  = (spot_rec - spot) * 100  # basis points

        taxa_mensal = ((1 + fwd / 100) ** (1 / 12) - 1) * 100

        rows_val.append({
            "Vértice (du)":        int(du),
            "Prazo":               _anos_label(anos),
            "BEI spot (% a.a.)":   round(spot, 4),
            "Forward impl. (% a.a.)": round(fwd, 4),
            "Taxa mensal (%)":     round(taxa_mensal, 4),
            "Spot reconstruído":   round(spot_rec, 6),
            "Erro (bp)":           round(erro_bp, 6),
        })
        anos_prev = anos

    val_df = pd.DataFrame(rows_val)
    max_erro = val_df["Erro (bp)"].abs().max()

    if max_erro < 0.01:
        st.success(
            f"Reconstrução OK — erro máximo: **{max_erro:.2e} bp** "
            f"(tolerância: 0,01 bp). Os forwards reconstituem os spots com precisão numérica.",
            icon="✅",
        )
    else:
        st.error(f"Erro de reconstrução elevado: {max_erro:.4f} bp. Verificar código.", icon="❌")

    st.dataframe(
        val_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Vértice (du)":           st.column_config.NumberColumn(format="%d"),
            "BEI spot (% a.a.)":      st.column_config.NumberColumn(format="%.4f"),
            "Forward impl. (% a.a.)": st.column_config.NumberColumn(format="%.4f"),
            "Taxa mensal (%)":        st.column_config.NumberColumn(format="%.4f"),
            "Spot reconstruído":      st.column_config.NumberColumn(format="%.6f"),
            "Erro (bp)":              st.column_config.NumberColumn(format="%.2e"),
        },
    )

    st.caption(
        "**Interpretação das colunas:** "
        "*BEI spot* = taxa publicada pela ANBIMA. "
        "*Forward implícito* = taxa marginal entre vértices consecutivos (bootstrap). "
        "*Taxa mensal* = `(1 + fwd/100)^(1/12) − 1`, usada na projeção mês a mês. "
        "*Spot reconstruído* = acúmulo dos forwards até esse vértice, deve igualar o spot. "
        "*Erro* = diferença em basis points — esperado < 0,01 bp."
    )


def _build_x_ticks(df: pd.DataFrame) -> tuple[list, list]:
    max_anos = df["vertice_anos"].max()
    candidates = [0.5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 25, 30, 33.5]
    tick_vals = [v for v in candidates if v <= max_anos + 0.5]
    tick_text = [_anos_label(v) for v in tick_vals]
    return tick_vals, tick_text


def _anos_label(anos: float) -> str:
    if anos < 1:
        return f"{round(anos * 12)}m"
    return f"{int(anos)}a" if anos == int(anos) else f"{anos:.1f}a"


def _render_snapshot_metrics(df: pd.DataFrame) -> None:
    """Mostra leitura pontual nos vértices de 1a, 5a e 10a (quando disponíveis)."""
    pontos = {1: "1 ano", 5: "5 anos", 10: "10 anos"}
    cols = st.columns(len(pontos))
    for col, (anos_alvo, label) in zip(cols, pontos.items()):
        sub = df[df["vertice_anos"] == float(anos_alvo)]
        if sub.empty:
            sub = df.iloc[(df["vertice_anos"] - anos_alvo).abs().argsort()[:1]]
        row = sub.iloc[0]
        ipca = f"{row['ipca_pct']:.2f}%" if pd.notna(row["ipca_pct"]) else "—"
        pre  = f"{row['pre_pct']:.2f}%"  if pd.notna(row["pre_pct"])  else "—"
        bei  = f"{row['bei_pct']:.2f}%"  if pd.notna(row["bei_pct"])  else "—"
        with col:
            st.markdown(f"**{label}**")
            st.markdown(
                f"IPCA+ **{ipca}** · PRE **{pre}** · BEI **{bei}**",
                help="Leituras pontuais no vértice mais próximo disponível",
            )


# ---------------------------------------------------------------------------
# Tabela e download
# ---------------------------------------------------------------------------

def _render_table(df: pd.DataFrame, ref_date) -> None:
    display = df.copy()
    display["Vértice (du)"]        = display["vertice_du"]
    display["Prazo"]               = display["vertice_anos"].apply(_anos_label)
    display["IPCA+ (% a.a.)"]      = display["ipca_pct"]
    display["PRE (% a.a.)"]        = display["pre_pct"]
    display["Infl. Implícita (%)"] = display["bei_pct"]

    cols_show = ["Vértice (du)", "Prazo", "IPCA+ (% a.a.)", "PRE (% a.a.)", "Infl. Implícita (%)"]
    st.dataframe(
        display[cols_show],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Vértice (du)":        st.column_config.NumberColumn("Vértice (du)", format="%d"),
            "IPCA+ (% a.a.)":      st.column_config.NumberColumn("IPCA+ (% a.a.)", format="%.4f"),
            "PRE (% a.a.)":        st.column_config.NumberColumn("PRE (% a.a.)", format="%.4f"),
            "Infl. Implícita (%)": st.column_config.NumberColumn("Infl. Implícita (%)", format="%.4f"),
        },
    )

    csv_df = display[cols_show].copy()
    csv = csv_df.to_csv(index=False, sep=";", decimal=",", float_format="%.4f").encode("utf-8-sig")
    st.download_button(
        "⬇️ CSV",
        data=csv,
        file_name=f"ettj_anbima_{ref_date.strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
