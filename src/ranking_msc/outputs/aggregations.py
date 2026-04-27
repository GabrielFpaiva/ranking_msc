"""
ranking_msc.outputs.aggregations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Agregações derivadas dos snapshots persistidos pelo motor.

Centraliza as transformações que são puras — recebem DataFrames já lidos do disco
e devolvem estruturas prontas para o frontend MCRA PMJP. As rotas FastAPI em
``app/api/routes/`` consomem estas funções; assim a camada API não duplica lógica
de pandas.

A leitura de disco (snapshots Parquet, scoring_metadata.json) continua em
``ranking_msc.outputs.snapshot`` — este módulo só transforma o que já foi lido.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ranking_msc.exceptions import SnapshotNotFoundError
from ranking_msc.outputs.snapshot import read_snapshot
from ranking_msc.rules.base import RULE_REGISTRY

logger = logging.getLogger("ranking_msc")


_SEVERIDADE_RANK: dict[str, int] = {"ERRO": 3, "ALERTA": 2, "INFO": 1}


@dataclass(frozen=True)
class TopRule:
    """Linha do ranking de regras violadas em uma competência."""

    regra_id: str
    regra_nome: str
    dimensao: str
    severidade_max: str
    pendencias: int


def top_violated_rules(
    pendencias: pd.DataFrame,
    *,
    limit: int = 8,
) -> list[TopRule]:
    """Lista as ``limit`` regras com mais pendências em uma execução.

    Args:
        pendencias: DataFrame de pendências (FACT_RESULTADO_REGRAS_COLUMNS).
        limit: número máximo de linhas a retornar.

    Returns:
        Lista ordenada decrescente por pendencias e severidade máxima.
    """
    if pendencias.empty:
        return []

    grouped = (
        pendencias.assign(
            _sev_rank=pendencias["severidade"].map(_SEVERIDADE_RANK).fillna(0),
        )
        .groupby(["regra_id", "regra_nome", "dimensao"], as_index=False)
        .agg(pendencias=("severidade", "size"), _sev_rank_max=("_sev_rank", "max"))
        .sort_values(
            by=["pendencias", "_sev_rank_max"],
            ascending=[False, False],
        )
        .head(limit)
    )

    inv_rank = {v: k for k, v in _SEVERIDADE_RANK.items()}
    return [
        TopRule(
            regra_id=str(row["regra_id"]),
            regra_nome=str(row["regra_nome"]) or _registry_name(str(row["regra_id"])),
            dimensao=str(row["dimensao"]),
            severidade_max=inv_rank.get(int(row["_sev_rank_max"]), "INFO"),
            pendencias=int(row["pendencias"]),
        )
        for _, row in grouped.iterrows()
    ]


def filter_pendencias(
    pendencias: pd.DataFrame,
    *,
    regra_id: str | None = None,
    severidade: str | None = None,
    conta_contabil_prefix: str | None = None,
) -> pd.DataFrame:
    """Aplica filtros usuais da tela Pendências sobre o DataFrame de pendências.

    Args:
        pendencias: DataFrame da execução (pode ser vazio).
        regra_id: filtra por regra exata (ex: ``"R054"``).
        severidade: filtra por severidade exata (``ERRO``/``ALERTA``/``INFO``).
        conta_contabil_prefix: filtra contas que começam com este prefixo (ex: ``"1.1.1"``).

    Returns:
        DataFrame filtrado (cópia rasa).
    """
    if pendencias.empty:
        return pendencias

    df = pendencias
    if regra_id:
        df = df[df["regra_id"] == regra_id]
    if severidade:
        df = df[df["severidade"] == severidade]
    if conta_contabil_prefix:
        df = df[df["conta_contabil"].astype(str).str.startswith(conta_contabil_prefix)]
    return df.reset_index(drop=True)


def _registry_name(rule_id: str) -> str:
    """Retorna o nome da regra olhando o RULE_REGISTRY (fallback ao id)."""
    rule_class = RULE_REGISTRY.get(rule_id)
    return rule_class.rule_name if rule_class else rule_id


# ---------------------------------------------------------------------------
# Heatmap: regras × competências
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeatmapCell:
    """Célula do heatmap: total de pendências e severidade máxima."""

    regra_id: str
    competencia: str
    pendencias: int
    severidade_max: str | None  # None se não houve pendência


@dataclass
class HeatmapMatrix:
    """Matriz para a tela Regras."""

    competencias: list[str] = field(default_factory=list)
    regras: list[dict[str, str]] = field(default_factory=list)  # {id, nome, dimensao}
    cells: list[HeatmapCell] = field(default_factory=list)


def discover_competencias(snapshots_dir: Path, siconfi: str) -> list[str]:
    """Varre o diretório de snapshots e devolve competências disponíveis para o ente."""
    base = snapshots_dir / siconfi
    if not base.is_dir():
        return []
    out = [
        p.parent.name
        for p in base.glob("*/resultado_regras.parquet")
    ]
    return sorted(out)


def build_heatmap(
    snapshots_dir: Path,
    siconfi: str,
    *,
    meses: int = 6,
) -> HeatmapMatrix:
    """Monta a matriz regras × competências a partir dos snapshots em disco.

    Args:
        snapshots_dir: diretório raiz de snapshots (ex: ``data/snapshots``).
        siconfi: código SICONFI do ente.
        meses: limite de competências (mais recentes) a considerar.

    Returns:
        HeatmapMatrix com lista de competências, lista de regras (RULE_REGISTRY)
        e células ``(regra_id, competencia, pendencias, severidade_max)``.

    Notas:
        Regras presentes no RULE_REGISTRY mas sem pendências em uma competência
        aparecem como células com ``pendencias=0`` e ``severidade_max=None``.
    """
    competencias = discover_competencias(snapshots_dir, siconfi)[-meses:]
    regras = sorted(RULE_REGISTRY.keys())
    matrix = HeatmapMatrix(
        competencias=competencias,
        regras=[
            {
                "id": rid,
                "nome": RULE_REGISTRY[rid].rule_name,
                "dimensao": RULE_REGISTRY[rid].dimensao,
            }
            for rid in regras
        ],
    )

    if not competencias:
        return matrix

    inv_rank = {v: k for k, v in _SEVERIDADE_RANK.items()}
    base = snapshots_dir / siconfi

    for competencia in competencias:
        try:
            df = read_snapshot(competencia, base_dir=base, label="resultado_regras")
        except SnapshotNotFoundError:
            continue

        if df.empty:
            counts = pd.DataFrame(columns=["regra_id", "qtd", "sev_rank"])
        else:
            counts = (
                df.assign(
                    _sev_rank=df["severidade"].map(_SEVERIDADE_RANK).fillna(0),
                )
                .groupby("regra_id", as_index=False)
                .agg(qtd=("severidade", "size"), sev_rank=("_sev_rank", "max"))
            )

        by_rule: dict[str, tuple[int, str | None]] = {
            str(row["regra_id"]): (
                int(row["qtd"]),
                inv_rank.get(int(row["sev_rank"])) if row["sev_rank"] else None,
            )
            for _, row in counts.iterrows()
        }

        for rid in regras:
            qtd, sev = by_rule.get(rid, (0, None))
            matrix.cells.append(
                HeatmapCell(
                    regra_id=rid,
                    competencia=competencia,
                    pendencias=qtd,
                    severidade_max=sev,
                )
            )

    return matrix


def rule_history(
    snapshots_dir: Path,
    siconfi: str,
    rule_id: str,
    *,
    meses: int = 6,
) -> list[HeatmapCell]:
    """Histórico de uma única regra ao longo das últimas competências.

    Reaproveita a mesma estrutura de célula do heatmap.
    """
    competencias = discover_competencias(snapshots_dir, siconfi)[-meses:]
    out: list[HeatmapCell] = []
    inv_rank = {v: k for k, v in _SEVERIDADE_RANK.items()}
    base = snapshots_dir / siconfi

    for competencia in competencias:
        try:
            df = read_snapshot(competencia, base_dir=base, label="resultado_regras")
        except SnapshotNotFoundError:
            continue
        sub = df[df["regra_id"] == rule_id] if not df.empty else df
        if sub.empty:
            out.append(
                HeatmapCell(
                    regra_id=rule_id,
                    competencia=competencia,
                    pendencias=0,
                    severidade_max=None,
                )
            )
            continue
        sev_rank_max = int(sub["severidade"].map(_SEVERIDADE_RANK).fillna(0).max())
        out.append(
            HeatmapCell(
                regra_id=rule_id,
                competencia=competencia,
                pendencias=int(len(sub)),
                severidade_max=inv_rank.get(sev_rank_max),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Conta: detalhe (saldos + IC)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContaSaldos:
    """Saldos (4 colunas principais) de uma conta em uma competência."""

    saldo_inicial_devedor: float
    saldo_inicial_credor: float
    movimento_devedor: float
    movimento_credor: float
    saldo_final_devedor: float
    saldo_final_credor: float


@dataclass(frozen=True)
class ContaDetail:
    """Detalhe agregado de uma conta para o Drawer Conta."""

    conta_contabil: str
    competencia: str
    saldos: ContaSaldos
    classificadores: dict[str, str]  # {po, fr, co, fp, dc, fs, nr, nd, ai}
    pcasp: dict[str, str] | None  # nivel/status/nat_saldo/ind_sf se PCASP carregada
    pendencias_count: int


def aggregate_conta(
    snapshots_dir: Path,
    siconfi: str,
    competencia: str,
    conta_contabil: str,
    *,
    pcasp: pd.DataFrame | None = None,
) -> ContaDetail | None:
    """Agrega saldos e classificadores de uma conta a partir do snapshot MSC.

    Args:
        snapshots_dir: raiz de snapshots.
        siconfi: ente.
        competencia: YYYY-MM.
        conta_contabil: código contábil (sem pontos, ex: ``111110200``).
        pcasp: DataFrame opcional do PCASP (load_pcasp). Se passado, devolve
            o registro como ``classificadores_pcasp``.

    Returns:
        ContaDetail ou None se a conta não existir no snapshot.
    """
    base = snapshots_dir / siconfi
    try:
        df = read_snapshot(competencia, base_dir=base, label="msc_normalizado")
    except SnapshotNotFoundError:
        return None

    if df.empty:
        return None

    sub = df[df["conta_contabil"].astype(str) == str(conta_contabil)]
    if sub.empty:
        return None

    saldos = ContaSaldos(
        saldo_inicial_devedor=float(sub["saldo_inicial_debito"].sum()),
        saldo_inicial_credor=float(sub["saldo_inicial_credito"].sum()),
        movimento_devedor=float(sub["movimento_debito"].sum()),
        movimento_credor=float(sub["movimento_credito"].sum()),
        saldo_final_devedor=float(sub["saldo_final_debito"].sum()),
        saldo_final_credor=float(sub["saldo_final_credito"].sum()),
    )

    classificadores: dict[str, str] = {}
    for col in ("po", "fp", "dc", "fs", "fr", "co", "nr", "nd", "ai"):
        if col in sub.columns:
            value = str(sub.iloc[0][col])
            if value and value.lower() != "nan":
                classificadores[col] = value

    pcasp_record: dict[str, str] | None = None
    if pcasp is not None and not pcasp.empty:
        match = pcasp[pcasp["conta_contabil"].astype(str) == str(conta_contabil)]
        if not match.empty:
            row = match.iloc[0]
            pcasp_record = {
                col: str(row[col])
                for col in ("nivel", "status", "nat_saldo", "ind_sf", "id_ic")
                if col in match.columns
            }

    pendencias_count = 0
    try:
        pend = read_snapshot(competencia, base_dir=base, label="resultado_regras")
        pendencias_count = int(
            len(pend[pend["conta_contabil"].astype(str) == str(conta_contabil)])
        )
    except SnapshotNotFoundError:
        pass

    return ContaDetail(
        conta_contabil=str(conta_contabil),
        competencia=competencia,
        saldos=saldos,
        classificadores=classificadores,
        pcasp=pcasp_record,
        pendencias_count=pendencias_count,
    )


# ---------------------------------------------------------------------------
# Listagens por prefixo de conta (Caixa, Passivos)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContaResumo:
    """Resumo de uma conta para listagens (Caixa, Passivos)."""

    conta_contabil: str
    saldo_inicial: float          # devedor − credor (positivo = saldo devedor líquido)
    saldo_final: float            # devedor − credor
    movimento_liquido: float      # mov_devedor − mov_credor
    fr: str | None                # fonte de recurso (se informada)


def accounts_by_prefix(
    snapshots_dir: Path,
    siconfi: str,
    competencia: str,
    prefixes: list[str],
    *,
    nat_saldo: str | None = None,
) -> list[ContaResumo]:
    """Lista contas cuja ``conta_contabil`` começa com algum dos prefixos.

    Agrega saldos somando todas as linhas (linhas distintas existem por IC),
    devolvendo um único registro por conta com os saldos consolidados.

    Args:
        snapshots_dir: raiz dos snapshots.
        siconfi: ente.
        competencia: YYYY-MM.
        prefixes: lista de prefixos (ex: ``["111"]`` para Caixa,
            ``["21"]`` para Passivo Circulante).
        nat_saldo: se ``"D"`` (devedora) ou ``"C"`` (credora), inverte o sinal
            de ``saldo_*`` quando a natureza for credora — útil para Passivos
            (que naturalmente têm saldo credor) aparecerem com valores positivos.
            Se None, mantém devedor−credor.

    Returns:
        Lista ordenada por conta_contabil.
    """
    base = snapshots_dir / siconfi
    try:
        df = read_snapshot(competencia, base_dir=base, label="msc_normalizado")
    except SnapshotNotFoundError:
        return []
    if df.empty:
        return []

    contas_str = df["conta_contabil"].astype(str)
    mask = pd.Series(False, index=df.index)
    for p in prefixes:
        mask = mask | contas_str.str.startswith(p)
    sub = df[mask]
    if sub.empty:
        return []

    grouped = sub.groupby("conta_contabil", as_index=False).agg(
        sid=("saldo_inicial_debito", "sum"),
        sic=("saldo_inicial_credito", "sum"),
        md=("movimento_debito", "sum"),
        mc=("movimento_credito", "sum"),
        sfd=("saldo_final_debito", "sum"),
        sfc=("saldo_final_credito", "sum"),
    )

    # FR como representativo da primeira linha (uma conta pode ter múltiplas FRs;
    # a tela trata isso como informação resumida)
    fr_by_conta: dict[str, str | None] = {}
    if "fr" in sub.columns:
        for conta, sub_grp in sub.groupby("conta_contabil"):
            frs = [
                str(v) for v in sub_grp["fr"].unique() if str(v) and str(v).lower() != "nan"
            ]
            fr_by_conta[str(conta)] = ", ".join(frs) if frs else None

    out: list[ContaResumo] = []
    sign = -1.0 if nat_saldo == "C" else 1.0
    for _, row in grouped.iterrows():
        conta = str(row["conta_contabil"])
        out.append(
            ContaResumo(
                conta_contabil=conta,
                saldo_inicial=sign * (float(row["sid"]) - float(row["sic"])),
                saldo_final=sign * (float(row["sfd"]) - float(row["sfc"])),
                movimento_liquido=sign * (float(row["md"]) - float(row["mc"])),
                fr=fr_by_conta.get(conta),
            )
        )
    return sorted(out, key=lambda r: r.conta_contabil)
