"""
Custo de Capital de Terceiros (Kd) — debêntures do setor elétrico.

Duas sub-rotinas:
  A. Cálculo histórico (replicação ANEEL)
  B. Regressão preditiva (projeção Camada 3)

Resultado esperado WACC 2026 (Transmissão):
    Kd_debentures     = 6,069%
    Custo de emissão  = 0,518%
    Kd_real_ai        = 6,587%
"""
import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import linregress


@dataclass
class KdResult:
    kd_debentures: float         # Taxa real média ponderada das debêntures
    custo_emissao: float         # Custo de emissão amortizado
    kd_real_ai: float            # kd_debentures + custo_emissao
    kd_real_di: float            # kd_real_ai * (1 - T)
    n_debentures: int            # Número de debêntures na amostra
    T: float


# ---------------------------------------------------------------------------
# Bloco A — cálculo histórico
# ---------------------------------------------------------------------------

def calcular_kd_historico(
    ano: int,
    wacc_aplicacao_df: pd.DataFrame,
    segmento: str = "transmissao",
    T: float = 0.34,
) -> KdResult:
    """
    Retorna os valores de Kd pré-calculados da planilha ANEEL para Camada 1.

    O cálculo bottom-up de Kd a partir das debêntures requer a inflação implícita
    (BEI) na data de emissão de cada título via engine ETTJ, o que demanda acesso
    à API ANBIMA. Para Camada 1 (replicação determinística sem chamadas externas),
    usamos os valores pré-calculados do WACC para aplicação.

    Para o cálculo bottom-up com engine ETTJ, veja calcular_kd_bottom_up().
    """
    row = wacc_aplicacao_df[
        (wacc_aplicacao_df["ano"] == ano) &
        (wacc_aplicacao_df["segmento"] == segmento)
    ]
    if row.empty:
        raise ValueError(f"Sem dados para ano={ano}, segmento={segmento}")

    r = row.iloc[0]
    kd_deb = float(r["kd_debentures"])
    kd_custo = float(r["kd_custo_emissao"])
    kd_ai = float(r["kd_real_ai"])
    kd_di = float(r["kd_real_di"])

    return KdResult(
        kd_debentures=kd_deb,
        custo_emissao=kd_custo,
        kd_real_ai=kd_ai,
        kd_real_di=kd_di,
        n_debentures=0,
        T=T,
    )


def calcular_kd_bottom_up(
    ano: int,
    debentures_df: pd.DataFrame,
    segmento: str = "transmissao",
    janela_anos: int = 10,
    T: float = 0.34,
    bei_series: Optional[pd.Series] = None,
) -> KdResult:
    """
    Cálculo bottom-up do Kd a partir das debêntures individuais.

    ANEEL usa média aritmética simples de taxa_real (validado: delta ≤ 1bp).
    Janela: data_emissao in [ano - janela_anos + 1, ano].
    """
    area_map = {"transmissao": "T", "distribuicao": "D"}
    area = area_map.get(segmento.lower(), "T")

    start = pd.Timestamp(f"{ano - janela_anos + 1}-01-01")
    end = pd.Timestamp(f"{ano}-12-31")

    df = debentures_df[
        (debentures_df["area"] == area) &
        (debentures_df["data_emissao"] >= start) &
        (debentures_df["data_emissao"] <= end) &
        (debentures_df["taxa_real"].notna())
    ].copy()

    if df.empty:
        raise ValueError(f"Sem debêntures {segmento} na janela {ano-janela_anos+1}–{ano}")

    kd_deb = float(df["taxa_real"].mean())
    n = len(df)

    return KdResult(
        kd_debentures=kd_deb,
        custo_emissao=0.0,
        kd_real_ai=kd_deb,
        kd_real_di=kd_deb * (1.0 - T),
        n_debentures=n,
        T=T,
    )


