"""
Basket Inference Engine — cesta de debêntures de transmissão para Camada 2.

Classifica o universo ANBIMA em:
  A — transmissora confirmada (empresa ∈ fixture área=T)
  B — candidata energia (keywords de transmissão, não confirmada como T)
  C — override manual do usuário
  X — excluída (distribuidora, fora da janela, taxa_real ausente)

Expõe executar_kd_sensibilidade() para calcular Kd nos cenários
base (A), amplo (A+B) e custom (A+C), reutilizando calcular_kd_com_custo_emissao().

Contrato JSON para frontend (endpoint POST /api/kd/sensibilidade):
  Body:     {"overrides": ["TAEE22", "NOVA TRANSMISSORA S.A."], "ano": 2026}
  Response: {cenarios, cesta_detalhes, overrides_resolvidos, fonte, data_ref}
  Cada KdResult serializa via dataclasses.asdict().
"""
from __future__ import annotations

import re
from typing import Optional

import pandas as pd

from wacc_regulatorio.config import JANELA_ANOS
from wacc_regulatorio.params.kd import KdResult, calcular_kd_com_custo_emissao

# Keywords para categoria B: candidatas com nome sugestivo mas não confirmadas como T na fixture
_KEYWORDS_B = ["TRANSMISS", "LINHAS DE ENERGIA", "LT ", " LT-", "ELETRIC"]

# Códigos CETIP: 3-4 letras + 2 dígitos + letra opcional (ex: TAEE22, CMDT12, CTEEP11)
# Strings apenas alfabéticas (ex: "CEMIG", "TAESA") são nomes de empresa, não códigos.
_RE_CODIGO = re.compile(r"^[A-Z]{3,5}\d{2}[A-Z]?$")


def _parece_codigo(s: str) -> bool:
    return bool(_RE_CODIGO.match(s.strip().upper()))


def inferir_cesta_transmissao(
    df_universo: pd.DataFrame,
    df_fixture: pd.DataFrame,
    overrides: list[str] | None = None,
    janela: tuple[int, int] | None = None,
) -> pd.DataFrame:
    """
    Classifica o universo de debêntures ANBIMA para a cesta de Transmissão.

    Args:
        df_universo: Dados ANBIMA ao vivo — mínimo: {codigo, indice, taxa_real}.
                     Opcionalmente: empresa, data_emissao, data_vencimento.
                     Se vazio, usa apenas a fixture.
        df_fixture:  Fixture ANEEL classificada (load_debentures()) — fonte de verdade.
        overrides:   Strings livres — código CETIP ou substring de nome de empresa.
                     Incluídos no cenário 'custom', não alteram 'base' nem 'amplo'.
        janela:      (ano_inicio, ano_fim) para filtro de data_emissao. None = sem filtro.

    Returns:
        DataFrame no formato da fixture com coluna 'categoria' (A/B/C/X) adicional.
        area='T' garantido para categorias A, B e C.
        Inclui toda a fixture + novos códigos do universo ao vivo não presentes na fixture.
    """
    if overrides is None:
        overrides = []
    overrides_up = [o.strip().upper() for o in overrides if o.strip()]

    # Transmissoras confirmadas: conjunto de nomes de empresa da fixture área=T
    transmissoras_nomes: set[str] = set(
        df_fixture.query("area == 'T'")["empresa"].dropna().str.strip().str.upper().unique()
    )

    # Base: fixture completa
    df = df_fixture.copy()

    # Atualiza taxa_real com dados ao vivo para códigos conhecidos
    if not df_universo.empty and "taxa_real" in df_universo.columns:
        live_map: dict[str, float] = (
            df_universo.dropna(subset=["taxa_real"])
            .set_index("codigo")["taxa_real"]
            .to_dict()
        )
        mask_known = df["codigo"].isin(live_map)
        df.loc[mask_known, "taxa_real"] = df.loc[mask_known, "codigo"].map(live_map)

        # Adiciona novos códigos do universo vivo que não estão na fixture
        novos = df_universo[~df_universo["codigo"].isin(set(df["codigo"]))].copy()
        if not novos.empty:
            novos["area"] = "?"  # desconhecida até a classificação abaixo
            df = pd.concat([df, novos], ignore_index=True)

    # Classifica cada linha
    cats: list[str] = []
    for _, row in df.iterrows():
        empresa_up = str(row.get("empresa") or "").strip().upper()
        codigo = str(row.get("codigo") or "").strip().upper()
        data_emissao = row.get("data_emissao")
        taxa_real = row.get("taxa_real")

        # Filtro de janela por ano de emissão
        if janela is not None and pd.notna(data_emissao):
            ano = data_emissao.year if hasattr(data_emissao, "year") else None
            if ano is not None and not (janela[0] <= ano <= janela[1]):
                cats.append("X")
                continue

        if pd.isna(taxa_real) or taxa_real is None:
            cats.append("X")
            continue

        # Categoria A: transmissora confirmada pelo fixture ANEEL (prioridade máxima)
        # A deve ser estável e não mudar com overrides do usuário.
        if empresa_up in transmissoras_nomes:
            cats.append("A")
            continue

        # Categoria C: override manual (só para linhas que não são A)
        # Permite adicionar debêntures de emissoras não-confirmadas como T.
        if _resolve_override(codigo, empresa_up, overrides_up):
            cats.append("C")
            continue

        # Categoria B: candidata por keyword energético (sensibilidade)
        # Exclui área=D explícita (distribuidoras confirmadas na fixture)
        if row.get("area") != "D" and any(kw in empresa_up for kw in _KEYWORDS_B):
            cats.append("B")
            continue

        cats.append("X")

    df = df.copy()
    df["categoria"] = cats

    # Garante area='T' para A, B e C — necessário para calcular_kd_com_custo_emissao()
    df.loc[df["categoria"].isin(["A", "B", "C"]), "area"] = "T"

    return df


