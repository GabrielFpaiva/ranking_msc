"""
ranking_msc.exceptions
~~~~~~~~~~~~~~~~~~~~~~

Exceções customizadas do projeto.

Hierarquia:
    RankingMSCError          (base — NUNCA levante diretamente)
    ├── ConfigError          — problema em settings.yaml ou variáveis
    ├── InputFormatError     — CSV fora do layout esperado
    ├── SnapshotError        — falha ao gravar/ler snapshot (parquet)
    ├── ReportError          — falha ao gerar relatório Excel
    ├── RuleExecutionError   — erro durante execução de uma regra
    └── ConcurrencyError     — conflito de concorrência entre usuários

Regra geral: cada módulo levanta a exceção mais específica possível,
sempre incluindo mensagem descritiva em português para o log.
"""


class RankingMSCError(Exception):
    """Classe-base de todas as exceções do ranking_msc."""


class ConfigError(RankingMSCError):
    """Erro de configuração (YAML ausente, valor inválido, etc.)."""


class InputFormatError(RankingMSCError):
    """CSV MSC com formato inválido ou colunas faltando."""


class SnapshotError(RankingMSCError):
    """Falha ao gravar ou ler snapshot Parquet de uma competência."""


class ReportError(RankingMSCError):
    """Falha ao gerar relatório Excel de pendências/evidências."""


class RuleExecutionError(RankingMSCError):
    """Erro inesperado durante a execução de uma regra de validação.

    Atributos extras (definir no __init__ quando implementar):
        rule_id: str — identificador da regra (ex: "R082")
        details: str — descrição adicional
    """

    def __init__(self, rule_id: str, message: str) -> None:
        self.rule_id = rule_id
        super().__init__(f"[{rule_id}] {message}")


class ConcurrencyError(RankingMSCError):
    """Conflito de concorrência — ex: dois usuários processando a mesma competência."""