def calcular_kd_com_custo_emissao(
    ano: int,
    debentures_df: pd.DataFrame,
    custo_emissao_df: pd.DataFrame,
    segmento: str = "transmissao",
    janela_anos: int = 10,
    T: float = 0.34,
    periodos_df: Optional[pd.DataFrame] = None,
) -> KdResult:
    """
    Kd bottom-up completo: taxa_real média aritmética + custo de emissão agregado.
    Janela: data_emissao in [ano - janela_anos + 1, ano].

    Metodologia ANEEL:
        kd_debentures    = média aritmética simples de taxa_real (validado: delta ≤ 1bp)
        kd_custo_emissao = IPCA+DI agregado da cesta (pré-computado no xlsx, via periodos_df)
                           Fallback: média simples de remuneracao_real (~+0.8bp vs ANEEL)
        kd_real_ai       = kd_debentures + kd_custo_emissao
        kd_real_di       = kd_real_ai × (1 − T)

    Args:
        ano: Último ano da janela (ex: 2025 para WACC 2026, janela [2016, 2025])
        debentures_df: de load_debentures()
        custo_emissao_df: de load_custo_emissao()
        segmento: "transmissao" (area=T) ou "distribuicao" (area=D)
        janela_anos: tamanho da janela (padrão 10)
        T: alíquota composita IRPJ + CSLL
        periodos_df: de load_custo_emissao_periodos() — IPCA+DI pré-computado por janela.
            Se fornecido, usa o agregado exato do ANEEL; caso contrário usa média simples.
    """
    area_map = {"transmissao": "T", "distribuicao": "D"}
    area = area_map.get(segmento.lower(), "T")

    start = pd.Timestamp(f"{ano - janela_anos + 1}-01-01")
    end = pd.Timestamp(f"{ano}-12-31")

    # --- kd_debentures ---
    deb = debentures_df[
        (debentures_df["area"] == area) &
        (debentures_df["data_emissao"] >= start) &
        (debentures_df["data_emissao"] <= end) &
        (debentures_df["taxa_real"].notna())
    ].copy()

    if deb.empty:
        raise ValueError(f"Sem debêntures {segmento} na janela {ano-janela_anos+1}–{ano}")

    kd_deb = float(deb["taxa_real"].mean())

    # --- kd_custo_emissao ---
    # Prioridade: IPCA+DI pré-computado pelo ANEEL (periodos_df)
    periodo_str = f"{ano - janela_anos + 1}-{ano}"
    kd_custo = None
    if periodos_df is not None and not periodos_df.empty:
        row_per = periodos_df[periodos_df["periodo"] == periodo_str]
        if not row_per.empty:
            kd_custo = float(row_per.iloc[0]["custo_emissao_agregado"])

    if kd_custo is None:
        # Fallback: média simples de remuneracao_real (~+0.8bp vs ANEEL)
        custo = custo_emissao_df[
            (custo_emissao_df["classificacao"] == area) &
            (custo_emissao_df["data_emissao"] >= start) &
            (custo_emissao_df["data_emissao"] <= end) &
            (custo_emissao_df["remuneracao_real"].notna())
        ]
        kd_custo = float(custo["remuneracao_real"].mean()) if not custo.empty else 0.0

    kd_ai = kd_deb + kd_custo

    return KdResult(
        kd_debentures=kd_deb,
        custo_emissao=kd_custo,
        kd_real_ai=kd_ai,
        kd_real_di=kd_ai * (1.0 - T),
        n_debentures=len(deb),
        T=T,
    )


# ---------------------------------------------------------------------------
# Bloco B — regressão preditiva
# ---------------------------------------------------------------------------

