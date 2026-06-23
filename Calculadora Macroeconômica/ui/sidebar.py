"""Sidebar com controles de cache e atualização."""
import streamlit as st
from collectors.updater import force_update_all, get_cache_status


def render_sidebar() -> dict:
    """
    Renderiza o conteúdo do st.sidebar.

    Returns:
        dict com chaves:
        - force_refresh (bool): usuário clicou em "Atualizar agora"
    """
    with st.sidebar:
        st.title("⚙️ Configurações")

        st.divider()
        st.subheader("Dados")

        force_refresh = False
        if st.button("🔄 Atualizar dados agora", use_container_width=True):
            with st.spinner("Atualizando séries e Focus..."):
                warnings = force_update_all()
                warnings_with_msg = {k: v for k, v in warnings.items() if v}
                if warnings_with_msg:
                    for key, msg in warnings_with_msg.items():
                        st.warning(f"{key}: {msg}")
                else:
                    st.success("Dados atualizados com sucesso.")
            force_refresh = True

        _render_cache_status()

        st.divider()
        st.caption(
            "Fontes: API SGS/BCB · Boletim Focus/BCB · ANBIMA ETTJ\n\n"
            "Validação: [Calculadora do Cidadão BCB](https://www3.bcb.gov.br/CALCIDADAO/publico/corrigirPorIndice.do)"
        )

    return {"force_refresh": force_refresh}


def _render_cache_status() -> None:
    """Exibe timestamps da última atualização do cache."""
    try:
        status = get_cache_status()
    except Exception:
        return

    with st.expander("Status do cache", expanded=False):
        for key, info in status.items():
            realized = info.get("realized_updated_at") or "—"
            focus    = info.get("focus_updated_at")

            if key == "ETTJ":
                st.text("ETTJ ANBIMA")
                st.caption(f"Último arquivo: {realized}")
            else:
                st.text(f"{key}")
                focus_str = focus or "—"
                st.caption(f"Realizado: {realized}  |  Focus: {focus_str}")
