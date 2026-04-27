"""
Testes da SPA history fallback do FastAPI MCRA PMJP.

Garante que rotas client-side do React Router (ex.: /regras, /pendencias)
caem em ``index.html`` quando o ``web/dist`` está construído, e que
chamadas a ``/api/*`` inexistentes continuam retornando JSON 404.

A presença do mount StaticFiles em "/" não pode "engolir" essas rotas:
StaticFiles é uma sub-aplicação independente e sua resposta 404 não dispara
de forma confiável o ``@app.exception_handler(404)`` da aplicação principal.
Por isso o app precisa ter uma rota catch-all explícita.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import PROJECT_ROOT
from app.api.main import app

_WEB_DIST = PROJECT_ROOT / "web" / "dist"

_DIST_BUILT = _WEB_DIST.is_dir() and (_WEB_DIST / "index.html").is_file()
_REQUIRES_DIST = pytest.mark.skipif(
    not _DIST_BUILT,
    reason="web/dist não está construído (rode `cd web && npm run build`).",
)

client = TestClient(app)


@_REQUIRES_DIST
class TestSpaFallback:
    def test_deep_link_react_router_serve_index_html(self) -> None:
        """GET /regras (rota client-side) deve cair em index.html, não 404."""
        response = client.get("/regras")
        assert response.status_code == 200, (
            f"Esperado 200 (index.html) para deep link client-side, "
            f"recebido {response.status_code}. Body: {response.text[:200]!r}"
        )
        assert "text/html" in response.headers.get("content-type", "")
        assert '<div id="root"></div>' in response.text

    def test_outra_rota_client_side_serve_index_html(self) -> None:
        """GET /pendencias também deve cair em index.html."""
        response = client.get("/pendencias")
        assert response.status_code == 200
        assert '<div id="root"></div>' in response.text

    def test_rota_aninhada_serve_index_html(self) -> None:
        """Caminhos aninhados como /regras/R001 também caem no shell SPA."""
        response = client.get("/regras/R001")
        assert response.status_code == 200
        assert '<div id="root"></div>' in response.text

    def test_api_inexistente_retorna_json_404(self) -> None:
        """/api/* inexistente continua sendo 404 JSON, nunca index.html."""
        response = client.get("/api/rota-que-nao-existe")
        assert response.status_code == 404
        assert "application/json" in response.headers.get("content-type", "")
        body = response.json()
        assert "detail" in body

    def test_index_html_servido_na_raiz(self) -> None:
        """GET / serve o index.html do dist."""
        response = client.get("/")
        assert response.status_code == 200
        assert '<div id="root"></div>' in response.text

    def test_assets_continuam_servidos(self) -> None:
        """Bundles em /assets/ continuam sendo servidos pelo StaticFiles."""
        assets_dir = _WEB_DIST / "assets"
        if not assets_dir.is_dir():
            pytest.skip("dist/assets ausente.")
        first_asset = next(iter(assets_dir.iterdir()), None)
        if first_asset is None:
            pytest.skip("dist/assets vazio.")
        response = client.get(f"/assets/{first_asset.name}")
        assert response.status_code == 200
        assert response.content == first_asset.read_bytes()

    def test_path_traversal_nao_escapa_dist(self) -> None:
        """Tentativa de path traversal (../) cai no index.html sem vazar arquivo."""
        response = client.get("/..%2F..%2Fpyproject.toml")
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            assert '<div id="root"></div>' in response.text
            assert "[tool.poetry]" not in response.text
            assert "[project]" not in response.text