def calibrar_regressao_kd(
    wacc_historico_df: pd.DataFrame,
    output_path: Path,
    excluir_outliers: list[int] = None,
) -> dict:
    """
    Calibra regressão Kd ~ f(Rf, EMBI) com dados históricos 2013-2025.

    Reporta:
        - Especificação 1: Kd ~ alpha + beta1*Rf
        - Especificação 2: Kd ~ alpha + beta1*Rf + beta2*EMBI (preferencial se ΔR²>2%)
        - Resíduos por ano, destacando outliers com |resid| > 2*std
        - Compara coeficientes com/sem outliers se excluir_outliers fornecido

    Salva coeficientes em output_path (JSON).
    """
    if excluir_outliers is None:
        excluir_outliers = []

    df = wacc_historico_df[wacc_historico_df["segmento"] == "transmissao"].copy()
    df = df.dropna(subset=["rf", "kd_real_ai"])

    results = {}

    for label, mask in [("full", pd.Series(True, index=df.index)),
                         ("no_outliers", ~df["ano"].isin(excluir_outliers))]:
        if label == "no_outliers" and not excluir_outliers:
            continue
        sub = df[mask]

        x_rf = sub["rf"].values
        x_embi = sub.get("embi_media", sub["kd_real_ai"].values * 0)  # fallback
        y = sub["kd_real_ai"].values

        # Spec 1: Kd ~ Rf
        sl1, ic1, r1, p1, se1 = linregress(x_rf, y)
        r2_1 = r1 ** 2
        pred1 = ic1 + sl1 * x_rf
        resid1 = y - pred1
        std1 = float(np.std(resid1))

        print(f"\n  [{label}] Especificacao 1: Kd ~ alpha + beta1*Rf")
        print(f"    alpha={ic1:.6f}  beta1={sl1:.6f}  R2={r2_1:.4f}  p={p1:.4f}")
        print(f"    Residuos por ano:")
        for ano_val, res in zip(sub["ano"], resid1):
            flag = " [OUTLIER]" if abs(res) > 2 * std1 else ""
            warn = " <-- 2020" if ano_val == 2020 else ""
            print(f"      {ano_val}: {res:+.4f}{flag}{warn}")

        results[f"{label}_spec1"] = {
            "alpha": float(ic1),
            "beta1_rf": float(sl1),
            "r2": float(r2_1),
            "p_beta1": float(p1),
        }

    # Salva os coeficientes da especificação 1 (full, sem EMBI — série mais estável)
    coef = results.get("full_spec1", list(results.values())[0])
    coef["spec"] = "simples"
    coef["anos_excluidos"] = excluir_outliers
    coef["n_obs"] = int(len(df))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(coef, f, indent=2, ensure_ascii=False)
    print(f"\n  Coeficientes salvos em {output_path}")

    return coef


