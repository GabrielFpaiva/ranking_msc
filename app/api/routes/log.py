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


def reverse_readline(filename: Path, buf_size: int = 8192):
    """A generator that returns the lines of a file in reverse order."""
    with filename.open("rb") as fh:
        fh.seek(0, 2)  # os.SEEK_END
        segment = None
        offset = 0
        file_size = remaining_size = fh.tell()
        while remaining_size > 0:
            offset = min(file_size, offset + buf_size)
            fh.seek(file_size - offset)
            buffer = fh.read(min(remaining_size, buf_size))
            remaining_size -= buf_size
            lines = buffer.split(b'\n')
            if segment is not None:
                lines[-1] += segment
            segment = lines[0]
            for index in range(len(lines) - 1, 0, -1):
                if lines[index]:
                    yield lines[index].decode('utf-8', errors='replace')
        if segment is not None and segment:
            yield segment.decode('utf-8', errors='replace')


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

    items = []
    for line in reverse_readline(log_path):
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
            
        items.append(
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
        if len(items) >= limit:
            break

    # We read backwards, so the items are newest first. We can reverse them
    # to maintain chronological order from top to bottom if desired, or leave it.
    # Usually log viewers expect chronological, but tail often just returns the newest at the bottom.
    items.reverse()

    return LogPageOut(total=len(items), items=items)
