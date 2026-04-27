"""
app.api.routes.log
~~~~~~~~~~~~~~~~~~

GET /api/log — leitura paginada do JSON Lines em ``data/logs/ranking_msc.jsonl``.

Filtros opcionais: ``execucao_id``, ``level``. Sempre retorna as últimas N linhas
(``limit``, default 200) — leitura tail para evitar I/O desnecessário em logs grandes.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from fastapi import APIRouter, Query

from app.api.deps import PROJECT_ROOT, get_settings
from app.api.schemas import LogEntryOut, LogPageOut

router = APIRouter(prefix="/api", tags=["log"])


@router.get(
    "/log",
    response_model=LogPageOut,
    summary="Tail das últimas N entradas do log JSONL",
)
def get_log(
    execucao_id: str | None = Query(None, description="Filtra por execucao_id"),
    level: str | None = Query(None, description="INFO | WARNING | ERROR"),
    limit: int = Query(200, ge=1, le=2000),
) -> LogPageOut:
    settings = get_settings()
    log_path: Path = (PROJECT_ROOT / settings.paths.logs_dir / "ranking_msc.jsonl").resolve()
    if not log_path.is_file():
        return LogPageOut(total=0, items=[])

    entries: deque[LogEntryOut] = deque(maxlen=limit)
    total = 0
    with log_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except ValueError:
                continue
            if execucao_id and payload.get("execucao_id") != execucao_id:
                continue
            if level and payload.get("level") != level:
                continue
            total += 1
            entries.append(
                LogEntryOut(
                    ts=str(payload.get("ts", "")),
                    level=str(payload.get("level", "INFO")),
                    msg=str(payload.get("msg", "")),
                    execucao_id=payload.get("execucao_id"),
                    competencia=payload.get("competencia"),
                    modulo=payload.get("modulo"),
                    regra_id=payload.get("regra_id"),
                    siconfi=payload.get("siconfi"),
                )
            )

    return LogPageOut(total=total, items=list(entries))
