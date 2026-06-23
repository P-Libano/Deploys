"""Gráficos Plotly para o dashboard de correção monetária."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.deflator import CorrecaoResult, corrigir_valor
import config


def render_evolution_chart(result: CorrecaoResult) -> None:
    """
    Seção 2: gráfico dual-axis.
    Eixo Y esq: valor corrigido acumulado (R$).
    Eixo Y dir: variação mensal (%).
    Área hachurada para o trecho projetado.
    """
    fig = _build_evolution_figure(result)
    st.plotly_chart(fig, use_container_width=True)


def render_comparison_chart(
    data_origem: str,
    data_destino: str,
    valor: float,
) -> None:
    """
    Seção 3: bar chart horizontal comparando variação acumulada dos 4 índices.
    """
    rows = []
    for key, meta in config.SERIES.items():
        try:
            r = corrigir_valor(valor, data_origem, data_destino, key)
            rows.append({
                "Índice": meta["label"],
                "Variação (%)": r.variacao_pct,
                "Valor Corrigido": r.valor_corrigido,
            })
        except Exception:
            pass

    if not rows:
        st.info("Não foi possível calcular a comparação entre índices.")
        return

    df = pd.DataFrame(rows).sort_values("Variação (%)", ascending=True)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df["Índice"],
            x=df["Variação (%)"],
            orientation="h",
            text=[f"{v:+.2f}%" for v in df["Variação (%)"]],
            textposition="outside",
            marker_color=[
                "rgba(0,128,0,0.7)" if v >= 0 else "rgba(200,0,0,0.7)"
                for v in df["Variação (%)"]
            ],
        )
    )
    fig.update_layout(
        title=f"Variação acumulada — {data_origem} → {data_destino}",
        xaxis_title="Variação (%)",
        yaxis_title="",
        height=280,
        margin=dict(l=10, r=60, t=40, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_focus_history_chart(series_key: str, reference_year: int) -> None:
    """
    Seção 4: evolução semanal das expectativas Focus para um ano de referência.
    Mostra como a mediana foi revisada ao longo do tempo.
    """
    from collectors.focus import fetch_focus_annual_history

    with st.spinner(f"Carregando histórico Focus {reference_year}..."):
        try:
            df = fetch_focus_annual_history(series_key, reference_year)
        except Exception as e:
            st.warning(f"Não foi possível carregar histórico Focus: {e}")
            return

    if df.empty:
        st.info(f"Sem dados Focus disponíveis para {config.SERIES[series_key]['label']} {reference_year}.")
        return

    label = config.SERIES[series_key]["label"]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["Data"],
            y=df["Mediana"],
            mode="lines+markers",
            name="Mediana",
            line=dict(color="royalblue", width=2),
            marker=dict(size=4),
        )
    )
    if "Media" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Data"],
                y=df["Media"],
                mode="lines",
                name="Média",
                line=dict(color="orange", width=1.5, dash="dot"),
            )
        )
    fig.update_layout(
        title=f"Evolução das expectativas Focus — {label} {reference_year}",
        xaxis_title="Data da pesquisa",
        yaxis_title="Expectativa (%)",
        height=380,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Builder interno do gráfico de evolução
# ---------------------------------------------------------------------------

def _build_evolution_figure(result: CorrecaoResult) -> go.Figure:
    """Constrói o Figure Plotly dual-axis a partir de um CorrecaoResult."""
    from collections import OrderedDict

    serie_fatores = result.serie_mensal
    if serie_fatores.empty:
        return go.Figure()

    periods = serie_fatores.index
    dates = [p.to_timestamp() for p in periods]
    monthly_pct = [(f - 1) * 100 for f in serie_fatores.values]

    # Valor acumulado mês a mês
    accumulated = []
    cur = result.valor_original
    for f in serie_fatores.values:
        cur = cur * f
        accumulated.append(cur)

    # Determinar ponto de corte realizado/projetado
    last_realized_period = pd.Period(result.ultimo_realizado.replace("/", "-"), freq="M")
    cutoff_idx = None
    for i, p in enumerate(periods):
        if p > last_realized_period:
            cutoff_idx = i
            break

    fig = go.Figure()

    # Linha do valor acumulado — trecho realizado
    if cutoff_idx is None or cutoff_idx >= len(dates):
        # Tudo realizado
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=accumulated,
                mode="lines",
                name="Valor corrigido (realizado)",
                line=dict(color="royalblue", width=2),
                yaxis="y1",
            )
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=dates[:cutoff_idx + 1],
                y=accumulated[:cutoff_idx + 1],
                mode="lines",
                name="Valor corrigido (realizado)",
                line=dict(color="royalblue", width=2),
                yaxis="y1",
            )
        )
        # Trecho projetado: linha laranja tracejada + área sombreada
        fig.add_trace(
            go.Scatter(
                x=dates[cutoff_idx:],
                y=accumulated[cutoff_idx:],
                mode="lines+markers",
                name="Projeção Focus",
                line=dict(color="darkorange", width=2.5, dash="dash"),
                marker=dict(symbol="circle-open", size=5, color="darkorange"),
                fill="tonexty",
                fillcolor="rgba(255,165,0,0.12)",
                yaxis="y1",
            )
        )
        # add_vline com annotation_text causa TypeError em pandas recente (bug Plotly).
        # Usar add_shape + add_annotation separados.
        cutoff_x = dates[cutoff_idx].isoformat()
        fig.add_shape(
            type="line",
            x0=cutoff_x, x1=cutoff_x,
            y0=0, y1=1,
            xref="x", yref="paper",
            line=dict(dash="dot", color="gray", width=1.5),
        )
        fig.add_annotation(
            x=cutoff_x,
            y=1,
            xref="x", yref="paper",
            text=f"Realizado até {result.ultimo_realizado}",
            showarrow=False,
            xanchor="left",
            font=dict(size=11, color="gray"),
            bgcolor="rgba(0,0,0,0)",
        )

    # Barras de variação mensal — realizadas (verde/vermelho) vs projetadas (laranja/âmbar)
    if cutoff_idx is None or cutoff_idx >= len(dates):
        bar_colors = [
            "rgba(0,150,0,0.65)" if v >= 0 else "rgba(200,0,0,0.65)"
            for v in monthly_pct
        ]
    else:
        bar_colors = []
        for i, v in enumerate(monthly_pct):
            if i < cutoff_idx:
                bar_colors.append("rgba(0,150,0,0.65)" if v >= 0 else "rgba(200,0,0,0.65)")
            else:
                bar_colors.append("rgba(255,165,0,0.75)")   # laranja = projetado

    fig.add_trace(
        go.Bar(
            x=dates,
            y=monthly_pct,
            name="Variação mensal (%)",
            marker_color=bar_colors,
            opacity=0.85,
            yaxis="y2",
        )
    )

    fig.update_layout(
        title=f"Evolução do valor — {result.data_origem} → {result.data_destino} ({result.indice})",
        xaxis_title="Período",
        yaxis=dict(title="Valor (R$)", tickprefix="R$ "),
        yaxis2=dict(
            title="Variação mensal (%)",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=420,
        barmode="overlay",
    )
    return fig
