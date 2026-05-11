"""
ranking_msc.rules.base
~~~~~~~~~~~~~~~~~~~~~~

Interface base para todas as regras de validação do Ranking MSC.

Cada regra (R082 … R111) deve herdar de ``Rule`` e implementar ``execute()``.
O retorno é SEMPRE um DataFrame com as colunas definidas em
``ranking_msc.schemas.FACT_RESULTADO_REGRAS_COLUMNS``.

═══════════════════════════════════════════════════════════════
 GUIA DE EXTENSÃO — Como adicionar uma nova regra:
═══════════════════════════════════════════════════════════════

 1. Crie o arquivo  src/ranking_msc/rules/r<NNN>.py
 2. Defina uma classe que herde de Rule:

        from ranking_msc.rules.base import Rule

        class R099(Rule):
            rule_id   = "R099"
            rule_name = "Verifica saldo X contra Y"
            dimensao  = "Fechamento"

            def execute(self, df, context):
                # lógica …
                return self.build_issues(rows)

 3. Registre a regra no ``RULE_REGISTRY`` (ver final deste arquivo).
 4. Adicione "R099" na lista ``rules.enabled`` do settings.yaml.
 5. Pronto — o executor (engine/executor.py) já vai carregá-la.
═══════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

import pandas as pd

from ranking_msc.schemas import FACT_RESULTADO_REGRAS_COLUMNS

if TYPE_CHECKING:
    from ranking_msc.engine.executor import EngineContext


class Rule(ABC):
    """Classe-base abstrata para regras de validação.

    Atributos de classe obrigatórios (sobrescreva na subclasse):
        rule_id   — identificador único (ex: "R082")
        rule_name — nome curto legível
        dimensao  — "PCASP", "Fechamento", "Temporal", "Domínio", etc.
    """

    rule_id: str = ""
    rule_name: str = ""
    dimensao: str = ""
    is_scoring: ClassVar[bool] = True
    """Se False, a regra é INFO-only e não entra no cálculo de pontuação."""

    @abstractmethod
    def execute(self, df: pd.DataFrame, context: EngineContext) -> pd.DataFrame:
        """Executa a regra sobre o DataFrame MSC normalizado.

        Args:
            df: DataFrame com colunas de ``FACT_MSC_COLUMNS``.
            context: metadados da execução (competência, siconfi, settings…).

        Returns:
            DataFrame de pendências com colunas de
            ``FACT_RESULTADO_REGRAS_COLUMNS`` (pode estar vazio se não
            houver pendências).
        """
        ...

    # ------------------------------------------------------------------
    # Helpers disponíveis para todas as regras
    # ------------------------------------------------------------------

    def build_issues(
        self,
        rows: list[Any],
        *,
        extra_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Constrói DataFrame de pendências com schema padronizado.

        Preenche automaticamente ``regra_id``, ``regra_nome`` e ``dimensao``
        a partir dos atributos da classe.

        Args:
            rows: lista de dicts, cada dict representando uma pendência.
                  Deve conter ao menos: severidade, conta_contabil, descricao,
                  valor_esperado, valor_encontrado, competencia.
            extra_columns: colunas adicionais de evidência (opcionais).

        Returns:
            DataFrame padronizado.
        """
        if not rows:
            return pd.DataFrame(columns=FACT_RESULTADO_REGRAS_COLUMNS)

        df = pd.DataFrame(rows)

        # Injeta metadados da regra
        df["regra_id"] = self.rule_id
        df["regra_nome"] = self.rule_name
        df["dimensao"] = self.dimensao

        # Garante que todas as colunas obrigatórias existam
        for col in FACT_RESULTADO_REGRAS_COLUMNS:
            if col not in df.columns:
                df[col] = None

        # Reordena: obrigatórias primeiro, extras depois
        ordered = FACT_RESULTADO_REGRAS_COLUMNS + (extra_columns or [])
        ordered = [c for c in ordered if c in df.columns]
        return df[ordered]

    def __repr__(self) -> str:
        return f"<Rule {self.rule_id}: {self.rule_name}>"


# ---------------------------------------------------------------------------
# Registro global de regras
# ---------------------------------------------------------------------------
# Dicionário rule_id → classe. Cada módulo r<NNN>.py deve se registrar aqui
# (ou usar o helper ``register_rule``).
#
# Exemplo:
#     from ranking_msc.rules.base import register_rule
#     @register_rule
#     class R082(Rule): ...

# ---------------------------------------------------------------------------
# Constantes compartilhadas entre regras
# ---------------------------------------------------------------------------

TOLERANCIA_CENTAVO: float = 0.01
"""Tolerância monetária padrão (R$ 0,01) usada em comparações de saldo."""

# ---------------------------------------------------------------------------
# Helper compartilhado para validação de IC vazia
# ---------------------------------------------------------------------------

_IC_VAZIA: frozenset[str] = frozenset({"", "0", "nan"})


def ic_esta_informada(val: object) -> bool:
    """Retorna True se o valor de uma IC está preenchido (não é vazio).

    Trata None, float NaN, string vazia, "0" e "nan"/"NAN" como valores vazios.
    A comparação é case-insensitive para tolerar o uppercasing de normalize_ic.
    Compartilhado por todas as regras que validam colunas IC.

    Args:
        val: valor bruto da célula de uma coluna IC.

    Returns:
        True se a IC está informada, False caso contrário.
    """
    if val is None:
        return False
    if isinstance(val, float) and math.isnan(val):
        return False
    return str(val).strip().lower() not in _IC_VAZIA


def ic_mask_informada(series: pd.Series) -> pd.Series:
    """Versão vetorizada de ``ic_esta_informada`` — retorna mask booleana.

    Substitui ``.apply(ic_esta_informada)`` que é O(n) em Python puro.
    Usa operações vetorizadas do pandas/numpy para performance ~10-50× maior.

    Args:
        series: coluna IC do DataFrame (pode conter str, NaN, None, int).

    Returns:
        Series booleana — True onde a IC está preenchida.
    """
    s = series.fillna("").astype(str).str.strip().str.lower()
    return ~s.isin(_IC_VAZIA)


RULE_REGISTRY: dict[str, type[Rule]] = {}


def register_rule(cls: type[Rule]) -> type[Rule]:
    """Decorator para registrar uma regra automaticamente.

    Uso:
        @register_rule
        class R082(Rule):
            rule_id = "R082"
            ...
    """
    if not cls.rule_id:
        raise ValueError(f"Regra {cls.__name__} precisa definir 'rule_id'.")
    RULE_REGISTRY[cls.rule_id] = cls
    return cls
