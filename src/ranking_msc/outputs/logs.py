"""
ranking_msc.outputs.logs
~~~~~~~~~~~~~~~~~~~~~~~~~

Configuração de logging estruturado (JSON Lines) para o projeto.

Padrão recomendado:
    - Console: mensagens legíveis (nível INFO+) durante desenvolvimento.
    - Arquivo: JSON Lines (nível DEBUG+) para análise posterior.
      Cada linha é um JSON com campos padronizados, facilitando grep/jq.

Arquivo de log: data/logs/ranking_msc.jsonl
    Formato por linha:
    {"ts": "2024-01-15T10:30:00", "level": "INFO", "execucao_id": "abc-123",
     "competencia": "2024-01", "msg": "Regra R082 executada", ...}

Uso no servidor (multiusuário):
    - O logger do Python é thread-safe por padrão.
    - Cada execução inclui ``execucao_id`` no log para rastreabilidade.
    - O arquivo .jsonl é append-only, sem risco de conflito de escrita.
    - Para rotação: usar RotatingFileHandler ou logrotate externo.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# JSON Formatter para arquivos
# ---------------------------------------------------------------------------

class JSONLineFormatter(logging.Formatter):
    """Formatter que emite cada registro como uma linha JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Campos extras injetados via logging.info("msg", extra={...})
        for key in ("execucao_id", "competencia", "siconfi", "regra_id", "usuario"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])

        return json.dumps(log_entry, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Setup principal
# ---------------------------------------------------------------------------

def setup_logging(
    *,
    log_dir: str | Path = "data/logs",
    log_file: str = "ranking_msc.jsonl",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> logging.Logger:
    """Configura o logger raiz do projeto.

    Deve ser chamado UMA VEZ no início da aplicação (web_app.py ou main).

    Args:
        log_dir: diretório para o arquivo de log.
        log_file: nome do arquivo (JSON Lines).
        console_level: nível mínimo no console.
        file_level: nível mínimo no arquivo.

    Returns:
        Logger configurado (``ranking_msc``).
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("ranking_msc")
    logger.setLevel(logging.DEBUG)

    # Evita handlers duplicados se chamado mais de uma vez
    if logger.handlers:
        return logger

    # Handler: console (legível)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(console_level)
    console.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(console)

    # Handler: arquivo JSON Lines
    file_handler = logging.FileHandler(
        log_path / log_file, encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(JSONLineFormatter())
    logger.addHandler(file_handler)

    return logger


# ---------------------------------------------------------------------------
# Helper para log de execução
# ---------------------------------------------------------------------------

def log_execucao(
    logger: logging.Logger,
    *,
    execucao_id: str,
    competencia: str,
    status: str,
    message: str = "",
    **extra: Any,
) -> None:
    """Emite log estruturado de uma execução do motor.

    Exemplo:
        log_execucao(logger, execucao_id="abc", competencia="2024-01",
                     status="OK", message="Processamento concluído",
                     total_pendencias=42)
    """
    logger.info(
        message or f"Execução {execucao_id} — {status}",
        extra={
            "execucao_id": execucao_id,
            "competencia": competencia,
            **extra,
        },
    )
