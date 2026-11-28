#!/usr/bin/env python3
"""CLI que aplica as migrações SQL pendentes no Postgres (Supabase).

Uso:
    DATABASE_URL=postgresql://... python scripts/db_migrate.py
    python scripts/db_migrate.py --config config/settings.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from ranking_msc.config.settings import load_settings  # noqa: E402
from ranking_msc.exceptions import RankingMSCError  # noqa: E402
from ranking_msc.io.db import apply_migrations, connect  # noqa: E402

logger = logging.getLogger("ranking_msc")


def main(argv: list[str] | None = None) -> int:
    """Conecta no banco da configuração e aplica as migrações que faltam."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", help="caminho do settings.yaml")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        settings = load_settings(args.config)
        with connect(settings.database.url) as conn:
            novas = apply_migrations(conn)
    except RankingMSCError as exc:
        logger.error("%s", exc)
        return 1
    logger.info("Migrações aplicadas: %s", ", ".join(novas) if novas else "nenhuma (já em dia)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
