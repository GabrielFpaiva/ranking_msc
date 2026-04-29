"""
app.api
~~~~~~~

Pacote FastAPI que expõe o motor ranking_msc para o frontend MCRA PMJP.

Substitui o ``app/web_app.py`` (Panel) — ver branch F0-00.

Em dev:
    uvicorn app.api.main:app --reload --port 8000

Em prod (após ``cd web && npm run build``):
    uvicorn app.api.main:app --port 8000  # serve API + StaticFiles do dist/
"""
