"""Aba de extração do vetor de fator de correção para uso em modelos financeiros."""
import io
from datetime import datetime

import pandas as pd
import streamlit as st

import config
from engine.deflator import PrePlanoRealError, FutureLimitError
from engine.vector import build_inflation_vector

_INDICES_LABELS = {k: v["label"] for k, v in config.SERIES.items()}


def render_vector_tab(force_refresh: bool = False) -> None:
    """Renderiza a aba completa de extração do vetor de inflação."""
    st.header("Vetor de Correção")
    st.caption(
        "Gera uma série mensal de fatores de correção entre duas datas, "
        "com base em uma data-referência (fator = 1,0000). "
        "Use para deflacionar ou inflacionar fluxos de caixa em bloco."
    )

    today = datetime.today()
    max_year = today.year + (config.MAX_FUTURE_MONTHS // 12) + 1

    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

    with col1:
        st.subheader("Data base")
        st.caption("Fator = 1,0000 nesta data")
        mes_base, ano_base = _date_selector("vec_base", today.month, today.year, max_year)

    with col2:
        st.subheader("Data início")
        mes_ini, ano_ini = _date_selector("vec_ini", 1, 2015, max_year)

    with col3:
        st.subheader("Data fim")
        mes_fim, ano_fim = _date_selector("vec_fim", today.month, today.year + 2, max_year)

    with col4:
        st.subheader("Índice")
        indice_label = st.radio(
            "Índice",
            options=list(_INDICES_LABELS.values()),
            key="vec_indice",
            label_visibility="collapsed",
        )
        indice = _label_to_key(indice_label)

    projecao = "focus"
    if indice == "IPCA":
        st.caption("**Fonte da projeção** (meses futuros)")
        fonte_opcoes = ["Focus BCB", "ETTJ — Inflação Implícita (ANBIMA)"]
        fonte_sel = st.radio(
            "Fonte da projeção",
            options=fonte_opcoes,
            index=st.session_state.get("vec_projecao_idx", 0),
            horizontal=True,
            key="vec_projecao_radio",
            label_visibility="collapsed",
        )
        projecao = "ettj" if "ETTJ" in fonte_sel else "focus"
        st.session_state["vec_projecao_idx"] = fonte_opcoes.index(fonte_sel)

    gerar = st.button("Gerar Vetor", type="primary", use_container_width=True)

    if gerar:
        base_str  = f"{str(mes_base).zfill(2)}/{ano_base}"
        start_str = f"{str(mes_ini).zfill(2)}/{ano_ini}"
        end_str   = f"{str(mes_fim).zfill(2)}/{ano_fim}"

        with st.spinner("Montando vetor..."):
            try:
                vec = build_inflation_vector(base_str, start_str, end_str, indice, force_refresh, projecao)
                st.session_state["vec_last"] = vec
            except (PrePlanoRealError, FutureLimitError, KeyError, ValueError) as e:
                st.error(str(e))
                st.session_state.pop("vec_last", None)
            except Exception as e:
                st.error(f"Erro inesperado: {e}")
                st.session_state.pop("vec_last", None)

    vec = st.session_state.get("vec_last")
    if vec is None:
        return

    # -------------------------------------------------------------------------
    # Resultado
    # -------------------------------------------------------------------------
    df = vec.data
    n_real = len(df[df["Tipo"] == "Realizado"])
    n_focus = len(df[df["Tipo"] == "Projeção Focus"])
    n_ettj  = len(df[df["Tipo"] == "Projeção ETTJ BEI"])
    n_proj  = n_focus + n_ettj

    col_info, col_dl = st.columns([3, 1])
    with col_info:
        proj_label = ""
        if n_ettj:
            proj_label = f" + {n_ettj} meses projetados (ETTJ BEI)"
        elif n_focus:
            proj_label = f" + {n_focus} meses projetados (Focus Anual)"
        st.markdown(
            f"**{vec.indice}** · base {vec.base_date} · "
            f"{n_real} meses realizados{proj_label}"
        )

    if n_ettj:
        st.info(
            "**Granularidade ETTJ**: o menor vértice BEI disponível é **6 meses (126 du)**. "
            "Todos os meses dentro da mesma janela de 6 meses recebem a mesma taxa mensal — "
            "não há dados de mercado com resolução inferior a esse prazo. "
            "A cada 6 meses projetados a taxa dá um salto para a taxa forward do próximo intervalo da curva.",
            icon="ℹ️",
        )
    with col_dl:
        _download_buttons(df, vec)

    # Tabela colorida: linhas de projeção em laranja claro
    st.dataframe(
        df.style.apply(_highlight_projection, axis=1),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Período":           st.column_config.TextColumn("Período", width="small"),
            "Taxa Mensal (%)":   st.column_config.NumberColumn("Taxa Mensal (%)", format="%.4f"),
            "Fator Mensal":      st.column_config.NumberColumn("Fator Mensal",    format="%.6f"),
            "Fator Acumulado":   st.column_config.NumberColumn("Fator Acumulado", format="%.6f"),
            "Variação Acum. (%)": st.column_config.NumberColumn("Var. Acum. (%)", format="%.4f"),
            "Tipo":              st.column_config.TextColumn("Tipo", width="medium"),
        },
    )

    _render_vector_explainer(vec.base_date, vec.indice)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_selector(prefix: str, default_mes: int, default_ano: int, max_year: int) -> tuple[int, int]:
    meses = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",
             7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}
    col_m, col_a = st.columns(2)
    with col_m:
        mes = st.selectbox("Mês", list(meses.keys()),
                           format_func=lambda m: meses[m],
                           index=default_mes - 1,
                           key=f"{prefix}_mes",
                           label_visibility="collapsed")
    with col_a:
        anos = list(range(1940, max_year + 1))
        idx = anos.index(default_ano) if default_ano in anos else len(anos) - 1
        ano = st.selectbox("Ano", anos, index=idx,
                           key=f"{prefix}_ano",
                           label_visibility="collapsed")
    return mes, ano