def _resolve_override(codigo: str, empresa_up: str, overrides_up: list[str]) -> bool:
    for o in overrides_up:
        if _parece_codigo(o) and o == codigo:
            return True
        if not _parece_codigo(o) and o in empresa_up:
            return True
    return False


def executar_kd_sensibilidade(
    df_cesta: pd.DataFrame,
    custo_emissao_df: pd.DataFrame,
    ano: int,
    cenarios: dict[str, list[str]] | None = None,
    janela_anos: int = JANELA_ANOS,
    T: float = 0.34,
) -> dict[str, KdResult]:
    """
    Calcula Kd para cada cenário de cesta usando calcular_kd_com_custo_emissao().

    Cenários padrão:
      "base":   ["A"]        -> replicação ANEEL mais fiel (só transmissoras confirmadas)
      "amplo":  ["A", "B"]   -> inclui candidatas por keyword (sensibilidade upper-bound)
      "custom": ["A", "C"]   -> base + overrides do usuário

    Args:
        df_cesta:         Output de inferir_cesta_transmissao() com coluna 'categoria'.
        custo_emissao_df: de load_custo_emissao() — custo de emissão amortizado.
        ano:              Último ano da janela (ex: 2026 para projeção WACC 2027).
        cenarios:         Override dos cenários padrão.
        janela_anos:      Tamanho da janela (padrão JANELA_ANOS = 10).
        T:                Alíquota composita IRPJ + CSLL.

    Returns:
        {"base": KdResult, "amplo": KdResult, "custom": KdResult}

    Contrato para serialização JSON:
        import dataclasses
        payload = {k: dataclasses.asdict(v) for k, v in results.items()}
    """
    if cenarios is None:
        cenarios = {
            "base":   ["A"],
            "amplo":  ["A", "B"],
            "custom": ["A", "C"],
        }

    results: dict[str, KdResult] = {}
    for nome, cats in cenarios.items():
        subset = df_cesta[df_cesta["categoria"].isin(cats)].copy()
        if subset.empty or subset["taxa_real"].dropna().empty:
            results[nome] = KdResult(
                kd_debentures=0.0,
                custo_emissao=0.0,
                kd_real_ai=0.0,
                kd_real_di=0.0,
                n_debentures=0,
                T=T,
            )
            continue
        results[nome] = calcular_kd_com_custo_emissao(
            ano=ano,
            debentures_df=subset,
            custo_emissao_df=custo_emissao_df,
            segmento="transmissao",
            janela_anos=janela_anos,
            T=T,
        )

    return results


def resolver_overrides(overrides: list[str], df_universo: pd.DataFrame) -> list[str]:
    """
    Reporta como cada override foi resolvido — para UI e logs de auditoria.

    Args:
        overrides:    Lista de strings fornecidas pelo usuário.
        df_universo:  DataFrame do universo ANBIMA (com coluna 'empresa' quando disponível).

    Returns:
        Lista de mensagens descritivas (uma por override).
    """
    msgs = []
    emp_col = "empresa" in df_universo.columns

    for o in overrides:
        o_up = o.strip().upper()
        if not o_up:
            continue

        if _parece_codigo(o_up):
            found = df_universo[df_universo["codigo"].str.upper() == o_up]
            if found.empty:
                msgs.append(f"{o} -> código não encontrado no universo")
            else:
                emp = found.iloc[0].get("empresa", "empresa desconhecida") if emp_col else "?"
                msgs.append(f"{o} -> encontrado ({emp})")
        else:
            if emp_col:
                found = df_universo[
                    df_universo["empresa"].fillna("").str.upper().str.contains(o_up, na=False)
                ]
                if found.empty:
                    msgs.append(f'"{o}" -> empresa não encontrada no universo')
                else:
                    msgs.append(f'"{o}" -> {len(found)} debênture(s) encontrada(s)')
            else:
                msgs.append(f'"{o}" -> empresa não disponível no universo (sem enriquecimento)')

    return msgs
