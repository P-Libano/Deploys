"""Entry point — Calculadora Macroeconômica com Correção Monetária."""
import streamlit as st

import config
from ui.calculator import render_calculator
from ui.charts import render_comparison_chart, render_evolution_chart, render_focus_history_chart
from ui.sidebar import render_sidebar
from ui.vector import render_vector_tab
from ui.whitepaper import render_whitepaper_tab


def main() -> None:
    st.set_page_config(
        page_title="Calculadora de Correção Monetária",
        page_icon="🏦",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "About": (
                "**Calculadora de Correção Monetária**\n\n"
                "Dados realizados: API SGS do Banco Central do Brasil\n"
                "Projeções: Boletim Focus (BCB)\n\n"
                "Validação: Calculadora do Cidadão BCB"
            )
        },
    )

    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    sidebar_state = render_sidebar()

    tab_calc, tab_vector, tab_ettj, tab_juros, tab_log, tab_docs = st.tabs([
        "📊 Calculadora",
        "📈 Vetor de Correção",
        "📉 ETTJ / Inflação Implícita",
        "📊 Curva de Juros",
        "📋 Log de Atualizações",
        "📖 Documentação",
    ])

    # -------------------------------------------------------------------------
    # Calculadora
    # -------------------------------------------------------------------------
    with tab_calc:
        result = render_calculator(force_refresh=sidebar_state["force_refresh"])

        if result is not None:
            st.subheader("Evolução do valor no período")
            render_evolution_chart(result)

            st.divider()
            st.subheader("Comparativo de índices")
            st.caption(
                f"Variação acumulada de {result.data_origem} a {result.data_destino} "
                "para os quatro índices principais."
            )
            render_comparison_chart(
                result.data_origem, result.data_destino, result.valor_original
            )

            if result.tem_projecao:
                st.divider()
                st.subheader("Histórico das expectativas Focus")
                from datetime import datetime
                anos_disponiveis = list(range(datetime.today().year - 2, datetime.today().year + 3))
                ano_ref = st.selectbox(
                    "Ano de referência",
                    options=anos_disponiveis,
                    index=min(2, len(anos_disponiveis) - 1),
                )
                render_focus_history_chart(result.indice, ano_ref)

    # -------------------------------------------------------------------------
    # Vetor de Correção
    # -------------------------------------------------------------------------
    with tab_vector:
        render_vector_tab(force_refresh=sidebar_state["force_refresh"])

    # -------------------------------------------------------------------------
    # ETTJ / Inflação Implícita
    # -------------------------------------------------------------------------
    with tab_ettj:
        from ui.ettj import render_ettj_tab
        render_ettj_tab()

    # -------------------------------------------------------------------------
    # Curva de Juros
    # -------------------------------------------------------------------------
    with tab_juros:
        from ui.juros import render_juros_tab
        render_juros_tab()

    # -------------------------------------------------------------------------
    # Log
    # -------------------------------------------------------------------------
    with tab_log:
        _render_log_tab()

    # -------------------------------------------------------------------------
    # Documentação / Whitepaper
    # -------------------------------------------------------------------------
    with tab_docs:
        render_whitepaper_tab()


def _render_log_tab() -> None:
    st.subheader("Log de Atualizações dos Dados")
    st.caption(
        "Registra cada vez que os dados foram buscados nas APIs, "
        "destacando quando novos períodos foram incorporados à base."
    )

    try:
        from data.update_log import to_dataframe
        df = to_dataframe(limit=300)
    except Exception as e:
        st.error(f"Erro ao carregar log: {e}")
        return

    if df.empty:
        st.info(
            "Nenhuma atualização registrada ainda. "
            "Faça um cálculo ou clique em 'Atualizar dados agora' na sidebar."
        )
        return

    col_f, col_clear = st.columns([3, 1])
    with col_f:
        series_opts = ["Todas"] + sorted(df["Série"].dropna().unique().tolist())
        serie_filtro = st.selectbox("Filtrar por série", series_opts, key="log_filter_serie")
    with col_clear:
        st.write("")
        st.write("")
        if st.button("🗑️ Limpar log", type="secondary"):
            _clear_log()
            st.rerun()

    df_view = df if serie_filtro == "Todas" else df[df["Série"] == serie_filtro]

    st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Horário":          st.column_config.TextColumn("Horário",          width="medium"),
            "Série":            st.column_config.TextColumn("Série",            width="small"),
            "Evento":           st.column_config.TextColumn("Evento",           width="large"),
            "Último período":   st.column_config.TextColumn("Último período",   width="small"),
            "Novos registros":  st.column_config.NumberColumn("Novos registros",width="small"),
            "Nota":             st.column_config.TextColumn("Nota",             width="large"),
        },
    )

    novos = df_view[df_view["Evento"].str.contains("🆕", na=False)]
    if not novos.empty:
        st.success(f"**{len(novos)} evento(s) com novos dados** detectados.")


def _clear_log() -> None:
    try:
        from data.update_log import FALLBACK_LOG_PATH, LOG_PATH
        for path in (FALLBACK_LOG_PATH, LOG_PATH):
            if path.exists():
                path.write_text("[]", encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    main()
