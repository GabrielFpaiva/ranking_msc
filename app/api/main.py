"""
app.api.main
~~~~~~~~~~~~

Aplicação FastAPI que serve o motor ranking_msc para o frontend MCRA PMJP.

Em dev: uvicorn app.api.main:app --reload --port 8000  (frontend Vite no :5173)
Em prod: build do front é servido como StaticFiles em /
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.deps import PROJECT_ROOT, get_logger, get_settings
from app.api.routes import caixa as caixa_routes
from app.api.routes import compare as compare_routes
from app.api.routes import competencias as competencias_routes
from app.api.routes import contas as contas_routes
from app.api.routes import log as log_routes
from app.api.routes import passivos as passivos_routes
from app.api.routes import pendencias as pendencias_routes
from app.api.routes import ranking as ranking_routes
from app.api.routes import recommendations as recommendations_routes
from app.api.routes import rules as rules_routes
from app.api.routes import run as run_routes
from app.api.routes import score as score_routes
from app.api.routes import superavit as superavit_routes

app = FastAPI(
    title="MCRA PMJP API",
    description="API que expõe o motor ranking_msc para o frontend MCRA.",
    version="0.1.0",
)

app.include_router(run_routes.router)
app.include_router(competencias_routes.router)
app.include_router(score_routes.router)
app.include_router(pendencias_routes.router)
app.include_router(rules_routes.router)
app.include_router(contas_routes.router)
app.include_router(caixa_routes.router)
app.include_router(passivos_routes.router)
app.include_router(superavit_routes.router)
app.include_router(compare_routes.router)
app.include_router(recommendations_routes.router)
app.include_router(log_routes.router)
app.include_router(ranking_routes.router)

# CORS: liberado para dev (Vite no :5173). Em prod o front é servido pelo
# próprio FastAPI então same-origin elimina a necessidade.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/health")
def healthcheck() -> dict[str, str]:
    """Healthcheck leve — confirma que API e motor estão importáveis."""
    settings = get_settings()
    logger = get_logger()
    logger.debug("Healthcheck called")
    return {
        "status": "ok",
        "app_title": settings.app.title,
        "rules_enabled": str(len(settings.rules.enabled)),
    }


@app.get("/api/")
def api_root() -> dict[str, str]:
    """Sentinel — confirma que o prefixo /api está vivo."""
    return {"service": "mcra-pmjp", "version": app.version}


# Em prod (após `cd web && npm run build`), monta o dist/ na raiz "/" pra que
# o mesmo processo sirva API + SPA. Em dev o Vite serve o front no :5173.
_WEB_DIST: Path = PROJECT_ROOT / "web" / "dist"
if _WEB_DIST.is_dir():

    @app.exception_handler(404)
    async def _spa_fallback(_request: object, _exc: object) -> JSONResponse:
        """SPA history fallback: rotas client-side caem em index.html."""
        index = _WEB_DIST / "index.html"
        if index.is_file():
            return JSONResponse(
                content={"redirect": "/"},
                status_code=404,
            )
        return JSONResponse(content={"detail": "Not Found"}, status_code=404)

    app.mount("/", StaticFiles(directory=_WEB_DIST, html=True), name="web")
