# Inflation Engine — Context Document

> Use this document as context when building systems that reuse the calculation engine.
> It describes contracts, methodology, and known edge cases — not UI or app structure.

---

## 1. Entry Points

### `corrigir_valor` — single-value monetary correction
```python
from engine.deflator import corrigir_valor, CorrecaoResult

result: CorrecaoResult = corrigir_valor(
    valor       = 1000.0,       # float — R$ amount to correct
    data_origem = "01/2010",    # "MM/YYYY" — origin month (inclusive)
    data_destino= "06/2026",    # "MM/YYYY" — destination month (inclusive); may be future
    indice      = "IPCA",       # see §3 for valid values
    force_refresh = False,      # bool — bypass local cache
    projecao    = "focus",      # "focus" | "ettj" (ETTJ only valid for IPCA)
)
```

**Returns `CorrecaoResult`:**
| Field | Type | Description |
|---|---|---|
| `valor_original` | float | Input value |
| `valor_corrigido` | float | Corrected value |
| `fator_acumulado` | float | Cumulative factor (e.g. 2.31) |
| `variacao_pct` | float | `(fator - 1) × 100` |
| `n_meses` | int | Number of months in interval |
| `data_origem` | str | "MM/YYYY" |
| `data_destino` | str | "MM/YYYY" (may be adjusted if no projection available) |
| `indice` | str | Index used |
| `tem_projecao` | bool | True if any month uses projected data |
| `ultimo_realizado` | str | Last month with actual realized data ("MM/YYYY") |
| `fonte_projecao` | str\|None | "Focus Anual", "Focus Anual + extrapolação", "ETTJ BEI", or None |
| `serie_mensal` | pd.Series | Monthly factors (PeriodIndex → float), used for charts |
| `data_warning` | str\|None | Non-fatal warning (cache age, missing projection, etc.) |

---

### `build_inflation_vector` — monthly factor table for a date range
```python
from engine.vector import build_inflation_vector, InflationVector

vec: InflationVector = build_inflation_vector(
    base_date  = "01/2020",   # "MM/YYYY" — month where accumulated factor = 1.0
    start_date = "01/2018",   # "MM/YYYY" — first row of output table
    end_date   = "12/2026",   # "MM/YYYY" — last row of output table
    indice     = "IPCA",
    force_refresh = False,
    projecao   = "focus",     # "focus" | "ettj"
)
```

**Returns `InflationVector`:**
- `vec.data` — `pd.DataFrame` with columns:

| Column | Type | Description |
|---|---|---|
| `Período` | str | "MM/YYYY" |
| `Taxa Mensal (%)` | float | Monthly variation, e.g. 0.42 |
| `Fator Mensal` | float | `1 + taxa/100` |
| `Fator Acumulado` | float | Chain product from `base_date` (base = 1.0) |
| `Variação Acum. (%)` | float | `(fator_acum - 1) × 100` |
| `Tipo` | str | "Realizado" \| "Projeção Focus" \| "Projeção ETTJ BEI" |

- `vec.last_realized` — str "MM/YYYY", last month with actual data
- `vec.has_projection` — bool

---

### `get_factor_between` — raw factor, no I/O
```python
from engine.index_builder import get_factor_between

# monthly_pct: pd.Series with PeriodIndex (freq="M") and values in % (e.g. 0.42)
factor = get_factor_between(monthly_pct, "01/2020", "06/2026")
# Returns float. Interval is INCLUSIVE on both ends (compatible with BCB Calculadora do Cidadão).
# For deflation (end < start): returns 1 / forward_factor automatically.
```

---

## 2. Calculation Methodology

### Factor accumulation (realized data)
```
factor(start → end) = ∏ (1 + rₜ/100)  for t in [start, end] inclusive
```
Both endpoints are included. This matches the BCB Calculadora do Cidadão convention.

### Projection — Focus (default)
Source: BCB Boletim Focus (median expectations), via BCB API.

- **Annual expectation → monthly distribution:**
  - Uniform compound rate: `monthly = (1 + annual/100)^(1/12) − 1`
  - For the current year (partial realized months): residual factor = `annual_factor / realized_factor_so_far`, distributed equally across remaining months.
  - For years beyond Focus horizon: last available annual rate is replicated (`fonte_projecao = "Focus Anual + extrapolação"`).
- Focus monthly rates are **ignored** — only annual medians are used.

### Projection — ETTJ BEI (IPCA only)
Source: ANBIMA ETTJ curve (NTN-B implied inflation = Break-Even Inflation).

- Uses **forward rates between consecutive vertices**, not spot rates.
- Forward between vertices v1, v2 (in business days `du`):
  ```
  f = [(1 + bei2/100)^(du2/252) / (1 + bei1/100)^(du1/252)]^(252/Δdu) − 1
  ```
- Each projected month `t` is assigned `du_t = t × 21 du` from the first projected month.
- Beyond the last vertex: last forward rate is held constant.
- Before the first vertex: BEI spot of the first vertex is used.

---

## 3. Available Indices

| Key | Label | Source (BCB SGS) | Start | Focus projection |
|---|---|---|---|---|
| `"IPCA"` | IPCA | 433 | 07/1994 | Yes (+ ETTJ option) |
| `"IGPM"` | IGP-M | 189 | 01/1940 | Yes |
| `"IPCA15"` | IPCA-15 | 7478 | 02/1999 | Yes |
| `"INPC"` | INPC | 188 | 01/1979 | Yes |
| `"INCC"` | INCC | 192 | 01/1985 | No |
| `"SELIC"` | SELIC | 4390 | 06/1986 | No |
| `"CDI"` | CDI | 4391 | 06/1986 | No |

Indices without Focus projection (`INCC`, `SELIC`, `CDI`): `data_destino` is silently capped to `ultimo_realizado` when the requested end date is in the future. A `data_warning` is set.

---

## 4. Date Format

All date parameters use `"MM/YYYY"` strings (e.g. `"07/1994"`, `"06/2026"`).
Internal representation: `pd.Period` with `freq="M"`.

Parser: `engine.index_builder._parse_period("MM/YYYY") → pd.Period`

---

## 5. Limits and Guardrails

| Constraint | Value | Error raised |
|---|---|---|
| Minimum origin date | Per-index `start` (see §3) | `PrePlanoRealError` |
| Maximum future destination | Today + 120 months (10 years) | `FutureLimitError` |
| Invalid index key | — | `KeyError` |
| No cache and API unreachable | — | `NoCacheError` |
| Empty interval after filtering | — | `ValueError` |

---

## 6. Data Layer

- **Realized series**: fetched from BCB SGS API, cached locally (TTL: 1 day).
- **Focus projections**: fetched from BCB Focus API, cached locally (TTL: 7 days).
- **ETTJ**: fetched from ANBIMA, cached locally.
- `force_refresh=True` bypasses cache on any call.
- `get_realized_series(indice)` returns `(series, from_cache, warning)` — `warning` is non-None when data is stale.

---

## 7. Out of Scope

The engine does NOT:
- Convert between currencies or apply exchange rates.
- Provide pre-Plano Real corrections (before 07/1994 for IPCA).
- Interpolate within a month (granularity is monthly).
- Apply seasonal adjustment to projections.
- Chain multiple indices in a single call (do it externally by multiplying factors).