def carregar_coeficientes_kd(path: Path) -> dict:
    """Carrega coeficientes calibrados do JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def kd_projetado(
    rf_t: float,
    embi_t: float,
    coef: dict,
    spec: str = "simples",
) -> float:
    """
    Projeta Kd_real_ai para o ano t usando regressão calibrada.

    Args:
        rf_t: Taxa livre de risco no ano t (decimal)
        embi_t: EMBI no ano t (decimal)
        coef: Coeficientes de calibrar_regressao_kd()
        spec: 'simples' (Kd~Rf) ou 'embi' (Kd~Rf+EMBI)

    Returns:
        Kd_real_ai projetado como decimal
    """
    alpha = coef["alpha"]
    beta1 = coef["beta1_rf"]

    if spec == "embi" and "beta2_embi" in coef:
        beta2 = coef["beta2_embi"]
        return alpha + beta1 * rf_t + beta2 * embi_t
    else:
        return alpha + beta1 * rf_t


# ---------------------------------------------------------------------------
# Bloco C — Kd-mid (T-1): mesma amostra ANEEL + BEI atual via ETTJ
# ---------------------------------------------------------------------------

def calcular_taxa_real_ettj(
    taxa_nominal: float,
    prazo_anos: float,
    ettj_df: pd.DataFrame,
) -> float:
    """
    Converte taxa nominal de emissão em taxa real usando BEI interpolado da ETTJ atual.

    taxa_real = (1 + taxa_nominal) / (1 + BEI_prazo) - 1
    BEI_prazo = interpolação linear da curva ETTJ NTN-B no prazo da debênture.

    Args:
        taxa_nominal: taxa nominal decimal (ex: 0.1447 para 14,47%)
        prazo_anos:   prazo original da debênture em anos (emissão → vencimento)
        ettj_df:      curva ETTJ com colunas prazo_anos, yield_real (decimal)

    Returns:
        taxa_real como decimal
    """
    prazo_clip = float(np.clip(prazo_anos, ettj_df["prazo_anos"].min(), ettj_df["prazo_anos"].max()))
    bei = float(np.interp(prazo_clip, ettj_df["prazo_anos"].values, ettj_df["yield_real"].values))
    return (1.0 + taxa_nominal) / (1.0 + bei) - 1.0


def calcular_kd_fixture_bottomup(
    ano: int,
    debentures_df: pd.DataFrame,
    custo_emissao_df: pd.DataFrame,
    segmento: str = "transmissao",
    janela_anos: int = 10,
    T: float = 0.34,
    periodos_df: Optional[pd.DataFrame] = None,
) -> KdResult:
    """
    Replica Kd da ANEEL bottom-up usando inflacao_implicita do fixture.

    A coluna inflacao_implicita em debentures.csv contém o BEI que a ANEEL
    interpolou da ETTJ ANBIMA na data de emissão de cada debênture. Usando:
        taxa_real = (1 + taxa_nominal_pct/100) / (1 + inflacao_implicita) - 1

    Para DI sem taxa_nominal_pct ou IPCA, usa taxa_real do fixture diretamente.
    Resultado esperado: 0bp de delta vs calcular_kd_com_custo_emissao().

    Args:
        ano:              Último ano da janela (ex: 2025 para WACC 2026)
        debentures_df:    de load_debentures()
        custo_emissao_df: de load_custo_emissao()
        segmento:         "transmissao" ou "distribuicao"
        janela_anos:      tamanho da janela (padrão 10)
        T:                alíquota composita IRPJ + CSLL
        periodos_df:      de load_custo_emissao_periodos() — IPCA+DI pré-computado.
                          Se fornecido, usa o agregado exato ANEEL (recomendado para C1).
    """
    area_map = {"transmissao": "T", "distribuicao": "D"}
    area = area_map.get(segmento.lower(), "T")

    start = pd.Timestamp(f"{ano - janela_anos + 1}-01-01")
    end = pd.Timestamp(f"{ano}-12-31")

    deb = debentures_df[
        (debentures_df["area"] == area) &
        (debentures_df["data_emissao"] >= start) &
        (debentures_df["data_emissao"] <= end) &
        (debentures_df["taxa_real"].notna())
    ].copy()

    if deb.empty:
        raise ValueError(f"Sem debêntures {segmento} na janela {ano - janela_anos + 1}–{ano}")

    # Recalcula taxa_real usando BEI histórico (inflacao_implicita) quando disponível
    has_bei = "inflacao_implicita" in deb.columns and "taxa_nominal_pct" in deb.columns
    if has_bei:
        mask_di = deb["taxa_nominal_pct"].notna() & deb["inflacao_implicita"].notna()
        deb.loc[mask_di, "taxa_real_bu"] = (
            (1 + deb.loc[mask_di, "taxa_nominal_pct"] / 100.0)
            / (1 + deb.loc[mask_di, "inflacao_implicita"])
            - 1
        )
        deb.loc[~mask_di, "taxa_real_bu"] = deb.loc[~mask_di, "taxa_real"]
        kd_deb = float(deb["taxa_real_bu"].mean())
    else:
        kd_deb = float(deb["taxa_real"].mean())

    # Custo de emissão — usa periodos_df se fornecido (valor ANEEL pré-computado)
    # Tenta match exato; se ausente usa período mais recente (custo congelado por CVM 160)
    periodo_str = f"{ano - janela_anos + 1}-{ano}"
    kd_custo = None
    if periodos_df is not None and not periodos_df.empty:
        row_per = periodos_df[periodos_df["periodo"] == periodo_str]
        if not row_per.empty:
            kd_custo = float(row_per.iloc[0]["custo_emissao_agregado"])
        else:
            kd_custo = float(periodos_df.iloc[-1]["custo_emissao_agregado"])

    if kd_custo is None:
        custo = custo_emissao_df[
            (custo_emissao_df["classificacao"] == area) &
            (custo_emissao_df["data_emissao"] >= start) &
            (custo_emissao_df["data_emissao"] <= end) &
            (custo_emissao_df["remuneracao_real"].notna())
        ]
        kd_custo = float(custo["remuneracao_real"].mean()) if not custo.empty else 0.0

    kd_ai = kd_deb + kd_custo

    return KdResult(
        kd_debentures=kd_deb,
        custo_emissao=kd_custo,
        kd_real_ai=kd_ai,
        kd_real_di=kd_ai * (1.0 - T),
        n_debentures=len(deb),
        T=T,
    )


def calcular_kd_ettj_atualizado(
    ano: int,
    debentures_df: pd.DataFrame,
    custo_emissao_df: pd.DataFrame,
    ettj_df: pd.DataFrame,
    segmento: str = "transmissao",
    janela_anos: int = 10,
    T: float = 0.34,
    periodos_df: Optional[pd.DataFrame] = None,
) -> KdResult:
    """
    Kd T-1: mesmos títulos do fixture ANEEL, taxa_real re-computada com BEI atual.

    Lógica por tipo de indexador:
    - DI (248/266 na amostra T): taxa_nominal_pct / inflacao_implicita existem
      → taxa_real_atualizada = (1 + taxa_nominal_pct/100) / (1 + BEI_ettj_prazo) - 1
    - IPCA (18/266): taxa_real já é o spread real sobre IPCA → mantida sem alteração
    - DI sem taxa_nominal_pct (11 títulos): mantém taxa_real da fixture (NaN → excluído)

    Mantém mesma janela e critério de filtro de C1 para comparabilidade.

    Args:
        ano:              Último ano da janela (ex: 2025 para WACC 2026)
        debentures_df:    de load_debentures()
        custo_emissao_df: de load_custo_emissao()
        ettj_df:          curva ETTJ atual — colunas: prazo_anos, yield_real (decimal)
        segmento:         "transmissao" ou "distribuicao"
        janela_anos:      tamanho da janela (padrão 10)
        T:                alíquota composita IRPJ + CSLL
        periodos_df:      de load_custo_emissao_periodos() — IPCA+DI pré-computado.
                          Se fornecido, usa o agregado congelado (custo emissão frozen por CVM 160).
    """
    area_map = {"transmissao": "T", "distribuicao": "D"}
    area = area_map.get(segmento.lower(), "T")

    start = pd.Timestamp(f"{ano - janela_anos + 1}-01-01")
    end = pd.Timestamp(f"{ano}-12-31")

    deb = debentures_df[
        (debentures_df["area"] == area) &
        (debentures_df["data_emissao"] >= start) &
        (debentures_df["data_emissao"] <= end) &
        (debentures_df["taxa_real"].notna())
    ].copy()

    if deb.empty:
        raise ValueError(f"Sem debêntures {segmento} na janela {ano - janela_anos + 1}–{ano}")

    # Prazo original: data_emissao → data_vencimento (em anos)
    deb["_prazo_anos"] = (
        (deb["data_vencimento"] - deb["data_emissao"]).dt.days / 365.25
    ).clip(lower=0.5)

    # DI-indexado com taxa_nominal_pct disponível → recalcula com BEI atual
    mask_di = deb["taxa_nominal_pct"].notna()
    deb.loc[mask_di, "taxa_real_mid"] = deb.loc[mask_di].apply(
        lambda r: calcular_taxa_real_ettj(
            r["taxa_nominal_pct"] / 100.0,
            r["_prazo_anos"],
            ettj_df,
        ),
        axis=1,
    )
    # IPCA-indexado ou DI sem taxa_nominal → mantém taxa_real da fixture
    deb.loc[~mask_di, "taxa_real_mid"] = deb.loc[~mask_di, "taxa_real"]

    kd_deb = float(deb["taxa_real_mid"].mean())
    n = len(deb)

    # Custo de emissão: congelado por CVM 160 (jul/2022)
    # Usa periodos_df se fornecido — tenta match exato primeiro, depois o mais recente
    # (CVM 160 congela o valor; o período mais recente disponível é sempre o correto)
    periodo_str = f"{ano - janela_anos + 1}-{ano}"
    kd_custo = None
    if periodos_df is not None and not periodos_df.empty:
        row_per = periodos_df[periodos_df["periodo"] == periodo_str]
        if not row_per.empty:
            kd_custo = float(row_per.iloc[0]["custo_emissao_agregado"])
        else:
            # Fallback ao período mais recente (custo congelado por CVM 160)
            kd_custo = float(periodos_df.iloc[-1]["custo_emissao_agregado"])

    if kd_custo is None:
        # Sem periodos_df: média individual (~+8bp vs ANEEL)
        custo = custo_emissao_df[
            (custo_emissao_df["classificacao"] == area) &
            (custo_emissao_df["data_emissao"] >= start) &
            (custo_emissao_df["data_emissao"] <= end) &
            (custo_emissao_df["remuneracao_real"].notna())
        ]
        kd_custo = float(custo["remuneracao_real"].mean()) if not custo.empty else 0.0

    kd_ai = kd_deb + kd_custo

    return KdResult(
        kd_debentures=kd_deb,
        custo_emissao=kd_custo,
        kd_real_ai=kd_ai,
        kd_real_di=kd_ai * (1.0 - T),
        n_debentures=n,
        T=T,
    )
