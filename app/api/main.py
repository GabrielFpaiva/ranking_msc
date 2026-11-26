"""
app.api.main
~~~~~~~~~~~~

Aplicação FastAPI que serve o motor ranking_msc para o frontend MCRA PMJP.

Em dev: uvicorn app.api.main:app --reload --port 8000  (frontend Vite no :5173)
Em prod: build do front é servido como StaticFiles em /
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.deps import PROJECT_ROOT, absolute_uso_dir, get_logger, get_settings
from app.api.routes import auth as auth_routes
from app.api.routes import caixa as caixa_routes
from app.api.routes import compare as compare_routes
from app.api.routes import competencias as competencias_routes
from app.api.routes import contas as contas_routes
from app.api.routes import entregas as entregas_routes
from app.api.routes import exports as exports_routes
from app.api.routes import invites as invites_routes
from app.api.routes import log as log_routes
from app.api.routes import passivos as passivos_routes
from app.api.routes import pendencias as pendencias_routes
from app.api.routes import recommendations as recommendations_routes
from app.api.routes import rules as rules_routes
from app.api.routes import run as run_routes
from app.api.routes import score as score_routes
from app.api.routes import summary as summary_routes
from app.api.routes import superavit as superavit_routes
from app.api.routes import uso as uso_routes
from app.api.uso_store import (
    ACUMULADOR,
    LOCK_USO,
    compactar_meses_pendentes,
    dia_local,
    escrever_flush,
    limpar_cache,
)

INTERVALO_FLUSH_S = 300


def _flush_agora() -> None:
    """Drena o acumulador para o disco e compacta meses fechados.

    ``ano_mes_corrente`` é lido do relógio **uma única vez, aqui em cima,
    antes de ``ACUMULADOR.drenar()``** — não depois da escrita. Uma revisão
    de código pegou o caso de ler o relógio de novo depois do flush: isso
    abre uma corrida na virada do mês, em que um heartbeat concorrente
    calcula seu próprio `dia_local()` depois deste flush já ter drenado o
    buffer mas antes da meia-noite real (se marcando com `2026-09-30`),
    enquanto a segunda leitura do relógio deste flush já cruzou para
    outubro. O retardatário seria então gravado, no próximo ciclo, num
    `2026-09.jsonl` novo ao lado do `2026-09.agg.jsonl` já existente — que
    `_caminho_mes` nunca lê (o compactado tem precedência) e que a próxima
    varredura de compactação apaga como lixo de crash. Dado perdido em
    silêncio. Uma única leitura do relógio, antes de drenar, fecha essa
    janela por completo.

    A ordem escrever → compactar também importa: deltas gravados perto da
    virada do mês precisam chegar ao disco antes que a compactação dobre
    aquele mês em `.agg.jsonl`.
    """
    with LOCK_USO:
        ano_mes_corrente = dia_local()[:7]
        uso_dir = absolute_uso_dir()
        pendentes = ACUMULADOR.drenar()
        try:
            for mes in sorted({chave.dia[:7] for chave in pendentes}):
                lote = {
                    chave: tempo for chave, tempo in pendentes.items() if chave.dia[:7] == mes
                }
                escrever_flush(uso_dir, lote)
                for chave in lote:
                    pendentes.pop(chave, None)
            compactar_meses_pendentes(uso_dir, ano_mes_corrente)
        except OSError:
            ACUMULADOR.restaurar(pendentes)
            raise
        finally:
            # Mesmo com uma falha após a escrita, o cache fechado pode ter
            # ficado obsoleto; nunca sirva a cópia anterior.
            limpar_cache()


async def _loop_flush() -> None:
    """Dispara ``_flush_agora()`` a cada ``INTERVALO_FLUSH_S`` segundos."""
    while True:
        await asyncio.sleep(INTERVALO_FLUSH_S)
        try:
            await asyncio.to_thread(_flush_agora)
        except OSError:
            get_logger().error("Falha ao gravar tempo de uso", exc_info=True)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Sobe o loop de flush e garante uma última gravação no shutdown."""
    tarefa = asyncio.create_task(_loop_flush())
    try:
        yield
    finally:
        tarefa.cancel()
        with suppress(asyncio.CancelledError):
            await tarefa
        await asyncio.to_thread(_flush_agora)


app = FastAPI(
    title="MCRA PMJP API",
    description="API que expõe o motor ranking_msc para o frontend MCRA.",
    version="0.1.2",
    lifespan=lifespan,
)

app.include_router(auth_routes.router)
app.include_router(invites_routes.public_router)
app.include_router(invites_routes.router)
app.include_router(run_routes.router)
app.include_router(competencias_routes.router)
app.include_router(score_routes.router)
app.include_router(summary_routes.router)
app.include_router(pendencias_routes.router)
app.include_router(rules_routes.router)
app.include_router(contas_routes.router)
app.include_router(caixa_routes.router)
app.include_router(passivos_routes.router)
app.include_router(superavit_routes.router)
app.include_router(compare_routes.router)
app.include_router(exports_routes.router)
app.include_router(recommendations_routes.router)
app.include_router(log_routes.router)
app.include_router(entregas_routes.router)
app.include_router(uso_routes.router)

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


# Em prod (após `cd web && npm run build`), o mesmo processo serve API + SPA.
# Em dev o Vite serve o front no :5173, então este bloco só ativa quando o
# build existe. /assets/* fica no StaticFiles (bundles hashados, cacheáveis);
# todo o resto vai pra um catch-all que serve arquivos do dist quando existem
# e cai em index.html caso contrário, deixando o React Router resolver a rota.
# Importante: NÃO usar app.mount("/", StaticFiles(...)) + exception_handler(404),
# porque o StaticFiles montado em "/" vira sub-app e seu 404 não dispara de
# forma confiável o handler global do app principal (Starlette/uvicorn).
_WEB_DIST: Path = PROJECT_ROOT / "web" / "dist"
if _WEB_DIST.is_dir():
    _INDEX_HTML = (_WEB_DIST / "index.html").read_text(encoding="utf-8")
    _WEB_DIST_RESOLVED = _WEB_DIST.resolve()

    _ASSETS_DIR = _WEB_DIST / "assets"
    if _ASSETS_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def spa_catchall(full_path: str) -> FileResponse | HTMLResponse | JSONResponse:
        """Catch-all explícito para SPA history fallback.

        Convenções:
        * ``/api/*`` não casado pelos routers retorna JSON 404 (mantém o
          contrato com o frontend, que espera JSON nas chamadas de API).
        * Demais caminhos tentam servir um arquivo físico do dist (favicon,
          robots.txt, manifest...) e, se não existir, devolvem o
          ``index.html`` para o React Router cuidar da rota client-side.
        * Tentativas de path traversal (``../``) caem no index.html.
        """
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(content={"detail": "Not Found"}, status_code=404)

        if full_path:
            candidate = (_WEB_DIST / full_path).resolve()
            try:
                candidate.relative_to(_WEB_DIST_RESOLVED)
            except ValueError:
                return HTMLResponse(content=_INDEX_HTML, status_code=200)
            if candidate.is_file():
                return FileResponse(candidate)

        return HTMLResponse(content=_INDEX_HTML, status_code=200)
