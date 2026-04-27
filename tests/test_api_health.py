"""
Testes do healthcheck e endpoints sentinela do FastAPI MCRA PMJP.

Garante que ``app.api.main`` importa o motor ranking_msc corretamente e
expõe os endpoints básicos antes que rotas de negócio sejam adicionadas.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


class TestHealthcheck:
    def test_health_retorna_200_com_status_ok(self) -> None:
        """GET /api/health responde 200 com payload mínimo esperado."""
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "app_title" in body
        assert "rules_enabled" in body

    def test_health_reflete_motor_carregado(self) -> None:
        """rules_enabled vem do settings real e deve ser numérico ≥ 0."""
        response = client.get("/api/health")
        body = response.json()
        rules_enabled = int(body["rules_enabled"])
        assert rules_enabled >= 0


class TestApiRoot:
    def test_api_root_retorna_servico_e_versao(self) -> None:
        """GET /api/ identifica o serviço (sentinel para o front)."""
        response = client.get("/api/")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "mcra-pmjp"
        assert body["version"]
