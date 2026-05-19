"""
Testes dos endpoints de listagem de contas (Caixa, Passivos, Superávit) — fatia D.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api import deps as api_deps
from app.api.main import app
from fastapi.testclient import TestClient

from tests.conftest import _build_msc_csv_bytes  # type: ignore[attr-defined]


def _csv_with_caixa_and_passivos() -> bytes:
    """Gera CSV com contas em vários prefixos (1.1.1, 2.1, 2.2)."""
    rows = [
        # Caixa (111)
        ["111110200", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
         "1000.00", "beginning_balance", "D"],
        ["111110200", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
         "200.00", "period_change", "D"],
        ["111110200", "10131", "PO", "1", "FP", "1500", "FR", "", "", "", "", "", "",
         "1200.00", "ending_balance", "D"],
        # Passivo Circulante (21)
        ["210000000", "10131", "PO", "2", "FP", "1500", "FR", "", "", "", "", "", "",
         "500.00", "beginning_balance", "C"],
        ["210000000", "10131", "PO", "2", "FP", "1500", "FR", "", "", "", "", "", "",
         "100.00", "period_change", "C"],
        ["210000000", "10131", "PO", "2", "FP", "1500", "FR", "", "", "", "", "", "",
         "600.00", "ending_balance", "C"],
        # Passivo Não-Circulante (22)
        ["220000000", "10131", "PO", "2", "FP", "1500", "FR", "", "", "", "", "", "",
         "300.00", "beginning_balance", "C"],
        ["220000000", "10131", "PO", "2", "FP", "1500", "FR", "", "", "", "", "", "",
         "300.00", "ending_balance", "C"],
    ]
    return _build_msc_csv_bytes(rows=rows)


@pytest.fixture
def populated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[str, str]]:
    """Roda /api/run com CSV multi-prefixo e devolve (siconfi, competencia)."""
    snapshots = tmp_path / "snapshots"
    reports = tmp_path / "reports"
    snapshots.mkdir()
    reports.mkdir()

    monkeypatch.setattr(api_deps, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(api_deps, "absolute_reports_dir", lambda: reports)
    from app.api.routes import caixa as caixa_module
    from app.api.routes import passivos as passivos_module
    from app.api.routes import run as run_module

    for module in (run_module, caixa_module, passivos_module):
        monkeypatch.setattr(module, "absolute_snapshots_dir", lambda: snapshots)
    monkeypatch.setattr(run_module, "absolute_reports_dir", lambda: reports)

    client = TestClient(app)
    response = client.post(
        "/api/run",
        files={"file": ("msc.csv", _csv_with_caixa_and_passivos(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    yield body["siconfi"], body["competencia"]


class TestCaixa:
    def test_caixa_retorna_contas_com_prefixo_111(self, populated: tuple[str, str]) -> None:
        siconfi, competencia = populated
        client = TestClient(app)
        response = client.get(
            "/api/caixa", params={"siconfi": siconfi, "competencia": competencia}
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["groups"]) == 1
        group = body["groups"][0]
        assert group["label"] == "Caixa e Equivalentes"
        contas = [it["conta_contabil"] for it in group["items"]]
        assert "111110200" in contas
        assert all(c.startswith("111") for c in contas)


class TestPassivos:
    def test_passivos_separa_circ_e_nao_circ(self, populated: tuple[str, str]) -> None:
        siconfi, competencia = populated
        client = TestClient(app)
        response = client.get(
            "/api/passivos", params={"siconfi": siconfi, "competencia": competencia}
        )
        assert response.status_code == 200
        body = response.json()
        labels = [g["label"] for g in body["groups"]]
        assert "Passivo Circulante" in labels
        assert "Passivo Não-Circulante" in labels

    def test_passivos_inverte_sinal_para_natureza_credora(
        self, populated: tuple[str, str]
    ) -> None:
        """Passivo é credor por natureza — saldo apresentado positivo."""
        siconfi, competencia = populated
        client = TestClient(app)
        response = client.get(
            "/api/passivos", params={"siconfi": siconfi, "competencia": competencia}
        )
        body = response.json()
        circ = next(g for g in body["groups"] if g["label"] == "Passivo Circulante")
        if circ["items"]:
            assert circ["items"][0]["saldo_final"] > 0


class TestSuperavit:
    def test_superavit_retorna_payload_informativo_com_referencia_a_task(
        self, populated: tuple[str, str]
    ) -> None:
        siconfi, competencia = populated
        client = TestClient(app)
        response = client.get(
            "/api/superavit", params={"siconfi": siconfi, "competencia": competencia}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "not_implemented"
        assert body["see"] == "F0-04"