def _download_buttons(df: pd.DataFrame, vec) -> None:
    """Botão de download CSV e Excel."""
    # CSV
    csv = df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(
        "⬇️ CSV",
        data=csv,
        file_name=f"vetor_{vec.indice}_{vec.base_date.replace('/','_')}.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _highlight_projection(row) -> list[str]:
    tipo = row.get("Tipo", "")
    if tipo == "Projeção Focus":
        return ["background-color: rgba(255,165,0,0.15)"] * len(row)
    if tipo == "Projeção ETTJ BEI":
        return ["background-color: rgba(52,152,219,0.13)"] * len(row)
    return [""] * len(row)


def _label_to_key(label: str) -> str:
    for key, lbl in _INDICES_LABELS.items():
        if lbl == label:
            return key
    return "IPCA"


def _render_vector_explainer(base_date: str, indice: str) -> None:
    """Mini-guia de como usar o vetor em um modelo financeiro."""
    with st.expander("Como usar este vetor em um modelo financeiro", expanded=False):
        st.markdown(f"""
**Premissa:** o fator acumulado na data base ({base_date}) é **1,0000**.

- Fator > 1,0 → o preço subiu em relação à base
- Fator < 1,0 → o preço caiu em relação à base (deflação)

---

**Para inflacionar um fluxo histórico até a data base** *(trazer ao "dinheiro de hoje")*:

```
Valor_base = Valor_período ÷ Fator_Acumulado_período
```

Exemplo: CAPEX de R\$ 500.000 em Mar/2018, base = hoje
→ Valor_hoje = 500.000 ÷ 0,6234 = **R\$ 802.000** *(poder de compra equivalente)*

---

**Para inflacionar um fluxo atual para datas futuras** *(projetar OPEX/CAPEX)*:

```
Valor_futuro = Valor_base × Fator_Acumulado_futuro
```

Exemplo: custo anual de R\$ 100.000 (base hoje), projetar para 2027
→ Valor_2027 = 100.000 × 1,0830 = **R\$ 108.300**

---

**Em planilha / modelo DCF:** crie uma coluna com os fatores, multiplique cada linha de fluxo pelo fator do período correspondente. Para deflacionar, divida. Para inflacionar, multiplique.
""")
