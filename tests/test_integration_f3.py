"""
tests/test_integration_f3.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Teste de integração F3 — todas as regras implementadas na Fase 3.

Fluxo testado:
    CSV → read_msc_csv() → normalize_ic() → run_engine(todas_regras)
    → write_snapshot_atomic() + export_issues_excel()

Critério principal (F3-12):
    Todas as regras executam sem crash (status == "OK") em dados reais.

CSVs de entrada:
    ref/amostras/msc_2025-11.csv    — competência novembro 2025
    ref/amostras/msc_2025-12.csv    — competência dezembro 2025
    ref/amostras/msc_2026-01.csv    — competência janeiro 2026
    ref/amostras/encerramento2025.csv — encerramento de exercício 2025

Regras cobertas (24):
    R001–R005, R010–R012, R020–R032, R070, R080–R081
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path

import pytest

import ranking_msc.rules  # noqa: F401 — popula RULE_REGISTRY via __init__.py
from ranking_msc.config.settings import RulesSettings, Settings
from ranking_msc.engine.executor import EngineContext, EngineResult, run_engine
from ranking_msc.io.reader_msc import read_msc_csv
from ranking_msc.outputs.reports import export_issues_excel
from ranking_msc.outputs.snapshot import write_snapshot_atomic
from ranking_msc.rules.base import RULE_REGISTRY
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS
from ranking_msc.transform.ic_normalize import normalize_ic

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_AMOSTRAS = Path(Settings().paths.ref_dir) / "amostras"

# Snapshot das regras implementadas na Fase 3 (F3-01 a F3-12).
# Usado apenas para verificar que nenhuma regra ESPERADA está faltando.
# Não é um gate de "nenhuma regra além dessas" — novas regras são bem-vindas.
_REGRAS_F3: frozenset[str] = frozenset({
    "R001", "R002", "R003", "R004", "R005",
    "R010", "R011", "R012",
    "R020", "R021", "R022", "R023",
    "R024", "R025", "R026", "R027", "R028", "R029",
    "R030", "R031", "R032",
    "R070",
    "R080", "R081",
})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings_todas_regras() -> Settings:
    """Settings com todas as regras registradas habilitadas."""
    return dataclasses.replace(
        Settings(),
        rules=RulesSettings(enabled=sorted(RULE_REGISTRY.keys())),
    )


def _run_pipeline(csv_path: Path, tmp_path: Path) -> tuple[EngineResult, str]:
    """Executa o pipeline completo com todas as regras.

    Args:
        csv_path: arquivo CSV MSC de entrada.
        tmp_path: diretório base temporário para outputs isolados.

    Returns:
        Tupla (EngineResult, competencia).
    """
    raw = read_msc_csv(csv_path)
    df = normalize_ic(raw.df)
    context = EngineContext(
        competencia=raw.competencia,
        siconfi=raw.siconfi,
        settings=_settings_todas_regras(),
        usuario="integration_test_f3",
        pre_pivot_issues=raw.pre_pivot_issues,
    )
    result = run_engine(df, context)
    write_snapshot_atomic(
        result.pendencias,
        raw.competencia,
        base_dir=tmp_path / "snapshots",
    )
    export_issues_excel(
        result.pendencias,
        raw.competencia,
        output_dir=tmp_path / "reports",
    )
    return result, raw.competencia


# ---------------------------------------------------------------------------
# Testes: Registry
# ---------------------------------------------------------------------------


class TestRegistryCompleto:
    """Verifica integridade do RULE_REGISTRY após todos os imports da Fase 3."""

    def test_todas_regras_esperadas_estao_registradas(self) -> None:
        """Nenhuma regra implementada está faltando no RULE_REGISTRY."""
        faltando = _REGRAS_F3 - set(RULE_REGISTRY.keys())
        assert not faltando, (
            f"Regras ausentes no RULE_REGISTRY (faltou importar em __init__.py?): "
            f"{sorted(faltando)}"
        )

    def test_todas_regras_sao_instanciaveis(self) -> None:
        """Toda classe registrada pode ser instanciada sem argumentos."""
        for rule_id, cls in RULE_REGISTRY.items():
            try:
                cls()
            except Exception as exc:
                pytest.fail(f"{rule_id}: falha ao instanciar — {exc}")


# ---------------------------------------------------------------------------
# Testes: CSV reais
# ---------------------------------------------------------------------------


class TestTodasRegrasCSVReal:
    """Pipeline com dados reais de produção usando todas as 24 regras."""

    @pytest.mark.parametrize("csv_name", [
        "msc_2025-11.csv",
        "msc_2025-12.csv",
        "msc_2026-01.csv",
        "encerramento2025.csv",
    ])
    def test_pipeline_sem_crash(self, csv_name: str, tmp_path: Path) -> None:
        """Todas as regras executam sem crash em cada CSV de amostra disponível."""
        csv_path = _AMOSTRAS / csv_name
        if not csv_path.exists():
            pytest.skip(f"Amostra ausente: {csv_path}")

        result, competencia = _run_pipeline(csv_path, tmp_path)

        assert result.status == "OK", (
            f"[{csv_name}] status='{result.status}' — alguma regra levantou exceção"
        )
        assert set(FACT_RESULTADO_REGRAS_COLUMNS).issubset(result.pendencias.columns)
        assert (tmp_path / "snapshots" / competencia / "resultado_regras.parquet").exists()
        assert any((tmp_path / "reports").glob("*.xlsx"))

    def test_schema_pendencias_correto_dados_reais(self, tmp_path: Path) -> None:
        """DataFrame de pendências respeita exatamente FACT_RESULTADO_REGRAS_COLUMNS."""
        csv_path = _AMOSTRAS / "msc_2025-11.csv"
        if not csv_path.exists():
            pytest.skip(f"Amostra ausente: {csv_path}")

        result, _ = _run_pipeline(csv_path, tmp_path)

        assert list(result.pendencias.columns) == FACT_RESULTADO_REGRAS_COLUMNS, (
            f"Colunas inesperadas: {list(result.pendencias.columns)}"
        )

    def test_pendencias_tem_apenas_severidades_validas(self, tmp_path: Path) -> None:
        """Todas as pendências têm severidade ERRO, ALERTA ou INFO — nenhum valor espúrio."""
        csv_path = _AMOSTRAS / "msc_2025-11.csv"
        if not csv_path.exists():
            pytest.skip(f"Amostra ausente: {csv_path}")

        result, _ = _run_pipeline(csv_path, tmp_path)

        if result.pendencias.empty:
            pytest.skip("Nenhuma pendência gerada — não é possível validar severidades")

        invalidas = result.pendencias[
            ~result.pendencias["severidade"].isin({"ERRO", "ALERTA", "INFO"})
        ]
        assert invalidas.empty, (
            f"Pendências com severidade inválida:\n{invalidas[['regra_id', 'severidade']].head()}"
        )

    def test_todas_pendencias_tem_regra_id_valido(self, tmp_path: Path) -> None:
        """Toda pendência gerada tem regra_id presente no RULE_REGISTRY."""
        csv_path = _AMOSTRAS / "msc_2025-11.csv"
        if not csv_path.exists():
            pytest.skip(f"Amostra ausente: {csv_path}")

        result, _ = _run_pipeline(csv_path, tmp_path)

        if result.pendencias.empty:
            pytest.skip("Nenhuma pendência gerada")

        ids_gerados = set(result.pendencias["regra_id"].unique())
        desconhecidos = ids_gerados - set(RULE_REGISTRY.keys())
        assert not desconhecidos, (
            f"Pendências com regra_id não registrado: {desconhecidos}"
        )


# ---------------------------------------------------------------------------
# Testes: Violações sintéticas por regra-chave
# ---------------------------------------------------------------------------


class TestViolacoesSinteticas:
    """Dados sintéticos que ativam regras específicas.

    Garante que regras críticas disparam corretamente mesmo quando
    executadas em conjunto com todas as demais.
    """

    def test_r070_detecta_ic_position_swap(
        self,
        tmp_path: Path,
        build_msc_csv: Callable[..., bytes],
    ) -> None:
        """R070 detecta IC-position-swap: mesmas ICs em posições diferentes no CSV.

        Duplicatas exatas são colapsadas pelo pivot_table no reader (aggfunc='sum'),
        portanto R070 foca em linhas onde os mesmos valores de IC aparecem em
        posições distintas (IC1/TIPO1 vs IC2/TIPO2 trocados) — após normalize_ic
        produzem a mesma chave normalizada → duplicata real de negócio.
        """
        # Linha 1: IC1=10131/PO, IC2=1/FP  — beginning_balance D
        row1 = ["111110200", "10131", "PO", "1",     "FP", "1500", "FR", "", "", "", "", "", "",
                "1000.00", "beginning_balance", "D"]
        # Linha 2: IC1=1/FP,    IC2=10131/PO — ICs em posições trocadas
        # Após normalize_ic: po=10131, fp=1 em ambas → mesma chave → duplicata
        row2 = ["111110200", "1",     "FP", "10131", "PO", "1500", "FR", "", "", "", "", "", "",
                "2000.00", "beginning_balance", "D"]

        csv_bytes: bytes = build_msc_csv(rows=[row1, row2])
        csv_path = tmp_path / "MSC_2507507EX_2025-07.csv"
        csv_path.write_bytes(csv_bytes)

        result, _ = _run_pipeline(csv_path, tmp_path)

        assert result.status == "OK"
        r070 = result.pendencias[result.pendencias["regra_id"] == "R070"]
        assert len(r070) >= 1, (
            "R070 deveria detectar IC-position-swap como duplicata após normalize_ic"
        )
        assert (r070["severidade"] == "ERRO").all()

    def test_r010_conta_fora_pcasp_detectada(
        self,
        tmp_path: Path,
        build_msc_csv: Callable[..., bytes],
    ) -> None:
        """R010 detecta conta inexistente no PCASP com todas as regras ativas."""
        rows = [
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "500.00", "beginning_balance", "D"],
            ["999999999", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
             "500.00", "beginning_balance", "C"],
        ]
        csv_bytes: bytes = build_msc_csv(rows=rows)
        csv_path = tmp_path / "MSC_2507507EX_2025-08.csv"
        csv_path.write_bytes(csv_bytes)

        result, _ = _run_pipeline(csv_path, tmp_path)

        assert result.status == "OK"
        r010 = result.pendencias[result.pendencias["regra_id"] == "R010"]
        assert len(r010) >= 1, "R010 deveria detectar conta fora do PCASP"
        assert (r010["severidade"] == "ERRO").all()

    def test_dois_csvs_geram_snapshots_isolados(
        self,
        tmp_path: Path,
        build_msc_csv: Callable[..., bytes],
    ) -> None:
        """Dois CSVs de competências distintas geram snapshots independentes."""
        for mes in ("2025-05", "2025-06"):
            csv_bytes: bytes = build_msc_csv(competencia=mes)
            csv_path = tmp_path / f"MSC_2507507EX_{mes}.csv"
            csv_path.write_bytes(csv_bytes)
            _run_pipeline(csv_path, tmp_path)

        assert (tmp_path / "snapshots" / "2025-05" / "resultado_regras.parquet").exists()
        assert (tmp_path / "snapshots" / "2025-06" / "resultado_regras.parquet").exists()
