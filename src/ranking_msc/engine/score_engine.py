"""
ranking_msc.engine.score_engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Motor de pontuação 0-100 baseado no Indicador de Conformidade Fiscal (ICF).

Implementa o modelo definido em doc/modelo_pontuacao.md v1.3:
- Peso w_r dinâmico: determinado pela severidade observada na execução.
- Regras INFO-only (is_scoring=False) excluídas do cálculo.
- Dimensões com Σw_r = 0 excluídas e pesos renormalizados.

Uso:
    from ranking_msc.engine.score_engine import calculate_score
    result = calculate_score(engine_result.pendencias, executed_rule_ids)
    print(result.pontuacao, result.banda)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from ranking_msc.rules.base import RULE_REGISTRY

logger = logging.getLogger("ranking_msc")

# ---------------------------------------------------------------------------
# Pesos das dimensões (W_d) — doc/modelo_pontuacao.md §4
# ---------------------------------------------------------------------------
DIMENSION_WEIGHTS: dict[str, float] = {
    "Estrutura": 0.20,
    "Fechamento": 0.25,
    "IC_Dominio": 0.30,
    "PCASP_Completude": 0.15,
    "Temporal": 0.10,
}

# ---------------------------------------------------------------------------
# Mapeamento de categorias (dimensao da regra) → dimensão de pontuação
# doc/modelo_pontuacao.md §3
# ---------------------------------------------------------------------------
DIMENSION_CATEGORIES: dict[str, list[str]] = {
    "Estrutura": ["Estrutura", "Formato", "Duplicidade"],
    "Fechamento": ["Fechamento", "Interconta"],
    "IC_Dominio": ["IC", "PO", "NR", "ND", "FR", "CO", "FS", "DC", "FP", "AI"],
    "PCASP_Completude": ["PCASP", "Completude", "Superávit"],
    "Temporal": ["Temporal", "Qualidade"],
}

# Lookup inverso: categoria → dimensão de pontuação
_CATEGORY_TO_DIMENSION: dict[str, str] = {
    cat: dim
    for dim, cats in DIMENSION_CATEGORIES.items()
    for cat in cats
}

# ---------------------------------------------------------------------------
# Bandas de classificação A-E — doc/modelo_pontuacao.md §6
# (threshold, banda) — primeira entrada com score >= threshold vence
# ---------------------------------------------------------------------------
_BANDS: list[tuple[float, str]] = [
    (95.0, "A"),
    (85.0, "B"),
    (75.0, "C"),
    (65.0, "D"),
    (0.0, "E"),
]


# ---------------------------------------------------------------------------
# Dataclasses de resultado
# ---------------------------------------------------------------------------


@dataclass
class DimensionScore:
    """Pontuação e breakdown de uma dimensão individual."""

    dimension: str
    """Nome da dimensão de pontuação (ex: 'Estrutura', 'IC_Dominio')."""

    score: float
    """P_d: razão de conformidade da dimensão (0.0–1.0)."""

    weight_normalized: float
    """W_norm_d: peso renormalizado desta dimensão no score final."""

    rules_total: int
    """Regras pontuáveis executadas nesta dimensão."""

    rules_passed: int
    """Regras que passaram sem issues pontuáveis."""

    rules_failed_alerta: int
    """Regras que falharam com ALERTA (sem ERRO)."""

    rules_failed_erro: int
    """Regras que falharam com ERRO."""


@dataclass
class ScoreResult:
    """Resultado completo do cálculo de pontuação."""

    pontuacao: float
    """Nota final 0-100 (arredondada a 2 casas decimais)."""

    banda: str
    """Banda de classificação: 'A' (≥95) a 'E' (<65)."""

    dimensions: dict[str, DimensionScore]
    """Breakdown por dimensão — inclui apenas dimensões ativas."""

    regras_executadas: int
    """Total de regras pontuáveis (is_scoring=True) executadas."""

    regras_falhas_erro: int
    """Regras que produziram ≥1 issue ERRO."""

    regras_falhas_alerta: int
    """Regras que produziram ≥1 issue ALERTA (sem ERRO)."""


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _classify_band(pontuacao: float) -> str:
    """Retorna banda A-E com base na pontuação final.

    Args:
        pontuacao: nota 0-100.

    Returns:
        Letra da banda conforme doc/modelo_pontuacao.md §6.
    """
    for threshold, band in _BANDS:
        if pontuacao >= threshold:
            return band
    return "E"  # fallback — nunca atingido pois 0.0 >= 0.0


# ---------------------------------------------------------------------------
# Função principal — implementada na Task 3
# ---------------------------------------------------------------------------


def calculate_score(
    pendencias: pd.DataFrame,
    executed_rule_ids: list[str],
) -> ScoreResult:
    """Calcula a pontuação 0-100 com base nas pendências do motor.

    Implementa o modelo de pontuação de doc/modelo_pontuacao.md v1.3.

    Args:
        pendencias: DataFrame de pendências de run_engine() com colunas
                    regra_id e severidade (pode ser vazio).
        executed_rule_ids: IDs das regras efetivamente executadas.

    Returns:
        ScoreResult com pontuação final, banda e breakdown por dimensão.
    """
    # 1. Para cada regra executada: determinar w_r, ok_r e dimensão de pontuação
    rule_data: list[dict[str, object]] = []

    for rule_id in executed_rule_ids:
        rule_class = RULE_REGISTRY.get(rule_id)
        if rule_class is None:
            continue
        # Excluir regras INFO-only
        if not rule_class.is_scoring:
            continue
        # Determinar dimensão de pontuação
        dimension = _CATEGORY_TO_DIMENSION.get(rule_class.dimensao)
        if dimension is None:
            logger.warning(
                "Regra %s tem dimensao '%s' não mapeada às 5 dimensões de pontuação"
                " — ignorada.",
                rule_id,
                rule_class.dimensao,
            )
            continue

        # Issues desta regra no DataFrame de pendências
        if len(pendencias) > 0 and "regra_id" in pendencias.columns:
            rule_issues = pendencias[pendencias["regra_id"] == rule_id]
        else:
            rule_issues = pd.DataFrame(columns=["severidade"])

        has_erro = (
            len(rule_issues) > 0 and (rule_issues["severidade"] == "ERRO").any()
        )
        has_alerta = (
            not has_erro
            and len(rule_issues) > 0
            and (rule_issues["severidade"] == "ALERTA").any()
        )

        # w_r dinâmico — doc/modelo_pontuacao.md §5.1
        if has_erro:
            w_r = 2
            ok_r = 0
        elif has_alerta:
            w_r = 1
            ok_r = 0
        else:
            # Passou (pontuável) — w_r = 1, ok_r = 1
            w_r = 1
            ok_r = 1

        rule_data.append(
            {
                "rule_id": rule_id,
                "dimension": dimension,
                "w_r": w_r,
                "ok_r": ok_r,
                "has_erro": has_erro,
                "has_alerta": has_alerta,
            }
        )

    # Edge case: nenhuma regra pontuável executada
    if not rule_data:
        return ScoreResult(
            pontuacao=0.0,
            banda="E",
            dimensions={},
            regras_executadas=0,
            regras_falhas_erro=0,
            regras_falhas_alerta=0,
        )

    # 2. Agregar numerador e denominador por dimensão
    dim_num: dict[str, float] = {d: 0.0 for d in DIMENSION_WEIGHTS}
    dim_den: dict[str, float] = {d: 0.0 for d in DIMENSION_WEIGHTS}
    dim_counts: dict[str, dict[str, int]] = {
        d: {"total": 0, "passed": 0, "alerta": 0, "erro": 0}
        for d in DIMENSION_WEIGHTS
    }

    for rd in rule_data:
        dim = str(rd["dimension"])
        dim_num[dim] += float(rd["w_r"]) * float(rd["ok_r"])  # type: ignore[arg-type]
        dim_den[dim] += float(rd["w_r"])  # type: ignore[arg-type]
        dim_counts[dim]["total"] += 1
        if rd["has_erro"]:
            dim_counts[dim]["erro"] += 1
        elif rd["has_alerta"]:
            dim_counts[dim]["alerta"] += 1
        else:
            dim_counts[dim]["passed"] += 1

    # 3. Identificar dimensões ativas (Σw_r > 0) e renormalizar pesos
    # — doc/modelo_pontuacao.md §5.3 e §8.2
    active: dict[str, float] = {
        d: DIMENSION_WEIGHTS[d] for d in DIMENSION_WEIGHTS if dim_den[d] > 0
    }
    w_total = sum(active.values())
    # w_total > 0 garantido pois rule_data não está vazio
    w_norm: dict[str, float] = {d: w / w_total for d, w in active.items()}

    # 4. Calcular P_d e pontuação final — doc/modelo_pontuacao.md §5.3 e §5.4
    pontuacao_raw = 0.0
    dimensions: dict[str, DimensionScore] = {}

    for dim, wn in w_norm.items():
        p_d = dim_num[dim] / dim_den[dim]
        pontuacao_raw += wn * p_d
        dimensions[dim] = DimensionScore(
            dimension=dim,
            score=p_d,
            weight_normalized=wn,
            rules_total=dim_counts[dim]["total"],
            rules_passed=dim_counts[dim]["passed"],
            rules_failed_alerta=dim_counts[dim]["alerta"],
            rules_failed_erro=dim_counts[dim]["erro"],
        )

    pontuacao = round(100.0 * pontuacao_raw, 2)

    # 5. Estatísticas globais
    total_executadas = sum(dim_counts[d]["total"] for d in DIMENSION_WEIGHTS)
    total_erro = sum(dim_counts[d]["erro"] for d in DIMENSION_WEIGHTS)
    total_alerta = sum(dim_counts[d]["alerta"] for d in DIMENSION_WEIGHTS)

    return ScoreResult(
        pontuacao=pontuacao,
        banda=_classify_band(pontuacao),
        dimensions=dimensions,
        regras_executadas=total_executadas,
        regras_falhas_erro=total_erro,
        regras_falhas_alerta=total_alerta,
    )
