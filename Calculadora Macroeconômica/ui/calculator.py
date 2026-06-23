"""Componente principal da calculadora de correção monetária."""
from datetime import datetime

import streamlit as st

import config
from collectors.updater import NoCacheError
from engine.deflator import (
    CorrecaoResult,
    FutureLimitError,
    PrePlanoRealError,
    corrigir_valor,
)

_INDICES_LABELS = {
    k: v["label"]
    for k, v in config.SERIES.items()
    if k in config.CALCULATOR_INDICES
}
_PLANO_REAL_YEAR = 1994
_PLANO_REAL_MONTH = 7


def render_calculator(force_refresh: bool = False) -> CorrecaoResult | None:
    """
    Renderiza a seção da calculadora (Seção 1).
    Gerencia persistência via st.session_state com prefixo 'calc_'.

    Returns:
        CorrecaoResult se o cálculo foi executado, None caso contrário.
    """
    st.header("Correção Monetária")
    st.caption(
        "Atualiza valores pelo índice de inflação escolhido, "
        "combinando dados realizados com projeções do Boletim Focus para datas futuras."
    )

    today = datetime.today()
    max_future = datetime.today()
    max_future_year = today.year + (config.MAX_FUTURE_MONTHS // 12) + 1

    _init_session_state(today)

    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

    with col1:
        st.subheader("Valor")
        valor = st.number_input(
            "Valor original (R$)",
            min_value=0.01,
            value=st.session_state["calc_valor"],
            step=0.01,
            format="%.2f",
            key="calc_valor_input",
            label_visibility="collapsed",
        )

    with col2:
        st.subheader("Data de origem")
        mes_orig, ano_orig = _render_date_selector(
            "orig",
            default_mes=st.session_state["calc_orig_mes"],
            default_ano=st.session_state["calc_orig_ano"],
            min_year=_PLANO_REAL_YEAR,
            max_year=today.year,
        )

    with col3:
        st.subheader("Data de destino")
        mes_dest, ano_dest = _render_date_selector(
            "dest",
            default_mes=st.session_state["calc_dest_mes"],
            default_ano=st.session_state["calc_dest_ano"],
            min_year=_PLANO_REAL_YEAR,
            max_year=max_future_year,
        )

    with col4:
        st.subheader("Índice")
        indice_label = st.radio(
            "Índice",
            options=list(_INDICES_LABELS.values()),
            index=list(_INDICES_LABELS.values()).index(
                _INDICES_LABELS.get(st.session_state["calc_indice"], "IPCA")
            ),
            key="calc_indice_radio",
            label_visibility="collapsed",
        )
        indice = _label_to_key(indice_label)

    # Selector de fonte de projeção — só relevante para IPCA (BEI é IPCA-linked)
    projecao = "focus"
    if indice == "IPCA":
        st.caption("**Fonte da projeção** (meses futuros)")
        fonte_opcoes = ["Focus BCB", "ETTJ — Inflação Implícita (ANBIMA)"]
        fonte_sel = st.radio(
            "Fonte da projeção",
            options=fonte_opcoes,
            index=st.session_state.get("calc_projecao_idx", 0),
            horizontal=True,
            key="calc_projecao_radio",
            label_visibility="collapsed",
        )
        projecao = "ettj" if "ETTJ" in fonte_sel else "focus"
        st.session_state["calc_projecao_idx"] = fonte_opcoes.index(fonte_sel)

    calcular = st.button(
        "Calcular Correção Monetária",
        type="primary",
        use_container_width=True,
    )

    data_origem = f"{str(mes_orig).zfill(2)}/{ano_orig}"
    data_destino = f"{str(mes_dest).zfill(2)}/{ano_dest}"

    # Invalidar resultado em cache se os inputs mudaram
    cached = st.session_state.get("calc_last_result")
    if cached is not None:
        if (
            cached.data_origem != data_origem
            or cached.data_destino != data_destino
            or cached.indice != indice
            or abs(cached.valor_original - valor) > 0.001
        ):
            del st.session_state["calc_last_result"]

    result = None
    if calcular:
        st.session_state["calc_valor"] = valor
        st.session_state["calc_indice"] = indice

        with st.spinner("Buscando dados e calculando..."):
            result = _run_calculation(valor, data_origem, data_destino, indice, force_refresh, projecao)

        if result is not None:
            st.session_state["calc_last_result"] = result
        else:
            # Garantir que resultado antigo inválido não apareça
            st.session_state.pop("calc_last_result", None)

    # Exibir último resultado se existir
    if result is None and "calc_last_result" in st.session_state:
        result = st.session_state["calc_last_result"]

    if result is not None:
        _render_result_cards(result)

    return result


def _run_calculation(
    valor: float,
    data_origem: str,
    data_destino: str,
    indice: str,
    force_refresh: bool,
    projecao: str = "focus",
) -> CorrecaoResult | None:
    """Executa corrigir_valor() com tratamento de erros tipados."""
    try:
        return corrigir_valor(
            valor, data_origem, data_destino, indice,
            force_refresh=force_refresh, projecao=projecao,
        )
    except PrePlanoRealError as e:
        st.error(f"**Data inválida:** {e}")
    except FutureLimitError as e:
        st.error(f"**Limite de projeção excedido:** {e}")
    except NoCacheError as e:
        st.error(
            f"**Sem dados disponíveis:** {e}\n\n"
            "Verifique sua conexão com a internet e tente novamente."
        )
    except KeyError as e:
        st.error(f"**Índice inválido:** {e}")
    except Exception as e:
        st.error(f"**Erro inesperado:** {e}")
    return None


def _render_result_cards(result: CorrecaoResult) -> None:
    """Exibe os 4 cards de resultado e o badge de proveniência."""
    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Valor Corrigido",
            value=_fmt_brl(result.valor_corrigido),
            delta=f"{result.variacao_pct:+.2f}%",
            delta_color="normal" if result.variacao_pct >= 0 else "inverse",
        )
    with col2:
        st.metric(
            label="Fator Acumulado",
            value=f"{result.fator_acumulado:.4f}×",
        )
    with col3:
        st.metric(
            label="Variação Total",
            value=f"{result.variacao_pct:+.2f}%",
        )
    with col4:
        st.metric(
            label="Período",
            value=f"{result.n_meses} {'mês' if result.n_meses == 1 else 'meses'}",
        )

    # Badge de proveniência dos dados
    if result.data_warning:
        st.warning(f"⚠️ {result.data_warning}", icon="⚠️")
    elif result.tem_projecao:
        fonte = result.fonte_projecao or "Focus"
        ultimo = result.ultimo_realizado
        if "ETTJ BEI" in fonte:
            st.info(
                f"🔵 **Projeção via Inflação Implícita ANBIMA (ETTJ BEI)** — "
                f"dados realizados até {ultimo}. Meses futuros usam o break-even PRE vs. IPCA+ "
                f"da curva zero-coupon ANBIMA como premissa de inflação mensal.",
                icon="📉",
            )
        elif "extrapolação" in fonte:
            st.warning(
                f"🟠 **Inclui extrapolação além do horizonte Focus** — "
                f"dados realizados até {ultimo}. Meses dentro do Boletim Focus usam expectativas de mercado; "
                f"meses além do horizonte replicam a última expectativa anual Focus disponível como premissa.",
                icon="📊",
            )
        else:
            st.info(
                f"🟡 **Inclui projeção {fonte}** — "
                f"dados realizados até {ultimo}; meses seguintes são estimativas do Boletim Focus.",
                icon="📊",
            )
    else:
        st.success("🟢 **Dados realizados** — período inteiramente coberto por dados oficiais.", icon="✅")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_date_selector(
    prefix: str,
    default_mes: int,
    default_ano: int,
    min_year: int,
    max_year: int,
) -> tuple[int, int]:
    """Renderiza dois selectboxes (mês, ano) para seleção de data."""
    col_m, col_a = st.columns(2)
    meses = {
        1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
    }
    with col_m:
        mes = st.selectbox(
            "Mês",
            options=list(meses.keys()),
            format_func=lambda m: meses[m],
            index=default_mes - 1,
            key=f"calc_{prefix}_mes",
            label_visibility="collapsed",
        )
    with col_a:
        anos = list(range(min_year, max_year + 1))
        ano_idx = anos.index(default_ano) if default_ano in anos else len(anos) - 1
        ano = st.selectbox(
            "Ano",
            options=anos,
            index=ano_idx,
            key=f"calc_{prefix}_ano",
            label_visibility="collapsed",
        )
    return mes, ano


def _init_session_state(today: datetime) -> None:
    """Inicializa defaults do session_state na primeira execução."""
    defaults = {
        "calc_valor": 1000.0,
        "calc_orig_mes": _PLANO_REAL_MONTH,
        "calc_orig_ano": _PLANO_REAL_YEAR,
        "calc_dest_mes": today.month,
        "calc_dest_ano": today.year,
        "calc_indice": "IPCA",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _label_to_key(label: str) -> str:
    """Converte label de exibição ("IGP-M") de volta para chave interna ("IGPM")."""
    for key, lbl in _INDICES_LABELS.items():
        if lbl == label:
            return key
    return "IPCA"


def _fmt_brl(value: float) -> str:
    """Formata float como moeda brasileira: R$ 1.234,56"""
    try:
        inteiro, decimal = f"{abs(value):,.2f}".split(".")
        inteiro = inteiro.replace(",", ".")
        sinal = "-" if value < 0 else ""
        return f"{sinal}R$ {inteiro},{decimal}"
    except Exception:
        return f"R$ {value:.2f}"
