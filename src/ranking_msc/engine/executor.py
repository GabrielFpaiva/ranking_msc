"""
ranking_msc.engine.executor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Motor principal de execução das regras de validação.

Fluxo futuro (a ser implementado):
    1. Receber DataFrame MSC já lido e normalizado.
    2. Montar EngineContext com metadados (competência, siconfi, settings).
    3. Carregar regras habilitadas (settings.rules.enabled) via RULE_REGISTRY.
    4. Executar cada regra em sequência (ou paralelo controlado).
    5. Consolidar pendências em um único DataFrame.
    6. Calcular scoring / nota final.
    7. Retornar EngineResult com pendências, logs e estatísticas.

Concorrência (multiusuário):
    - Cada execução recebe um ``execucao_id`` (UUID) para rastreabilidade.
    - TODO: implementar semáforo por competência para evitar que dois
      usuários processem o mesmo mês simultaneamente (ver SecuritySettings).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from ranking_msc.config.settings import Settings
from ranking_msc.rules.base import RULE_REGISTRY, Rule
from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS


@dataclass
class EngineContext:
    """Metadados de uma execução do motor.

    Criado pelo chamador (web_app ou script) e passado para cada regra.
    """
    competencia: str                  # "YYYY-MM"
    siconfi: str                      # código do ente
    settings: Settings
    execucao_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    usuario: str = "sistema"          # quem disparou a execução
    inicio: datetime = field(default_factory=datetime.now)

    # TODO (multiusuário): adicionar campo ``lock_token`` para controle
    # de concorrência por competência.


@dataclass
class EngineResult:
    """Resultado consolidado de uma execução do motor."""
    context: EngineContext
    pendencias: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS)
    )
    regras_executadas: int = 0
    regras_com_erro: int = 0
    erros: list[dict[str, Any]] = field(default_factory=list)
    fim: datetime = field(default_factory=datetime.now)

    @property
    def status(self) -> str:
        if self.regras_com_erro > 0:
            return "PARCIAL"
        return "OK"

    @property
    def total_pendencias(self) -> int:
        return len(self.pendencias)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def run_engine(df: pd.DataFrame, context: EngineContext) -> EngineResult:
    """Executa todas as regras habilitadas sobre o DataFrame MSC.

    Args:
        df: DataFrame com colunas de FACT_MSC_COLUMNS (já normalizado).
        context: metadados da execução.

    Returns:
        EngineResult com pendências consolidadas.

    Raises:
        NotImplementedError: stub — lógica ainda não implementada.

    Fluxo futuro (passo a passo):
        1. Filtrar regras habilitadas em context.settings.rules.enabled.
        2. Instanciar cada regra via RULE_REGISTRY[rule_id]().
        3. Para cada regra:
           a. Chamar rule.execute(df, context)
           b. Coletar DataFrame de pendências
           c. Em caso de erro, logar e decidir se continua (fail_fast?)
        4. Concatenar todas as pendências.
        5. (Opcional) Calcular scoring/nota.
        6. Preencher EngineResult e retornar.
    """
    # --- STUB: substituir pelo fluxo acima ---
    raise NotImplementedError(
        "run_engine() ainda não implementado. "
        "Consulte os comentários neste arquivo para o fluxo esperado."
    )
