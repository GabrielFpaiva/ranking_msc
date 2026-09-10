"""
app.api.schemas
~~~~~~~~~~~~~~~

Modelos Pydantic compartilhados entre as rotas da API MCRA PMJP.

Estes modelos definem o contrato JSON com o frontend (web/). Mantidos
deliberadamente pequenos: apenas os campos que o front consome. O dataframe
completo de pendências fica em rotas paginadas, não em respostas inline.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.api.uso_store import MAX_SEGUNDOS_POR_HEARTBEAT

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


class SummaryOut(BaseModel):
    """Resumo de uma competência já persistida (GET /api/summary).

    Reflete a competência ativa na Home sem depender do último ``POST /api/run``:
    score, total de pendências e ranking de regras, lidos do snapshot.
    """

    siconfi: str
    competencia: str
    total_pendencias: int
    score: ScoreOut
    top_regras: list[TopRuleOut]


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


class DeferredFeatureOut(BaseModel):
    """Resposta informativa para recursos ainda não entregues."""

    detail: str
    code: str = "not_implemented"
    see: str


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


# ---------------------------------------------------------------------------
# Listagens (fatia D — Caixa, Passivos)
# ---------------------------------------------------------------------------


class ContaResumoOut(BaseModel):
    conta_contabil: str
    saldo_inicial: float
    saldo_final: float
    movimento_liquido: float
    fr: str | None = None


class ContaListGroupOut(BaseModel):
    label: str
    prefixes: list[str]
    total_saldo_final: float
    items: list[ContaResumoOut]


class ContaListOut(BaseModel):
    siconfi: str
    competencia: str
    groups: list[ContaListGroupOut]


class SuperavitRowOut(BaseModel):
    fr: str
    ativo_financeiro: float
    passivo_financeiro: float
    resultado_financeiro: float


class SuperavitOut(BaseModel):
    siconfi: str
    competencia: str
    total_ativo_financeiro: float
    total_passivo_financeiro: float
    total_resultado_financeiro: float
    linhas_consideradas: int
    contas_consideradas: int
    items: list[SuperavitRowOut]


# ---------------------------------------------------------------------------
# Visões — Executivo, Comparar, Execução, Ranking (fatia E)
# ---------------------------------------------------------------------------


class RecommendationOut(BaseModel):
    """Ação recomendada derivada heuristicamente do estado atual."""

    titulo: str
    descricao: str
    severidade: Severidade = "ALERTA"
    referencia: str | None = Field(None, description="ID de regra ou dimensão associada")


class RecommendationsOut(BaseModel):
    siconfi: str
    competencia: str
    items: list[RecommendationOut]


class CompareDimensionOut(BaseModel):
    dimension: str
    score_a: float
    score_b: float
    delta: float


class CompareSideOut(BaseModel):
    competencia: str
    pontuacao: float
    banda: Banda
    total_pendencias: int


class CompareOut(BaseModel):
    siconfi: str
    a: CompareSideOut
    b: CompareSideOut
    delta_score: float
    delta_pendencias: int
    dimensions: list[CompareDimensionOut]


class LogEntryOut(BaseModel):
    ts: str
    level: str
    msg: str
    execucao_id: str | None = None
    competencia: str | None = None
    modulo: str | None = None
    regra_id: str | None = None
    siconfi: str | None = None


class LogPageOut(BaseModel):
    total: int
    items: list[LogEntryOut]


# ---------------------------------------------------------------------------
# Gestão da Informação — entregas ao Siconfi (F7)
# ---------------------------------------------------------------------------


class EntregaOut(BaseModel):
    """Uma entrega ao Siconfi, classificada."""

    instituicao: str
    entregavel: str
    periodo: int
    periodicidade: str
    status: str = Field(..., description="HOMOLOGADO, RETIFICADO ou SEM_STATUS")
    data_status: datetime | None = None
    fim_periodo: date | None = None
    dias_apos_fim_periodo: int | None = None
    prazo_dias: int | None = Field(
        None, description="Prazo configurado; ausente quando não há base normativa"
    )
    atrasada: bool | None = Field(
        None, description="null quando não há base para julgar — nunca inferir False"
    )


class ResumoEntregasOut(BaseModel):
    """Contagens do exercício."""

    total: int
    homologadas: int
    retificadas: int


class EntregasOut(BaseModel):
    """Resposta de GET /api/entregas."""

    ano: int
    id_ente: int
    origem: str = Field(
        ...,
        description=(
            "De onde veio o dado — não indica degradação. "
            "'api': buscado agora no Siconfi. "
            "'cache': servido do cache, dentro OU fora do TTL — ver 'aviso' "
            "para saber se houve degradação. "
            "'indisponivel': sem API e sem cache."
        ),
    )
    buscado_em: datetime | None = Field(
        None, description="Quando o dado exibido foi obtido — a idade do dado"
    )
    aviso: str | None = Field(
        None,
        description=(
            "Não nulo apenas quando houve degradação (Siconfi indisponível). "
            "Cache dentro do TTL não gera aviso — é o caminho normal."
        ),
    )
    resumo: ResumoEntregasOut
    entregas: list[EntregaOut]


# ---------------------------------------------------------------------------
# Tempo de uso por usuário (F6)
# ---------------------------------------------------------------------------


class HeartbeatIn(BaseModel):
    """Batida de relógio enviada pelo front a cada ~60 s.

    O teto de ``MAX_SEGUNDOS_POR_HEARTBEAT`` é deliberado: o heartbeat é de
    60 s, e sem limite qualquer cliente se daria horas de uso com uma
    requisição forjada. Esta é a fonte canônica do valor no servidor — o
    browser espelha o mesmo número em ``LIMITE_SERVIDOR_S``
    (``web/src/store/relogioUso.ts``), e os dois precisam mudar juntos.
    """

    rota: str
    aberto_s: int = Field(
        ..., ge=0, le=MAX_SEGUNDOS_POR_HEARTBEAT, description="Segundos com a aba visível"
    )
    ativo_s: int = Field(
        ..., ge=0, le=MAX_SEGUNDOS_POR_HEARTBEAT, description="Segundos com interação"
    )

    @field_validator("ativo_s")
    @classmethod
    def ativo_nao_excede_aberto(cls, valor: int, info: ValidationInfo) -> int:
        """Garante que tempo ativo seja subconjunto do tempo aberto."""
        if "aberto_s" in info.data and valor > info.data["aberto_s"]:
            raise ValueError("Tempo ativo não pode ser maior que o tempo aberto.")
        return valor


class UsoHojeOut(BaseModel):
    """Totais do dia corrente para o usuário autenticado."""

    aberto_s: int
    ativo_s: int


class UsoDiaOut(BaseModel):
    """Total de um dia dentro do mês consultado."""

    dia: str = Field(..., description="YYYY-MM-DD")
    aberto_s: int
    ativo_s: int
    por_rota: dict[str, int] = Field(
        default_factory=dict,
        description="rota → segundos de aba aberta naquele dia",
    )


class UsoRotaOut(BaseModel):
    """Total de uma tela dentro do período selecionado."""

    rota: str
    aberto_s: int
    ativo_s: int


class UsoMesOut(BaseModel):
    """Total de um mês dentro do ano consultado."""

    mes: str = Field(..., description="YYYY-MM")
    aberto_s: int
    ativo_s: int
    por_rota: dict[str, int] = Field(
        default_factory=dict,
        description="rota → segundos de aba aberta naquele mês",
    )


class UsoAnualOut(BaseModel):
    """Resposta de /api/uso/anual — doze meses, sempre completos e em ordem."""

    ano: int
    total_aberto_s: int
    total_ativo_s: int
    meses: list[UsoMesOut]


class UsoHistoricoOut(BaseModel):
    """Resposta de /api/uso/historico.

    ``dias`` cobre sempre o **mês inteiro** de ``ref``, com zeros preenchidos,
    para o front desenhar as semanas agrupadas sob o cabeçalho do mês sem
    precisar de várias requisições. ``rotas`` e os totais referem-se apenas ao
    período selecionado por ``escala``.
    """

    escala: Literal["dia", "semana", "mes"]
    ref: str
    inicio: str
    fim: str
    total_aberto_s: int
    total_ativo_s: int
    dias: list[UsoDiaOut]
    rotas: list[UsoRotaOut]
