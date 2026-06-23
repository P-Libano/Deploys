"""Motor principal de correção monetária."""
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

import config
from collectors.updater import NoCacheError, get_focus_projections, get_realized_series
from engine.index_builder import _parse_period, get_factor_between
from engine.projector import build_ettj_projection, build_projected_series


class PrePlanoRealError(ValueError):
    """Levantada quando a data de origem é anterior ao início da série."""
    pass


class FutureLimitError(ValueError):
    """Levantada quando a data de destino ultrapassa MAX_FUTURE_MONTHS."""
    pass


@dataclass
class CorrecaoResult:
    valor_original: float
    valor_corrigido: float
    fator_acumulado: float
    variacao_pct: float
    n_meses: int
    data_origem: str        # "MM/YYYY"
    data_destino: str       # "MM/YYYY"
    indice: str
    tem_projecao: bool
    ultimo_realizado: str   # "MM/YYYY" — último mês com dado efetivo
    fonte_projecao: str | None
    # Série mensal de fatores (ex: 1.0042) usada pelos gráficos
    serie_mensal: pd.Series = field(default_factory=pd.Series)
    data_warning: str | None = None


def corrigir_valor(
    valor: float,
    data_origem: str,
    data_destino: str,
    indice: str = "IPCA",
    force_refresh: bool = False,
    projecao: str = "focus",
) -> CorrecaoResult:
    """
    Calcula a correção monetária de `valor` entre dois meses.

    Args:
        valor: valor em R$ a ser corrigido
        data_origem: "MM/YYYY"
        data_destino: "MM/YYYY" — pode ser futuro (usa Focus)
        indice: "IPCA" | "IGPM" | "IPCA15" | "INPC"
        force_refresh: força atualização do cache antes de calcular

    Returns:
        CorrecaoResult completo

    Raises:
        KeyError: índice inválido
        PrePlanoRealError: data_origem antes do início da série
        FutureLimitError: data_destino além do limite futuro
        NoCacheError: API inacessível sem cache local
    """
    if indice not in config.SERIES:
        raise KeyError(f"Índice '{indice}' inválido. Opções: {list(config.SERIES)}")

    periodo_origem = _parse_period(data_origem)
    periodo_destino = _parse_period(data_destino)

    # Validação: data mínima da série
    serie_start_str = config.SERIES[indice]["start"]
    serie_start = _parse_period(serie_start_str)
    if periodo_origem < serie_start:
        raise PrePlanoRealError(
            f"A data de origem ({data_origem}) é anterior ao início da série "
            f"{indice} ({serie_start_str}). "
            "A correção monetária só está disponível a partir dessa data."
        )
    if periodo_destino < serie_start:
        raise PrePlanoRealError(
            f"A data de destino ({data_destino}) é anterior ao início da série {indice} ({serie_start_str})."
        )

    # Validação: limite futuro
    hoje = pd.Period(datetime.today(), freq="M")
    max_futuro = hoje + config.MAX_FUTURE_MONTHS
    if periodo_destino > max_futuro:
        raise FutureLimitError(
            f"A data de destino ({data_destino}) ultrapassa o limite máximo de "
            f"{config.MAX_FUTURE_MONTHS // 12} anos à frente ({max_futuro.strftime('%m/%Y')}). "
            "Reduza a data de destino para continuar."
        )

    # Caso trivial
    if periodo_origem == periodo_destino:
        return CorrecaoResult(
            valor_original=valor,
            valor_corrigido=valor,
            fator_acumulado=1.0,
            variacao_pct=0.0,
            n_meses=0,
            data_origem=data_origem,
            data_destino=data_destino,
            indice=indice,
            tem_projecao=False,
            ultimo_realizado=data_origem,
            fonte_projecao=None,
        )

    # Buscar série realizada
    realized, from_cache, warning = get_realized_series(indice, force_refresh=force_refresh)

    # Buscar projeções Focus se necessário
    last_realized = realized.index.max()
    tem_projecao = False
    fonte_projecao = None
    proj_warning = None

    destino_efetivo = max(periodo_origem, periodo_destino)
    if destino_efetivo > last_realized:
        if projecao == "ettj" and indice == "IPCA":
            from collectors.anbima_ettj import fetch_ettj
            ettj_df, _ = fetch_ettj(force_refresh=force_refresh)
            unified, last_realized, fonte_projecao = build_ettj_projection(
                realized, ettj_df, destino_efetivo
            )
        else:
            focus_monthly, focus_annual = get_focus_projections(indice, force_refresh=force_refresh)
            unified, last_realized, fonte_projecao = build_projected_series(
                realized, focus_monthly, focus_annual, destino_efetivo
            )
        tem_projecao = fonte_projecao != "realized only"

        # Índice sem projeção Focus: cap ao último realizado
        if not tem_projecao and periodo_destino > last_realized:
            proj_warning = (
                f"Sem projeção disponível para {indice}. "
                f"Cálculo limitado ao último dado realizado ({last_realized.strftime('%m/%Y')})."
            )
            periodo_destino = last_realized
            data_destino = last_realized.strftime("%m/%Y")
    else:
        unified = realized
        fonte_projecao = None

    # Calcular fator e valor corrigido
    fator = get_factor_between(unified, data_origem, data_destino)
    valor_corrigido = valor * fator
    variacao_pct = (fator - 1) * 100.0

    # Série mensal de fatores (para os gráficos)
    p_start, p_end = (
        (periodo_origem, periodo_destino)
        if periodo_origem <= periodo_destino
        else (periodo_destino, periodo_origem)
    )
    mask = (unified.index >= p_start) & (unified.index <= p_end)
    serie_pct = unified.loc[mask]
    serie_fatores = (1 + serie_pct / 100).rename("fator")

    n_meses = abs(periodo_destino.ordinal - periodo_origem.ordinal)

    return CorrecaoResult(
        valor_original=valor,
        valor_corrigido=valor_corrigido,
        fator_acumulado=fator,
        variacao_pct=variacao_pct,
        n_meses=n_meses,
        data_origem=data_origem,
        data_destino=data_destino,
        indice=indice,
        tem_projecao=tem_projecao,
        ultimo_realizado=last_realized.strftime("%m/%Y"),
        fonte_projecao=fonte_projecao if tem_projecao else None,
        serie_mensal=serie_fatores,
        data_warning=warning or proj_warning,
    )
