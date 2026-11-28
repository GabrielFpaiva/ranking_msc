"""Testes da regra R054 — Saldo Inicial do mês N = Saldo Final do mês N-1."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from ranking_msc.config.settings import PathsSettings, Settings
from ranking_msc.engine.executor import EngineContext
from ranking_msc.exceptions import SnapshotError
from ranking_msc.outputs.snapshot import write_snapshot_atomic
from ranking_msc.rules.r054 import R054, _prev_competencia

# ---------------------------------------------------------------------------
# Helpers de construção de DataFrames
# ---------------------------------------------------------------------------


def _df_mes_n(
    conta: str,
    si_d: float,
    si_c: float,
    po: str = "",
    fr: str = "",
) -> pd.DataFrame:
    """Cria DataFrame mínimo do mês N para teste de R054."""
    return pd.DataFrame({
        "conta_contabil": [conta],
        "po": [po],
        "fr": [fr],
        "saldo_inicial_debito": [si_d],
        "saldo_inicial_credito": [si_c],
        "saldo_final_debito": [0.0],
        "saldo_final_credito": [0.0],
        "movimento_debito": [0.0],
        "movimento_credito": [0.0],
    })


def _df_mes_anterior(
    conta: str,
    sf_d: float,
    sf_c: float,
    po: str = "",
    fr: str = "",
) -> pd.DataFrame:
    """Cria DataFrame mínimo do mês N-1 para salvar como snapshot."""
    return pd.DataFrame({
        "conta_contabil": [conta],
        "po": [po],
        "fr": [fr],
        "saldo_inicial_debito": [0.0],
        "saldo_inicial_credito": [0.0],
        "saldo_final_debito": [sf_d],
        "saldo_final_credito": [sf_c],
        "movimento_debito": [0.0],
        "movimento_credito": [0.0],
    })


def _make_context(tmp_path: Path, competencia: str = "2024-02") -> EngineContext:
    """Cria EngineContext apontando snapshots_dir para tmp_path."""
    paths = PathsSettings(
        data_dir=str(tmp_path),
        snapshots_dir=str(tmp_path),
        reports_dir=str(tmp_path / "reports"),
        logs_dir=str(tmp_path / "logs"),
        ref_dir=str(tmp_path / "ref"),
    )
    settings = Settings(paths=paths)
    return EngineContext(
        competencia=competencia,
        siconfi="250400",
        settings=settings,
        usuario="teste",
    )


_SICONFI_TESTE = "250400"


def _salvar_snapshot_anterior(
    df: pd.DataFrame,
    tmp_path: Path,
    competencia: str = "2024-02",
) -> None:
    """Salva df como snapshot msc_normalizado do mês anterior a competencia.

    Usa o mesmo siconfi de _make_context para que R054 encontre o arquivo.
    """
    prev = _prev_competencia(competencia)
    write_snapshot_atomic(
        df, prev, base_dir=str(tmp_path / _SICONFI_TESTE), label="msc_normalizado"
    )


# ---------------------------------------------------------------------------
# Testes unitários de _prev_competencia
# ---------------------------------------------------------------------------


class TestPrevCompetencia:
    def test_mes_comum_retorna_mes_anterior(self) -> None:
        """Mês comum retorna mês -1 no mesmo ano."""
        assert _prev_competencia("2024-06") == "2024-05"

    def test_janeiro_retorna_dezembro_do_ano_anterior(self) -> None:
        """Janeiro de qualquer ano retorna dezembro do ano anterior."""
        assert _prev_competencia("2024-01") == "2023-12"

    def test_dezembro_retorna_novembro(self) -> None:
        """Dezembro retorna novembro."""
        assert _prev_competencia("2024-12") == "2024-11"

    def test_formato_dois_digitos_mes(self) -> None:
        """Mês deve ter dois dígitos no retorno."""
        assert _prev_competencia("2024-10") == "2024-09"


# ---------------------------------------------------------------------------
# Testes da regra R054
# ---------------------------------------------------------------------------


class TestR054:
    def test_sem_snapshot_anterior_retorna_vazio(self, tmp_path: Path) -> None:
        """Quando não há snapshot do mês anterior, retorna DataFrame vazio sem ALERTA."""
        context = _make_context(tmp_path, competencia="2024-02")
        # Nenhum snapshot salvo em tmp_path
        df_n = _df_mes_n("111110200", si_d=1000.0, si_c=0.0)

        result = R054().execute(df_n, context)

        assert len(result) == 0

    def test_si_igual_sf_anterior_sem_pendencia(self, tmp_path: Path) -> None:
        """SI_liq do mês N == SF_liq do mês N-1 → nenhum ALERTA."""
        context = _make_context(tmp_path, competencia="2024-02")
        df_prev = _df_mes_anterior("111110200", sf_d=1000.0, sf_c=0.0)
        _salvar_snapshot_anterior(df_prev, tmp_path, competencia="2024-02")

        df_n = _df_mes_n("111110200", si_d=1000.0, si_c=0.0)
        result = R054().execute(df_n, context)

        assert len(result) == 0

    def test_si_diferente_sf_anterior_gera_alerta(self, tmp_path: Path) -> None:
        """SI_liq do mês N != SF_liq do mês N-1 → ALERTA com campos corretos."""
        context = _make_context(tmp_path, competencia="2024-02")
        # SF anterior = 1000; SI atual = 2000 → diferença = 1000
        df_prev = _df_mes_anterior("111110200", sf_d=1000.0, sf_c=0.0)
        _salvar_snapshot_anterior(df_prev, tmp_path, competencia="2024-02")

        df_n = _df_mes_n("111110200", si_d=2000.0, si_c=0.0)
        result = R054().execute(df_n, context)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["severidade"] == "ALERTA"
        assert row["regra_id"] == "R054"
        assert row["conta_contabil"] == "111110200"
        assert row["competencia"] == "2024-02"
        assert "111110200" in row["descricao"]
        assert "1000.00" in row["valor_esperado"]  # SF anterior
        assert "2000.00" in row["valor_encontrado"]  # SI atual

    def test_diferenca_dentro_da_tolerancia_sem_alerta(self, tmp_path: Path) -> None:
        """Diferença <= 0.01 (TOLERANCIA_CENTAVO) não gera ALERTA."""
        context = _make_context(tmp_path, competencia="2024-02")
        # SF anterior = 1000.00; SI atual = 1000.005 → diferença = 0.005 < 0.01
        df_prev = _df_mes_anterior("111110200", sf_d=1000.0, sf_c=0.0)
        _salvar_snapshot_anterior(df_prev, tmp_path, competencia="2024-02")

        df_n = _df_mes_n("111110200", si_d=1000.005, si_c=0.0)
        result = R054().execute(df_n, context)

        assert len(result) == 0

    def test_combo_ausente_no_snapshot_nao_gera_alerta(self, tmp_path: Path) -> None:
        """Combo presente no mês N mas ausente no mês N-1 não gera ALERTA (inner join)."""
        context = _make_context(tmp_path, competencia="2024-02")
        # Snapshot anterior só tem conta 211000000
        df_prev = _df_mes_anterior("211000000", sf_d=500.0, sf_c=0.0)
        _salvar_snapshot_anterior(df_prev, tmp_path, competencia="2024-02")

        # Mês N só tem conta 111110200 (nova) — não existe no snapshot anterior
        df_n = _df_mes_n("111110200", si_d=1000.0, si_c=0.0)
        result = R054().execute(df_n, context)

        assert len(result) == 0

    def test_multiplos_combos_divergentes(self, tmp_path: Path) -> None:
        """Múltiplos combos divergentes geram múltiplas linhas de ALERTA."""
        context = _make_context(tmp_path, competencia="2024-02")
        df_prev = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000"],
            "po": ["", ""],
            "fr": ["", ""],
            "saldo_inicial_debito": [0.0, 0.0],
            "saldo_inicial_credito": [0.0, 0.0],
            "saldo_final_debito": [1000.0, 500.0],
            "saldo_final_credito": [0.0, 0.0],
            "movimento_debito": [0.0, 0.0],
            "movimento_credito": [0.0, 0.0],
        })
        _salvar_snapshot_anterior(df_prev, tmp_path, competencia="2024-02")

        df_n = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000"],
            "po": ["", ""],
            "fr": ["", ""],
            "saldo_inicial_debito": [2000.0, 900.0],  # ambas divergem do anterior
            "saldo_inicial_credito": [0.0, 0.0],
            "saldo_final_debito": [0.0, 0.0],
            "saldo_final_credito": [0.0, 0.0],
            "movimento_debito": [0.0, 0.0],
            "movimento_credito": [0.0, 0.0],
        })
        result = R054().execute(df_n, context)

        assert len(result) == 2
        assert all(row["severidade"] == "ALERTA" for _, row in result.iterrows())

    def test_agrega_linhas_antes_de_comparar(self, tmp_path: Path) -> None:
        """Duas linhas do mesmo combo somadas antes de comparar — sem falso ALERTA.

        SI_D_total = 600 + 400 = 1000; SI_C = 0 → SI_liq = 1000
        SF anterior: SF_D = 1000; SF_C = 0 → SF_liq = 1000
        Diferença = 0 → sem ALERTA.
        """
        context = _make_context(tmp_path, competencia="2024-02")
        df_prev = _df_mes_anterior("111110200", sf_d=1000.0, sf_c=0.0, po="10131", fr="1500")
        _salvar_snapshot_anterior(df_prev, tmp_path, competencia="2024-02")

        # Mesmo combo em 2 linhas — deve agregar antes de comparar
        df_n = pd.DataFrame({
            "conta_contabil": ["111110200", "111110200"],
            "po": ["10131", "10131"],
            "fr": ["1500", "1500"],
            "saldo_inicial_debito": [600.0, 400.0],   # total = 1000
            "saldo_inicial_credito": [0.0, 0.0],
            "saldo_final_debito": [0.0, 0.0],
            "saldo_final_credito": [0.0, 0.0],
            "movimento_debito": [0.0, 0.0],
            "movimento_credito": [0.0, 0.0],
        })
        result = R054().execute(df_n, context)

        assert len(result) == 0

    def test_janeiro_le_snapshot_de_dezembro_anterior(self, tmp_path: Path) -> None:
        """Competência Janeiro lê snapshot de Dezembro do ano anterior."""
        context = _make_context(tmp_path, competencia="2024-01")
        df_prev = _df_mes_anterior("111110200", sf_d=800.0, sf_c=0.0)
        # Salva como snapshot de 2023-12, namespaceado pelo siconfi do context
        write_snapshot_atomic(
            df_prev, "2023-12", base_dir=str(tmp_path / _SICONFI_TESTE), label="msc_normalizado"
        )

        df_n = _df_mes_n("111110200", si_d=800.0, si_c=0.0)
        result = R054().execute(df_n, context)

        assert len(result) == 0

    def test_severidade_nunca_e_erro(self, tmp_path: Path) -> None:
        """R054 nunca gera pendência com severidade ERRO — apenas ALERTA."""
        context = _make_context(tmp_path, competencia="2024-02")
        df_prev = _df_mes_anterior("111110200", sf_d=100.0, sf_c=0.0)
        _salvar_snapshot_anterior(df_prev, tmp_path, competencia="2024-02")

        df_n = _df_mes_n("111110200", si_d=9999.0, si_c=0.0)
        result = R054().execute(df_n, context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["severidade"] != "ERRO"

    def test_df_mes_n_vazio_retorna_vazio(self, tmp_path: Path) -> None:
        """DataFrame do mês N vazio retorna vazio sem erro."""
        context = _make_context(tmp_path, competencia="2024-02")
        df_prev = _df_mes_anterior("111110200", sf_d=1000.0, sf_c=0.0)
        _salvar_snapshot_anterior(df_prev, tmp_path, competencia="2024-02")

        df_n = pd.DataFrame(columns=[
            "conta_contabil", "saldo_inicial_debito", "saldo_inicial_credito",
            "saldo_final_debito", "saldo_final_credito",
        ])
        result = R054().execute(df_n, context)

        assert len(result) == 0

    def test_snapshot_anterior_sem_coluna_ic_usa_intersecao(self, tmp_path: Path) -> None:
        """Snapshot anterior com menos colunas IC que o mês N — inner join usa interseção.

        Mês N tem 'po' e 'fr'; snapshot só tem 'po'.
        A chave de join deve ser apenas ['conta_contabil', 'po'] — sem fan-out.
        SI_liq = 1000; SF_liq = 1000 → sem ALERTA.
        """
        context = _make_context(tmp_path, competencia="2024-02")
        # Snapshot do mês anterior sem coluna 'fr'
        df_prev = pd.DataFrame({
            "conta_contabil": ["111110200"],
            "po": ["10131"],
            "saldo_final_debito": [1000.0],
            "saldo_final_credito": [0.0],
        })
        write_snapshot_atomic(
            df_prev, "2024-01", base_dir=str(tmp_path / _SICONFI_TESTE), label="msc_normalizado"
        )

        df_n = pd.DataFrame({
            "conta_contabil": ["111110200"],
            "po": ["10131"],
            "fr": ["1500"],
            "saldo_inicial_debito": [1000.0],
            "saldo_inicial_credito": [0.0],
            "saldo_final_debito": [0.0],
            "saldo_final_credito": [0.0],
        })
        result = R054().execute(df_n, context)

        assert len(result) == 0

    def test_snapshots_dir_do_context_tem_precedencia_sobre_settings(
        self, tmp_path: Path
    ) -> None:
        """context.snapshots_dir é usado em vez de settings.paths.snapshots_dir.

        Cenário: settings aponta para diretório vazio; snapshots reais estão
        em outro diretório passado via context.snapshots_dir (ex: --output-dir).
        R054 deve encontrar o snapshot no diretório correto e gerar ALERTA.
        """
        settings_dir = tmp_path / "settings_dir"
        real_dir = tmp_path / "real_dir"
        settings_dir.mkdir()
        real_dir.mkdir()

        # Snapshot só existe em real_dir/<siconfi>; settings_dir está vazio
        df_prev = _df_mes_anterior("111110200", sf_d=1000.0, sf_c=0.0)
        write_snapshot_atomic(
            df_prev, "2024-01", base_dir=str(real_dir / _SICONFI_TESTE), label="msc_normalizado"
        )

        # Context com snapshots_dir apontando para real_dir,
        # mas settings.paths.snapshots_dir apontando para settings_dir (vazio)
        paths = PathsSettings(
            data_dir=str(tmp_path),
            snapshots_dir=str(settings_dir),
            reports_dir=str(tmp_path / "reports"),
            logs_dir=str(tmp_path / "logs"),
            ref_dir=str(tmp_path / "ref"),
        )
        settings = Settings(paths=paths)
        context = EngineContext(
            competencia="2024-02",
            siconfi="250400",
            settings=settings,
            snapshots_dir=real_dir,
            usuario="teste",
        )

        df_n = _df_mes_n("111110200", si_d=9999.0, si_c=0.0)
        result = R054().execute(df_n, context)

        # Deve encontrar o snapshot e detectar a divergência
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"

    def test_erro_io_ao_ler_snapshot_propaga_snapshot_error(
        self, tmp_path: Path
    ) -> None:
        """SnapshotError de I/O propaga — não é tratado como ausência de snapshot.

        Garante que falhas operacionais (permissão, Parquet corrompido) não
        sejam silenciadas como se o snapshot simplesmente não existisse.
        """
        context = _make_context(tmp_path, competencia="2024-02")
        df_n = _df_mes_n("111110200", si_d=1000.0, si_c=0.0)

        # Simula falha de I/O: read_snapshot levanta SnapshotError (não NotFound)
        io_error = SnapshotError("Falha de permissão ao ler arquivo Parquet")
        with patch(
            "ranking_msc.io.store.ParquetStore.load_msc",
            side_effect=io_error,
        ):
            with pytest.raises(SnapshotError):
                R054().execute(df_n, context)
