"""
app.api.schemas
~~~~~~~~~~~~~~~

Modelos Pydantic compartilhados entre as rotas da API MCRA PMJP.

Estes modelos definem o contrato JSON com o frontend (web/). Mantidos
deliberadamente pequenos: apenas os campos que o front consome. O dataframe
completo de pendências fica em rotas paginadas, não em respostas inline.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severidade = Literal["ERRO", "ALERTA", "INFO"]
Banda = Literal["A", "B", "C", "D", "E"]


class DimensionScoreOut(BaseModel):
    """Breakdown de uma dimensão no cálculo de score."""

    dimension: str
    score: float = Field(..., description="P_d entre 0.0 e 1.0")
    weight_normalized: float
    rules_total: int
    rules_passed: int
    rules_failed_alerta: int
    rules_failed_erro: int


class ScoreOut(BaseModel):
    """Resumo de score calculado para uma competência."""

    pontuacao: float = Field(..., description="Nota 0–100, 2 casas decimais")
    banda: Banda
    dimensions: dict[str, DimensionScoreOut]
    regras_executadas: int
    regras_falhas_erro: int
    regras_falhas_alerta: int


class TopRuleOut(BaseModel):
    """Linha do ranking 'top regras violadas' da Home."""

    regra_id: str
    regra_nome: str
    dimensao: str
    severidade_max: Severidade
    pendencias: int


class CompetenciaOut(BaseModel):
    """Identificação de uma competência disponível para um ente."""

    siconfi: str
    competencia: str = Field(..., description="YYYY-MM")
    has_resultado: bool = True


class RunSummaryOut(BaseModel):
    """Resumo de uma execução do motor (POST /api/run)."""

    execucao_id: str
    siconfi: str
    competencia: str
    status: Literal["OK", "PARCIAL", "ERRO"]
    regras_executadas: int
    regras_com_erro: int
    total_pendencias: int
    score: ScoreOut
    top_regras: list[TopRuleOut]
    inicio: str
    fim: str


class PendenciaOut(BaseModel):
    """Linha da tabela de Pendências."""

    regra_id: str
    regra_nome: str
    dimensao: str
    severidade: Severidade
    conta_contabil: str
    descricao: str
    valor_esperado: str | None = None
    valor_encontrado: str | None = None
    competencia: str


class PendenciasPageOut(BaseModel):
    """Resposta paginada de pendências."""

    competencia: str
    siconfi: str
    total: int
    items: list[PendenciaOut]


class ScoreHistoryPointOut(BaseModel):
    """Ponto na linha do tempo de scores (Home, Executivo)."""

    competencia: str
    pontuacao: float
    banda: Banda
    total_pendencias: int


class ScoreHistoryOut(BaseModel):
    """Histórico de score por competência para um ente."""

    siconfi: str
    points: list[ScoreHistoryPointOut]


class ErrorOut(BaseModel):
    """Resposta de erro padronizada."""

    detail: str
    code: str = "internal_error"


# ---------------------------------------------------------------------------
# Regras / Heatmap / Drawer Regra (fatia C)
# ---------------------------------------------------------------------------


class RuleOut(BaseModel):
    """Item da listagem de regras (catálogo)."""

    rule_id: str
    rule_name: str
    dimensao: str
    is_scoring: bool


class RuleDetailOut(BaseModel):
    """Detalhe de uma regra para o Drawer Regra."""

    rule_id: str
    rule_name: str
    dimensao: str
    is_scoring: bool
    descricao: str = Field(..., description="Resumo da docstring do módulo da regra")
    formula: str | None = Field(None, description="Trecho de fórmula/regra (se houver)")


class HeatmapCellOut(BaseModel):
    regra_id: str
    competencia: str
    pendencias: int
    severidade_max: Severidade | None = None


class HeatmapRegraOut(BaseModel):
    id: str
    nome: str
    dimensao: str


class HeatmapOut(BaseModel):
    siconfi: str
    competencias: list[str]
    regras: list[HeatmapRegraOut]
    cells: list[HeatmapCellOut]


class RuleHistoryOut(BaseModel):
    siconfi: str
    rule_id: str
    cells: list[HeatmapCellOut]


# ---------------------------------------------------------------------------
# Drawer Conta
# ---------------------------------------------------------------------------


class ContaSaldosOut(BaseModel):
    saldo_inicial_devedor: float
    saldo_inicial_credor: float
    movimento_devedor: float
    movimento_credor: float
    saldo_final_devedor: float
    saldo_final_credor: float


class ContaDetailOut(BaseModel):
    conta_contabil: str
    competencia: str
    siconfi: str
    saldos: ContaSaldosOut
    classificadores: dict[str, str]
    pcasp: dict[str, str] | None
    pendencias_count: int
