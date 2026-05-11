"""Testes unitários das regras piloto (F2-17).

Cobre as 5 regras implementadas nas tasks F2-12..F2-15:
    - R003: Tipo_valor válido (pré-pivot, via context.pre_pivot_issues)
    - R004: Natureza_valor válida (pré-pivot, via context.pre_pivot_issues)
    - R010: Conta contábil existe no PCASP Estendido 2026
    - R021: PO com 5 dígitos e existente na tabela oficial
    - R030: Débito = Crédito por conta patrimonial (fechamento)

Critério de aceite: cada regra com ≥2 testes (positivo + negativo).
"""

from __future__ import annotations

import pandas as pd
import pytest

from ranking_msc.config.settings import Settings
from ranking_msc.engine.executor import EngineContext
from ranking_msc.rules.r001 import R001
from ranking_msc.rules.r0010 import R0010
from ranking_msc.rules.r0011 import R0011
from ranking_msc.rules.r002 import R002
from ranking_msc.rules.r003 import R003
from ranking_msc.rules.r004 import R004
from ranking_msc.rules.r005 import R005
from ranking_msc.rules.r010 import R010
from ranking_msc.rules.r011 import R011
from ranking_msc.rules.r012 import R012
from ranking_msc.rules.r021 import R021
from ranking_msc.rules.r030 import R030
from ranking_msc.rules.r033 import R033
from ranking_msc.rules.r034 import R034
from ranking_msc.rules.r035 import R035
from ranking_msc.rules.r038 import R038
from ranking_msc.rules.r053 import R053
from ranking_msc.rules.r061 import R061
from ranking_msc.rules.r062 import R062
from ranking_msc.rules.r066 import R066
from ranking_msc.rules.r067 import R067
from ranking_msc.rules.r068 import R068
from ranking_msc.rules.r071 import R071
from ranking_msc.rules.r072 import R072
from ranking_msc.rules.r073 import R073
from ranking_msc.rules.r074 import R074
from ranking_msc.rules.r082 import R082

# ---------------------------------------------------------------------------
# Helpers compartilhados
# ---------------------------------------------------------------------------

def _empty_df() -> pd.DataFrame:
    """DataFrame vazio com colunas mínimas esperadas pelas regras."""
    return pd.DataFrame(
        columns=["conta_contabil", "po", "movimento_debito", "movimento_credito"]
    )


def _pcasp_stub() -> pd.DataFrame:
    """PCASP reduzido: contas analíticas ativas das quatro classes patrimoniais."""
    return pd.DataFrame(
        {
            "conta_contabil": [
                "111110200",
                "211000000",
                "311000000",
                "411000000",
            ],
            "nivel": ["Último", "Último", "Último", "Último"],
            "status": ["Ativa", "Ativa", "Ativa", "Ativa"],
        }
    )


def _tabela_po_stub() -> pd.DataFrame:
    """Tabela PO reduzida para testes."""
    return pd.DataFrame({"codigo": ["10131", "20202", "30303"]})


# ---------------------------------------------------------------------------
# R003 — Tipo_valor válido
# ---------------------------------------------------------------------------


class TestR003:
    def test_pre_pivot_sem_violacoes_r003_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Contexto sem violações R003 → nenhuma pendência."""
        result = R003().execute(_empty_df(), engine_context)
        assert len(result) == 0

    def test_pre_pivot_com_violacao_r003_gera_pendencia_erro(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Violação R003 em pre_pivot_issues → pendência ERRO."""
        engine_context_com_violacao = EngineContext(
            competencia=engine_context.competencia,
            siconfi=engine_context.siconfi,
            settings=engine_context.settings,
            usuario=engine_context.usuario,
            pre_pivot_issues=[
                {
                    "regra": "R003",
                    "conta_contabil": "111110200",
                    "valor_encontrado": "TIPO_INVALIDO",
                }
            ],
        )
        result = R003().execute(_empty_df(), engine_context_com_violacao)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R003"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "TIPO_INVALIDO" in result.iloc[0]["descricao"]

    def test_pre_pivot_com_violacoes_r004_nao_afeta_r003(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Violações R004 em pre_pivot_issues não geram pendências R003."""
        engine_context_com_r004 = EngineContext(
            competencia=engine_context.competencia,
            siconfi=engine_context.siconfi,
            settings=engine_context.settings,
            usuario=engine_context.usuario,
            pre_pivot_issues=[
                {
                    "regra": "R004",
                    "conta_contabil": "111110200",
                    "valor_encontrado": "X",
                }
            ],
        )
        result = R003().execute(_empty_df(), engine_context_com_r004)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R004 — Natureza_valor válida
# ---------------------------------------------------------------------------


class TestR004:
    def test_pre_pivot_sem_violacoes_r004_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Contexto sem violações R004 → nenhuma pendência."""
        result = R004().execute(_empty_df(), engine_context)
        assert len(result) == 0

    def test_pre_pivot_com_violacao_r004_gera_pendencia_erro(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Violação R004 em pre_pivot_issues → pendência ERRO."""
        engine_context_com_violacao = EngineContext(
            competencia=engine_context.competencia,
            siconfi=engine_context.siconfi,
            settings=engine_context.settings,
            usuario=engine_context.usuario,
            pre_pivot_issues=[
                {
                    "regra": "R004",
                    "conta_contabil": "111110200",
                    "valor_encontrado": "X",
                }
            ],
        )
        result = R004().execute(_empty_df(), engine_context_com_violacao)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R004"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["valor_esperado"] == "D | C"

    def test_pre_pivot_com_violacoes_r003_nao_afeta_r004(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Violações R003 em pre_pivot_issues não geram pendências R004."""
        engine_context_com_r003 = EngineContext(
            competencia=engine_context.competencia,
            siconfi=engine_context.siconfi,
            settings=engine_context.settings,
            usuario=engine_context.usuario,
            pre_pivot_issues=[
                {
                    "regra": "R003",
                    "conta_contabil": "111110200",
                    "valor_encontrado": "INVALIDO",
                }
            ],
        )
        result = R004().execute(_empty_df(), engine_context_com_r003)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R0010 — Header na primeira linha
# ---------------------------------------------------------------------------


class TestR0010:
    def test_pre_pivot_sem_violacoes_r0010_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
    ) -> None:
        result = R0010().execute(_empty_df(), engine_context)
        assert len(result) == 0

    def test_pre_pivot_com_violacao_r0010_gera_pendencia_erro(
        self,
        engine_context: EngineContext,
    ) -> None:
        context = EngineContext(
            competencia=engine_context.competencia,
            siconfi=engine_context.siconfi,
            settings=engine_context.settings,
            usuario=engine_context.usuario,
            pre_pivot_issues=[
                {
                    "regra": "R0010",
                    "valor_encontrado": "header na primeira linha; metadata ausente",
                }
            ],
        )
        result = R0010().execute(_empty_df(), context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R0010"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "primeira linha" in result.iloc[0]["descricao"]


# ---------------------------------------------------------------------------
# R0011 — Valor não-negativo
# ---------------------------------------------------------------------------


class TestR0011:
    def test_pre_pivot_sem_violacoes_r0011_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
    ) -> None:
        result = R0011().execute(_empty_df(), engine_context)
        assert len(result) == 0

    def test_pre_pivot_com_violacao_r0011_gera_pendencia_erro(
        self,
        engine_context: EngineContext,
    ) -> None:
        context = EngineContext(
            competencia=engine_context.competencia,
            siconfi=engine_context.siconfi,
            settings=engine_context.settings,
            usuario=engine_context.usuario,
            pre_pivot_issues=[
                {
                    "regra": "R0011",
                    "conta_contabil": "111110200",
                    "valor_encontrado": "-100.00",
                }
            ],
        )
        result = R0011().execute(_empty_df(), context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R0011"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["conta_contabil"] == "111110200"
        assert "negativo" in result.iloc[0]["descricao"]


# ---------------------------------------------------------------------------
# R010 — Conta contábil existe no PCASP
# ---------------------------------------------------------------------------


class TestR010:
    def test_conta_existente_no_pcasp_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta presente no PCASP → nenhuma pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r010.load_pcasp", lambda *a, **kw: _pcasp_stub()
        )
        df = pd.DataFrame({"conta_contabil": ["111110200", "211000000"]})
        result = R010().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_ausente_no_pcasp_gera_pendencia_erro(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta ausente no PCASP → pendência ERRO com a conta na descrição."""
        monkeypatch.setattr(
            "ranking_msc.rules.r010.load_pcasp", lambda *a, **kw: _pcasp_stub()
        )
        df = pd.DataFrame({"conta_contabil": ["999999999"]})
        result = R010().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R010"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "999999999" in result.iloc[0]["descricao"]

    def test_conta_invalida_duplicada_gera_uma_unica_pendencia(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta inválida duplicada no DataFrame → uma única pendência (deduplicação)."""
        monkeypatch.setattr(
            "ranking_msc.rules.r010.load_pcasp", lambda *a, **kw: _pcasp_stub()
        )
        df = pd.DataFrame({"conta_contabil": ["999999999", "999999999", "111110200"]})
        result = R010().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["conta_contabil"] == "999999999"


# ---------------------------------------------------------------------------
# R021 — PO válido (5 dígitos + tabela)
# ---------------------------------------------------------------------------


class TestR021:
    def test_po_valido_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PO com 5 dígitos e presente na tabela → nenhuma pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r021.load_tabela_po",
            lambda *a, **kw: _tabela_po_stub(),
        )
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": ["10131"]})
        result = R021().execute(df, engine_context)
        assert len(result) == 0

    def test_po_ausente_da_tabela_gera_pendencia_erro(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PO com formato correto mas ausente da tabela → pendência ERRO."""
        monkeypatch.setattr(
            "ranking_msc.rules.r021.load_tabela_po",
            lambda *a, **kw: _tabela_po_stub(),
        )
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": ["99999"]})
        result = R021().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R021"
        assert result.iloc[0]["severidade"] == "ERRO"

    def test_po_com_formato_invalido_gera_pendencia_erro(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PO com menos de 5 dígitos → pendência ERRO de formato."""
        monkeypatch.setattr(
            "ranking_msc.rules.r021.load_tabela_po",
            lambda *a, **kw: _tabela_po_stub(),
        )
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": ["123"]})
        result = R021().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R021"
        assert result.iloc[0]["severidade"] == "ERRO"

    def test_po_vazio_e_ignorado(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Linha sem PO (valor vazio) → não gera pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r021.load_tabela_po",
            lambda *a, **kw: _tabela_po_stub(),
        )
        df = pd.DataFrame({"conta_contabil": ["211000000"], "po": [""]})
        result = R021().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R030 — Fechamento patrimonial (D = C)
# ---------------------------------------------------------------------------


class TestR030:
    def _df_patrimonial(
        self,
        conta: str,
        mov_d: float,
        mov_c: float,
    ) -> pd.DataFrame:
        """Cria DataFrame com uma conta patrimonial e os movimentos fornecidos."""
        return pd.DataFrame(
            {
                "conta_contabil": [conta],
                "movimento_debito": [mov_d],
                "movimento_credito": [mov_c],
            }
        )

    def test_debito_igual_credito_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Mov_D == Mov_C em conta patrimonial → nenhuma pendência."""
        df = self._df_patrimonial("111110200", 1000.00, 1000.00)
        result = R030().execute(df, engine_context)
        assert len(result) == 0

    def test_diferenca_acima_tolerancia_gera_pendencia_erro(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Mov_D ≠ Mov_C (diferença > 0.01) em conta patrimonial → pendência ERRO."""
        df = self._df_patrimonial("111110200", 1000.00, 500.00)
        result = R030().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R030"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["conta_contabil"] == "111110200"

    def test_conta_de_resultado_classe_5_e_ignorada(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Conta de classe 5 (resultado) com D ≠ C → não gera pendência."""
        df = self._df_patrimonial("511000000", 1000.00, 500.00)
        result = R030().execute(df, engine_context)
        assert len(result) == 0

    def test_diferenca_dentro_da_tolerancia_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Diferença ≤ 0.01 (tolerância) → não gera pendência."""
        df = self._df_patrimonial("211000000", 1000.00, 999.995)
        result = R030().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R001 — Colunas obrigatórias presentes
# ---------------------------------------------------------------------------


class TestR001:
    def test_sem_issues_r001_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Contexto sem issues R001 → nenhuma pendência."""
        result = R001().execute(_empty_df(), engine_context)
        assert len(result) == 0

    def test_coluna_ausente_gera_pendencia_erro(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Issue R001 no pre_pivot_issues → pendência ERRO por coluna ausente."""
        ctx = EngineContext(
            competencia=engine_context.competencia,
            siconfi=engine_context.siconfi,
            settings=engine_context.settings,
            usuario=engine_context.usuario,
            pre_pivot_issues=[
                {
                    "regra": "R001",
                    "conta_contabil": "",
                    "campo": "IC5",
                    "valor_encontrado": "coluna ausente no CSV",
                }
            ],
        )
        result = R001().execute(_empty_df(), ctx)
        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R001"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "IC5" in result.iloc[0]["descricao"]

    def test_multiplas_colunas_ausentes_geram_multiplas_pendencias(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Múltiplas colunas ausentes → uma pendência por coluna."""
        ctx = EngineContext(
            competencia=engine_context.competencia,
            siconfi=engine_context.siconfi,
            settings=engine_context.settings,
            usuario=engine_context.usuario,
            pre_pivot_issues=[
                {
                    "regra": "R001",
                    "conta_contabil": "",
                    "campo": "IC5",
                    "valor_encontrado": "coluna ausente no CSV",
                },
                {
                    "regra": "R001",
                    "conta_contabil": "",
                    "campo": "TIPO5",
                    "valor_encontrado": "coluna ausente no CSV",
                },
            ],
        )
        result = R001().execute(_empty_df(), ctx)
        assert len(result) == 2

    def test_issues_de_outras_regras_nao_afetam_r001(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Issues de R005 no pre_pivot_issues não geram pendências R001."""
        ctx = EngineContext(
            competencia=engine_context.competencia,
            siconfi=engine_context.siconfi,
            settings=engine_context.settings,
            usuario=engine_context.usuario,
            pre_pivot_issues=[
                {
                    "regra": "R005",
                    "conta_contabil": "111110200",
                    "campo": "Valor",
                    "valor_encontrado": "abc",
                }
            ],
        )
        result = R001().execute(_empty_df(), ctx)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R002 — CONTA preenchida em todas as linhas
# ---------------------------------------------------------------------------


class TestR002:
    def test_todas_contas_preenchidas_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Todas linhas com conta_contabil preenchida → nenhuma pendência."""
        df = pd.DataFrame({"conta_contabil": ["111110200", "211000000"]})
        result = R002().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_vazia_string_gera_pendencia_erro(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Linha com conta_contabil='' → pendência ERRO."""
        df = pd.DataFrame({"conta_contabil": ["111110200", ""]})
        result = R002().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R002"
        assert result.iloc[0]["severidade"] == "ERRO"

    def test_multiplas_contas_vazias_geram_uma_pendencia_por_linha(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Duas linhas com CONTA vazia → duas pendências."""
        df = pd.DataFrame({"conta_contabil": ["", "", "111110200"]})
        result = R002().execute(df, engine_context)
        assert len(result) == 2

    def test_df_sem_coluna_conta_contabil_retorna_vazio_sem_excecao(
        self,
        engine_context: EngineContext,
    ) -> None:
        """DataFrame sem coluna conta_contabil → retorna vazio sem exceção."""
        df = pd.DataFrame({"outra_coluna": ["valor"]})
        result = R002().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R005 — Valor numérico válido
# ---------------------------------------------------------------------------


class TestR005:
    def test_sem_issues_r005_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Contexto sem issues R005 → nenhuma pendência."""
        result = R005().execute(_empty_df(), engine_context)
        assert len(result) == 0

    def test_valor_nao_numerico_gera_pendencia_erro(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Issue R005 no pre_pivot_issues → pendência ERRO."""
        ctx = EngineContext(
            competencia=engine_context.competencia,
            siconfi=engine_context.siconfi,
            settings=engine_context.settings,
            usuario=engine_context.usuario,
            pre_pivot_issues=[
                {
                    "regra": "R005",
                    "conta_contabil": "111110200",
                    "campo": "Valor",
                    "valor_encontrado": "1.234,56",
                    "competencia": "2024-01",
                }
            ],
        )
        result = R005().execute(_empty_df(), ctx)
        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R005"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "1.234,56" in result.iloc[0]["valor_encontrado"]

    def test_descricao_menciona_ponto_como_separador(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Pendência R005 → descrição menciona separador decimal como ponto."""
        ctx = EngineContext(
            competencia=engine_context.competencia,
            siconfi=engine_context.siconfi,
            settings=engine_context.settings,
            usuario=engine_context.usuario,
            pre_pivot_issues=[
                {
                    "regra": "R005",
                    "conta_contabil": "111110200",
                    "campo": "Valor",
                    "valor_encontrado": "INVALIDO",
                    "competencia": "2024-01",
                }
            ],
        )
        result = R005().execute(_empty_df(), ctx)
        assert len(result) == 1
        assert "ponto" in result.iloc[0]["descricao"].lower()

    def test_issues_de_r003_nao_afetam_r005(
        self,
        engine_context: EngineContext,
    ) -> None:
        """Issues de R003 no pre_pivot_issues não geram pendências R005."""
        ctx = EngineContext(
            competencia=engine_context.competencia,
            siconfi=engine_context.siconfi,
            settings=engine_context.settings,
            usuario=engine_context.usuario,
            pre_pivot_issues=[
                {
                    "regra": "R003",
                    "conta_contabil": "111110200",
                    "valor_encontrado": "tipo_invalido",
                }
            ],
        )
        result = R005().execute(_empty_df(), ctx)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R011 — Conta é de último nível (analítica)
# ---------------------------------------------------------------------------


class TestR011:
    def test_conta_ultimo_nivel_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta com nivel == 'Último' no PCASP → nenhuma pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r011.load_pcasp", lambda *a, **kw: _pcasp_stub()
        )
        df = pd.DataFrame({"conta_contabil": ["111110200", "211000000"]})
        result = R011().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_sintetica_nivel_superior_gera_pendencia_erro(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta com nivel == 'Superior' no PCASP → pendência ERRO."""
        pcasp_com_sintetica = pd.DataFrame(
            {
                "conta_contabil": ["100000000", "111110200"],
                "nivel": ["Superior", "Último"],
                "status": ["Ativa", "Ativa"],
            }
        )
        monkeypatch.setattr(
            "ranking_msc.rules.r011.load_pcasp", lambda *a, **kw: pcasp_com_sintetica
        )
        df = pd.DataFrame({"conta_contabil": ["100000000"]})
        result = R011().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R011"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "100000000" in result.iloc[0]["descricao"]

    def test_conta_sintetica_duplicada_gera_uma_pendencia(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta sintética duplicada no DataFrame → uma única pendência (deduplicação)."""
        pcasp_com_sintetica = pd.DataFrame(
            {
                "conta_contabil": ["100000000"],
                "nivel": ["Superior"],
                "status": ["Ativa"],
            }
        )
        monkeypatch.setattr(
            "ranking_msc.rules.r011.load_pcasp", lambda *a, **kw: pcasp_com_sintetica
        )
        df = pd.DataFrame({"conta_contabil": ["100000000", "100000000"]})
        result = R011().execute(df, engine_context)
        assert len(result) == 1

    def test_conta_ausente_no_pcasp_nao_gera_pendencia_r011(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta ausente no PCASP (domínio de R010) → R011 não gera pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r011.load_pcasp", lambda *a, **kw: _pcasp_stub()
        )
        df = pd.DataFrame({"conta_contabil": ["999999999"]})
        result = R011().execute(df, engine_context)
        assert len(result) == 0

    def test_pcasp_sem_coluna_nivel_retorna_vazio_sem_excecao(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PCASP sem coluna 'nivel' → retorna vazio sem levantar exceção."""
        pcasp_sem_nivel = pd.DataFrame({"conta_contabil": ["111110200"]})
        monkeypatch.setattr(
            "ranking_msc.rules.r011.load_pcasp", lambda *a, **kw: pcasp_sem_nivel
        )
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        result = R011().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R012 — Conta está Ativa no PCASP
# ---------------------------------------------------------------------------


class TestR012:
    def test_conta_ativa_nao_gera_pendencia(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta com status == 'Ativa' no PCASP → nenhuma pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r012.load_pcasp", lambda *a, **kw: _pcasp_stub()
        )
        df = pd.DataFrame({"conta_contabil": ["111110200", "211000000"]})
        result = R012().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_inativa_gera_pendencia_alerta(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta com status != 'Ativa' no PCASP → pendência ALERTA."""
        pcasp_com_inativa = pd.DataFrame(
            {
                "conta_contabil": ["111110200", "211000000"],
                "nivel": ["Último", "Último"],
                "status": ["Ativa", "Inativa"],
            }
        )
        monkeypatch.setattr(
            "ranking_msc.rules.r012.load_pcasp", lambda *a, **kw: pcasp_com_inativa
        )
        df = pd.DataFrame({"conta_contabil": ["211000000"]})
        result = R012().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R012"
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert "211000000" in result.iloc[0]["descricao"]

    def test_conta_inativa_duplicada_gera_uma_pendencia(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta inativa duplicada no DataFrame → uma única pendência (deduplicação)."""
        pcasp_com_inativa = pd.DataFrame(
            {
                "conta_contabil": ["211000000"],
                "nivel": ["Último"],
                "status": ["Inativa"],
            }
        )
        monkeypatch.setattr(
            "ranking_msc.rules.r012.load_pcasp", lambda *a, **kw: pcasp_com_inativa
        )
        df = pd.DataFrame({"conta_contabil": ["211000000", "211000000"]})
        result = R012().execute(df, engine_context)
        assert len(result) == 1

    def test_conta_ausente_no_pcasp_nao_gera_pendencia_r012(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta ausente no PCASP (domínio de R010) → R012 não gera pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r012.load_pcasp", lambda *a, **kw: _pcasp_stub()
        )
        df = pd.DataFrame({"conta_contabil": ["999999999"]})
        result = R012().execute(df, engine_context)
        assert len(result) == 0

    def test_pcasp_sem_coluna_status_retorna_vazio_sem_excecao(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PCASP sem coluna 'status' → retorna vazio sem levantar exceção."""
        pcasp_sem_status = pd.DataFrame({"conta_contabil": ["111110200"]})
        monkeypatch.setattr(
            "ranking_msc.rules.r012.load_pcasp", lambda *a, **kw: pcasp_sem_status
        )
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        result = R012().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Helpers para R033, R034, R038, R082
# ---------------------------------------------------------------------------

def _ctx_with_issues(
    settings: Settings,
    issues: list[dict[str, object]],
) -> EngineContext:
    """EngineContext com pre_pivot_issues pré-populados."""
    ctx = EngineContext(
        competencia="2024-01",
        siconfi="250400",
        settings=settings,
        usuario="teste",
    )
    ctx.pre_pivot_issues = issues
    return ctx


def _pcasp_com_id_ic() -> pd.DataFrame:
    """PCASP stub com coluna id_ic para testes de R038."""
    return pd.DataFrame({
        "conta_contabil": ["111110200", "211000000", "311000000"],
        "id_ic": ["4", "2", "1"],
        "nivel": ["Último", "Último", "Último"],
        "status": ["Ativa", "Ativa", "Ativa"],
    })


# Helpers compartilhados R035/R036/R037
# ---------------------------------------------------------------------------

def _df_movimentos(contas: list[str], mov_d: list[float], mov_c: list[float]) -> pd.DataFrame:
    """Cria DataFrame com contas e movimentos para testes de fechamento agregado."""
    return pd.DataFrame({
        "conta_contabil": contas,
        "movimento_debito": mov_d,
        "movimento_credito": mov_c,
    })


# ---------------------------------------------------------------------------
# R033 — Pares IC/TIPO presentes
# ---------------------------------------------------------------------------

class TestR033:
    def test_sem_violacoes_retorna_vazio(
        self, engine_context: EngineContext
    ) -> None:
        """Sem issues R033 em pre_pivot_issues → zero pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        result = R033().execute(df, engine_context)
        assert len(result) == 0

    def test_violacao_drenada_gera_erro(
        self, settings: Settings
    ) -> None:
        """Issue R033 em pre_pivot_issues → ERRO drenado."""
        ctx = _ctx_with_issues(settings, [
            {
                "regra": "R033",
                "conta_contabil": "111110200",
                "campo": "IC1/TIPO1",
                "valor_encontrado": "IC1='10131' presente mas TIPO1 está vazio",
                "competencia": "2024-01",
            }
        ])
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        result = R033().execute(df, ctx)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R033"

    def test_issue_de_outra_regra_ignorado(
        self, settings: Settings
    ) -> None:
        """Issues de outras regras em pre_pivot_issues → R033 retorna vazio."""
        ctx = _ctx_with_issues(settings, [
            {"regra": "R009", "conta_contabil": "", "campo": "colunas_ic_tipo",
             "valor_encontrado": "10"}
        ])
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        result = R033().execute(df, ctx)
        assert len(result) == 0


# R035 — Débito = Crédito — Patrimonial (classes 1-4)
# ---------------------------------------------------------------------------


class TestR035:
    def test_totais_equilibrados_nao_gera_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Total D == Total C em contas patrimoniais → nenhuma pendência."""
        df = _df_movimentos(
            ["111110200", "211000000"],
            [500.00, 300.00],
            [400.00, 400.00],
        )
        result = R035().execute(df, engine_context)
        assert len(result) == 0

    def test_totais_desequilibrados_gera_pendencia_erro(
        self, engine_context: EngineContext
    ) -> None:
        """Total D ≠ Total C (diferença > tolerância) → uma pendência ERRO."""
        df = _df_movimentos(["111110200"], [1000.00], [500.00])
        result = R035().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R035"
        assert result.iloc[0]["severidade"] == "ERRO"
        assert "classes 1-4" in result.iloc[0]["conta_contabil"]

    def test_contas_de_outras_classes_nao_contaminam(
        self, engine_context: EngineContext
    ) -> None:
        """Contas classes 5-8 com D ≠ C não afetam R035."""
        df = _df_movimentos(
            ["511000000", "611000000", "711000000"],
            [100.00, 200.00, 300.00],
            [0.00, 0.00, 0.00],
        )
        result = R035().execute(df, engine_context)
        assert len(result) == 0

    def test_df_sem_contas_patrimoniais_nao_gera_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """DataFrame sem contas patrimoniais → nenhuma pendência."""
        df = _df_movimentos(["511000000"], [1000.00], [0.00])
        result = R035().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R034 — PO obrigatório
# ---------------------------------------------------------------------------

class TestR034:
    def test_todos_com_po_retorna_vazio(
        self, engine_context: EngineContext
    ) -> None:
        """Todas as contas com PO preenchido → zero pendências."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000"],
            "po": ["10131", "20202"],
        })
        result = R034().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_sem_po_gera_erro(
        self, engine_context: EngineContext
    ) -> None:
        """Conta sem PO → ERRO."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000"],
            "po": ["", "20202"],
        })
        result = R034().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R034"
        assert "111110200" in result.iloc[0]["conta_contabil"]

    def test_df_sem_coluna_po_retorna_vazio(
        self, engine_context: EngineContext
    ) -> None:
        """DataFrame sem coluna 'po' → retorna vazio sem exceção."""
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        result = R034().execute(df, engine_context)
        assert len(result) == 0

    def test_po_nan_e_zero_tratados_como_ausente(
        self, engine_context: EngineContext
    ) -> None:
        """Valores NaN e '0' em po → considerados ausentes → ERRO."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "211000000"],
            "po": ["0", "nan"],
        })
        result = R034().execute(df, engine_context)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# R038 — IC associada à conta correta
# ---------------------------------------------------------------------------

class TestR038:
    def test_ics_corretas_retorna_vazio(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ICs dentro do conjunto permitido para a conta → zero pendências."""
        monkeypatch.setattr(
            "ranking_msc.rules.r038.load_pcasp",
            lambda *a, **kw: _pcasp_com_id_ic(),
        )
        # conta 111110200 tem id_ic=4 → IC_MAP[4] = [PO, FP, FR, CO]
        df = pd.DataFrame({
            "conta_contabil": ["111110200"],
            "po": ["10131"],
            "fp": ["1"],
            "fr": ["1500"],
            "co": ["1001"],
            "dc": [""],
            "nr": [""],
            "nd": [""],
            "fs": [""],
            "ai": [""],
        })
        result = R038().execute(df, engine_context)
        assert len(result) == 0

    def test_ic_nao_permitida_gera_erro(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """IC não permitida para a conta (NR em conta com id_ic=2) → ERRO."""
        monkeypatch.setattr(
            "ranking_msc.rules.r038.load_pcasp",
            lambda *a, **kw: _pcasp_com_id_ic(),
        )
        # conta 211000000 tem id_ic=2 → IC_MAP[2] = [PO, FP] — NR não permitido
        df = pd.DataFrame({
            "conta_contabil": ["211000000"],
            "po": ["20202"],
            "fp": ["1"],
            "nr": ["12345678"],
            "fr": [""],
            "co": [""],
            "dc": [""],
            "nd": [""],
            "fs": [""],
            "ai": [""],
        })
        result = R038().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R038"
        assert "NR" in result.iloc[0]["descricao"]

    def test_pcasp_sem_id_ic_retorna_vazio(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PCASP sem coluna id_ic → retorna vazio sem exceção."""
        monkeypatch.setattr(
            "ranking_msc.rules.r038.load_pcasp",
            lambda *a, **kw: pd.DataFrame({"conta_contabil": ["111110200"]}),
        )
        df = pd.DataFrame({
            "conta_contabil": ["111110200"],
            "po": ["10131"],
        })
        result = R038().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R082 — Ordem das ICs conforme leiaute
# ---------------------------------------------------------------------------

class TestR082:
    def test_sem_violacoes_retorna_vazio(
        self, engine_context: EngineContext
    ) -> None:
        """Sem issues R082 em pre_pivot_issues → zero pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        result = R082().execute(df, engine_context)
        assert len(result) == 0

    def test_violacao_drenada_gera_alerta(
        self, settings: Settings
    ) -> None:
        """Issue R082 em pre_pivot_issues → ALERTA drenado."""
        ctx = _ctx_with_issues(settings, [
            {
                "regra": "R082",
                "conta_contabil": "111110200",
                "campo": "ordem_IC",
                "valor_encontrado": "CO,PO,FR",
                "competencia": "2024-01",
            }
        ])
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        result = R082().execute(df, ctx)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R082"

    def test_issue_de_outra_regra_ignorado(
        self, settings: Settings
    ) -> None:
        """Issues de outras regras → R082 retorna vazio."""
        ctx = _ctx_with_issues(settings, [
            {"regra": "R033", "conta_contabil": "111110200",
             "campo": "IC1/TIPO1", "valor_encontrado": "IC1='x' presente mas TIPO1 vazio"}
        ])
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        result = R082().execute(df, ctx)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Testes de regressão — P1/P2 badges
# ---------------------------------------------------------------------------


class TestR038MultiRow:
    """P1: R038 deve avaliar todas as linhas, não só a primeira por conta."""

    def test_segunda_linha_com_ic_invalida_detectada(
        self,
        engine_context: EngineContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta com 2 linhas: 1ª válida, 2ª com NR não permitida → ERRO detectado."""
        monkeypatch.setattr(
            "ranking_msc.rules.r038.load_pcasp",
            lambda *a, **kw: _pcasp_com_id_ic(),
        )
        # conta 211000000 tem id_ic=2 → IC_MAP[2] = [PO, FP]
        # Linha 1: válida (apenas PO+FP)
        # Linha 2: NR preenchida (não permitida para id_ic=2)
        df = pd.DataFrame({
            "conta_contabil": ["211000000", "211000000"],
            "po": ["20202", "20202"],
            "fp": ["1", "1"],
            "nr": ["", "12345678"],   # 2ª linha tem NR inválida
            "fr": ["", ""],
            "co": ["", ""],
            "dc": ["", ""],
            "nd": ["", ""],
            "fs": ["", ""],
            "ai": ["", ""],
        })
        result = R038().execute(df, engine_context)
        assert len(result) >= 1, (
            "P1 regression: R038 deve detectar IC inválida na 2ª linha "
            "da mesma conta, não apenas na primeira."
        )
        assert any("NR" in str(row["descricao"]) for _, row in result.iterrows())


class TestCheckIcPairsContinue:
    """P2: _check_ic_pairs deve continuar validando posições após coluna ausente."""

    def test_coluna_ic3_ausente_nao_impede_ic4(self) -> None:
        """CSV sem ic3/tipo3 mas com ic4/tipo4 → R033 detecta mismatch em ic4."""
        from ranking_msc.io.reader_msc import _check_ic_pairs

        # ic3/tipo3 ausentes, ic4 preenchido mas tipo4 vazio → R033
        df = pd.DataFrame({
            "conta_contabil": ["111110200"],
            "ic1": ["10131"], "tipo1": ["PO"],
            "ic2": ["1"],     "tipo2": ["FP"],
            # ic3/tipo3 ausentes
            "ic4": ["99999"], "tipo4": [""],   # mismatch!
            "ic5": [""],      "tipo5": [""],
            "ic6": [""],      "tipo6": [""],
        })
        issues = _check_ic_pairs(df, "2024-01")
        r033_ic4 = [i for i in issues if "IC4" in str(i.get("campo", ""))]
        assert len(r033_ic4) >= 1, (
            "P2 regression: _check_ic_pairs deve continuar validando "
            "posições após colunas intermediárias ausentes (ic3/tipo3)."
        )


class TestCheckIcOrderSkipsR033:
    """P2: _check_ic_order deve ignorar linhas com R033 (pares inconsistentes)."""

    def test_linha_com_r033_nao_gera_r082(self) -> None:
        """Conta com R033 (TIPO sem IC) → _check_ic_order não emite R082."""
        from ranking_msc.io.reader_msc import _check_ic_order

        # TIPO1=PO mas TIPO2=CO sem IC2 (puro R033, não deve gerar R082)
        df = pd.DataFrame({
            "conta_contabil": ["111110200"],
            "ic1": ["10131"], "tipo1": ["PO"],
            "ic2": [""],      "tipo2": ["CO"],  # R033 violation
            "ic3": [""],      "tipo3": [""],
            "ic4": [""],      "tipo4": [""],
            "ic5": [""],      "tipo5": [""],
            "ic6": [""],      "tipo6": [""],
        })

        issues = _check_ic_order(df, "2024-01")
        r082_for_conta = [
            i for i in issues
            if i.get("conta_contabil") == "111110200"
        ]
        assert len(r082_for_conta) == 0, (
            "P2 regression: _check_ic_order não deve emitir R082 para "
            "linhas com pares IC/TIPO inconsistentes."
        )

    def test_linha_sem_r033_ainda_gera_r082(self) -> None:
        """Conta sem R033 mas com ordem errada → _check_ic_order emite R082."""
        from ranking_msc.io.reader_msc import _check_ic_order

        # Ordem errada: CO antes de PO (deveria ser PO,FP,FR,CO)
        df = pd.DataFrame({
            "conta_contabil": ["111110200"],
            "ic1": ["1001"],  "tipo1": ["CO"],   # CO na posição 1 (errado)
            "ic2": ["10131"], "tipo2": ["PO"],   # PO na posição 2 (errado)
            "ic3": [""],      "tipo3": [""],
            "ic4": [""],      "tipo4": [""],
            "ic5": [""],      "tipo5": [""],
            "ic6": [""],      "tipo6": [""],
        })

        issues = _check_ic_order(df, "2024-01")
        assert len(issues) >= 1, (
            "Conta sem R033 mas com ordem IC errada deve gerar R082."
        )

    def test_posicao_errada_gera_r082_mesmo_sequencia_comprimida_valida(self) -> None:
        """P1: FR no slot-4 em vez do slot-2 ou slot-3 deve gerar R082."""
        from ranking_msc.io.reader_msc import _check_ic_order

        # (PO, "", "", FR, "", "") — FR no slot errado.  A sequência comprimida
        # (PO, FR) seria aceita pela validação antiga, mas não é um layout válido.
        df = pd.DataFrame({
            "conta_contabil": ["111110200"],
            "ic1": ["10131"], "tipo1": ["PO"],
            "ic2": [""],      "tipo2": [""],
            "ic3": [""],      "tipo3": [""],
            "ic4": ["111111"], "tipo4": ["FR"],  # FR no slot-4 — inválido
            "ic5": [""],      "tipo5": [""],
            "ic6": [""],      "tipo6": [""],
        })

        issues = _check_ic_order(df, "2024-01")
        assert len(issues) >= 1, (
            "P1 regression: FR no slot-4 sem intermediários é posição inválida "
            "e deve gerar R082 mesmo que a sequência comprimida (PO,FR) exista."
        )


# ---------------------------------------------------------------------------
# Helpers para R053, R061, R062
# ---------------------------------------------------------------------------

def _pcasp_com_ind_sf(financeiro: list[str], permanente: list[str]) -> pd.DataFrame:
    """PCASP stub com IND_SF para testes de R061/R062."""
    contas = financeiro + permanente
    ind_sf = ["Financeiro"] * len(financeiro) + ["Permanente"] * len(permanente)
    return pd.DataFrame({"conta_contabil": contas, "ind_sf": ind_sf})


def _pcasp_com_titulo_desc(contas_intra: list[str], contas_normais: list[str]) -> pd.DataFrame:
    """PCASP stub com titulo_desc para testes de R053."""
    contas = contas_intra + contas_normais
    titulos = (
        [f"CONTA INTRA OFSS {c}" for c in contas_intra]
        + [f"Conta normal {c}" for c in contas_normais]
    )
    return pd.DataFrame({"conta_contabil": contas, "titulo_desc": titulos})


def _df_saldos(contas: list[str], sf_d: list[float], sf_c: list[float]) -> pd.DataFrame:
    """DataFrame com saldos finais para testes de R053."""
    return pd.DataFrame({
        "conta_contabil": contas,
        "saldo_final_debito": sf_d,
        "saldo_final_credito": sf_c,
    })


# ---------------------------------------------------------------------------
# R061 — Conta exclusivamente Financeira com FP=2
# ---------------------------------------------------------------------------


class TestR061:
    def test_financeira_com_fp1_nao_gera_pendencia(
        self, engine_context: EngineContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IND_SF=Financeiro e FP=1 → correto, nenhuma pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r061.load_pcasp",
            lambda *a, **kw: _pcasp_com_ind_sf(["111110200"], []),
        )
        df = pd.DataFrame({"conta_contabil": ["111110200"], "fp": ["1"]})
        result = R061().execute(df, engine_context)
        assert len(result) == 0

    def test_financeira_com_fp2_gera_alerta(
        self, engine_context: EngineContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IND_SF=Financeiro e FP=2 → uma pendência ALERTA."""
        monkeypatch.setattr(
            "ranking_msc.rules.r061.load_pcasp",
            lambda *a, **kw: _pcasp_com_ind_sf(["111110200"], []),
        )
        df = pd.DataFrame({"conta_contabil": ["111110200"], "fp": ["2"]})
        result = R061().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R061"
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["valor_esperado"] == "1"

    def test_permanente_com_fp1_nao_afeta_r061(
        self, engine_context: EngineContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IND_SF=Permanente com FP=1 é escopo de R062, não de R061."""
        monkeypatch.setattr(
            "ranking_msc.rules.r061.load_pcasp",
            lambda *a, **kw: _pcasp_com_ind_sf([], ["211000000"]),
        )
        df = pd.DataFrame({"conta_contabil": ["211000000"], "fp": ["1"]})
        result = R061().execute(df, engine_context)
        assert len(result) == 0

    def test_ind_sf_ausente_retorna_vazio(
        self, engine_context: EngineContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PCASP sem coluna ind_sf → build_issues([]) sem exceção."""
        monkeypatch.setattr(
            "ranking_msc.rules.r061.load_pcasp",
            lambda *a, **kw: pd.DataFrame({"conta_contabil": ["111110200"]}),
        )
        df = pd.DataFrame({"conta_contabil": ["111110200"], "fp": ["2"]})
        result = R061().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R062 — Conta exclusivamente Permanente com FP=1
# ---------------------------------------------------------------------------


class TestR062:
    def test_permanente_com_fp2_nao_gera_pendencia(
        self, engine_context: EngineContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IND_SF=Permanente e FP=2 → correto, nenhuma pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r062.load_pcasp",
            lambda *a, **kw: _pcasp_com_ind_sf([], ["211000000"]),
        )
        df = pd.DataFrame({"conta_contabil": ["211000000"], "fp": ["2"]})
        result = R062().execute(df, engine_context)
        assert len(result) == 0

    def test_permanente_com_fp1_gera_alerta(
        self, engine_context: EngineContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IND_SF=Permanente e FP=1 → uma pendência ALERTA."""
        monkeypatch.setattr(
            "ranking_msc.rules.r062.load_pcasp",
            lambda *a, **kw: _pcasp_com_ind_sf([], ["211000000"]),
        )
        df = pd.DataFrame({"conta_contabil": ["211000000"], "fp": ["1"]})
        result = R062().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R062"
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["valor_esperado"] == "2"

    def test_financeira_com_fp2_nao_afeta_r062(
        self, engine_context: EngineContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IND_SF=Financeiro com FP=2 é escopo de R061, não de R062."""
        monkeypatch.setattr(
            "ranking_msc.rules.r062.load_pcasp",
            lambda *a, **kw: _pcasp_com_ind_sf(["111110200"], []),
        )
        df = pd.DataFrame({"conta_contabil": ["111110200"], "fp": ["2"]})
        result = R062().execute(df, engine_context)
        assert len(result) == 0

    def test_ind_sf_ausente_retorna_vazio(
        self, engine_context: EngineContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PCASP sem coluna ind_sf → build_issues([]) sem exceção."""
        monkeypatch.setattr(
            "ranking_msc.rules.r062.load_pcasp",
            lambda *a, **kw: pd.DataFrame({"conta_contabil": ["211000000"]}),
        )
        df = pd.DataFrame({"conta_contabil": ["211000000"], "fp": ["1"]})
        result = R062().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R053 — Contas INTRA OFSS com contrapartida
# ---------------------------------------------------------------------------


class TestR053:
    def test_titulo_desc_ausente_retorna_vazio(
        self, engine_context: EngineContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PCASP sem titulo_desc → build_issues([]) sem exceção."""
        monkeypatch.setattr(
            "ranking_msc.rules.r053.load_pcasp",
            lambda *a, **kw: pd.DataFrame({"conta_contabil": ["111110200"]}),
        )
        df = _df_saldos(["111110200"], [1000.0], [500.0])
        result = R053().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_contas_intra_retorna_vazio(
        self, engine_context: EngineContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PCASP sem contas INTRA → nenhuma pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r053.load_pcasp",
            lambda *a, **kw: _pcasp_com_titulo_desc([], ["111110200"]),
        )
        df = _df_saldos(["111110200"], [1000.0], [500.0])
        result = R053().execute(df, engine_context)
        assert len(result) == 0

    def test_intra_balanceada_nao_gera_pendencia(
        self, engine_context: EngineContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Contas INTRA com total D == total C → nenhuma pendência."""
        monkeypatch.setattr(
            "ranking_msc.rules.r053.load_pcasp",
            lambda *a, **kw: _pcasp_com_titulo_desc(["711110000", "811110000"], []),
        )
        df = _df_saldos(["711110000", "811110000"], [500.0, 500.0], [500.0, 500.0])
        result = R053().execute(df, engine_context)
        assert len(result) == 0

    def test_intra_desequilibrada_gera_alerta(
        self, engine_context: EngineContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Contas INTRA com total D ≠ total C → uma pendência ALERTA."""
        monkeypatch.setattr(
            "ranking_msc.rules.r053.load_pcasp",
            lambda *a, **kw: _pcasp_com_titulo_desc(["711110000"], []),
        )
        df = _df_saldos(["711110000"], [1000.0], [400.0])
        result = R053().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R053"
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert "INTRA" in result.iloc[0]["conta_contabil"]


# ---------------------------------------------------------------------------
# Helpers para R066–R074
# ---------------------------------------------------------------------------


def _df_completo(
    contas: list[str],
    nr: list[str],
    nd: list[str],
    si_d: list[float] | None = None,
    si_c: list[float] | None = None,
    sf_d: list[float] | None = None,
    sf_c: list[float] | None = None,
    mov_d: list[float] | None = None,
    mov_c: list[float] | None = None,
    has_si: list[bool] | None = None,
    has_sf: list[bool] | None = None,
    has_pc: list[bool] | None = None,
) -> pd.DataFrame:
    """DataFrame com todas as colunas necessárias para R066–R074.

    Quando ``has_si``/``has_sf``/``has_pc`` são fornecidos, inclui os flags
    de presença produzidos pelo ``reader_msc._pivot_values``
    (``_has_saldo_inicial``, ``_has_saldo_final``, ``_has_period_change``),
    permitindo testar o comportamento correto de R074 com valores zero
    legítimos.
    """
    n = len(contas)
    zeros = [0.0] * n
    data: dict[str, object] = {
        "conta_contabil": contas,
        "nr": nr,
        "nd": nd,
        "saldo_inicial_debito": si_d if si_d is not None else zeros,
        "saldo_inicial_credito": si_c if si_c is not None else zeros,
        "movimento_debito": mov_d if mov_d is not None else zeros,
        "movimento_credito": mov_c if mov_c is not None else zeros,
        "saldo_final_debito": sf_d if sf_d is not None else zeros,
        "saldo_final_credito": sf_c if sf_c is not None else zeros,
    }
    if has_si is not None:
        data["_has_saldo_inicial"] = has_si
    if has_sf is not None:
        data["_has_saldo_final"] = has_sf
    if has_pc is not None:
        data["_has_period_change"] = has_pc
    return pd.DataFrame(data)



# ---------------------------------------------------------------------------
# R066 — Receita presente (NR informado)
# ---------------------------------------------------------------------------


class TestR066:
    def test_df_com_nr_nao_gera_pendencia(self, engine_context: EngineContext) -> None:
        """Ao menos um registro com NR preenchido → nenhuma pendência."""
        df = _df_completo(["411110100"], ["12345678"], ["0"])
        result = R066().execute(df, engine_context)
        assert len(result) == 0

    def test_df_sem_nr_gera_alerta(self, engine_context: EngineContext) -> None:
        """Nenhum NR preenchido → um ALERTA."""
        df = _df_completo(["111110100", "211110100"], ["0", "0"], ["0", "0"])
        result = R066().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R066"
        assert result.iloc[0]["severidade"] == "ALERTA"

    def test_df_vazio_retorna_vazio(self, engine_context: EngineContext) -> None:
        """DataFrame vazio → nenhuma pendência."""
        result = R066().execute(pd.DataFrame(), engine_context)
        assert len(result) == 0

    def test_nr_nan_tratado_como_vazio(self, engine_context: EngineContext) -> None:
        """NR com float NaN → considerado vazio → ALERTA."""
        df = _df_completo(["411110100"], [str(float("nan"))], ["0"])
        result = R066().execute(df, engine_context)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# R067 — Despesa presente (ND informado)
# ---------------------------------------------------------------------------


class TestR067:
    def test_df_com_nd_nao_gera_pendencia(self, engine_context: EngineContext) -> None:
        """Ao menos um registro com ND preenchido → nenhuma pendência."""
        df = _df_completo(["311110100"], ["0"], ["33390300"])
        result = R067().execute(df, engine_context)
        assert len(result) == 0

    def test_df_sem_nd_gera_alerta(self, engine_context: EngineContext) -> None:
        """Nenhum ND preenchido → um ALERTA."""
        df = _df_completo(["111110100", "211110100"], ["0", "0"], ["0", "0"])
        result = R067().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R067"
        assert result.iloc[0]["severidade"] == "ALERTA"

    def test_df_vazio_retorna_vazio(self, engine_context: EngineContext) -> None:
        """DataFrame vazio → nenhuma pendência."""
        result = R067().execute(pd.DataFrame(), engine_context)
        assert len(result) == 0

    def test_nd_nan_tratado_como_vazio(self, engine_context: EngineContext) -> None:
        """ND com float NaN → considerado vazio → ALERTA."""
        df = _df_completo(["311110100"], ["0"], [str(float("nan"))])
        result = R067().execute(df, engine_context)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# R068 — 8 classes contábeis presentes
# ---------------------------------------------------------------------------


class TestR068:
    def _df_8_classes(self) -> pd.DataFrame:
        contas = [f"{c}11110100" for c in range(1, 9)]
        return _df_completo(contas, ["0"] * 8, ["0"] * 8)

    def test_todas_classes_presentes_nao_gera_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Todas as 8 classes presentes → nenhuma pendência."""
        result = R068().execute(self._df_8_classes(), engine_context)
        assert len(result) == 0

    def test_classes_faltantes_geram_alerta(
        self, engine_context: EngineContext
    ) -> None:
        """Classes 6, 7, 8 ausentes → 3 pendências ALERTA."""
        df = _df_completo(
            ["111110100", "211110100", "311110100", "411110100", "511110100"],
            ["0"] * 5,
            ["0"] * 5,
        )
        result = R068().execute(df, engine_context)
        assert len(result) == 3
        assert all(r == "ALERTA" for r in result["severidade"])
        assert all(r == "R068" for r in result["regra_id"])

    def test_df_vazio_retorna_vazio(self, engine_context: EngineContext) -> None:
        """DataFrame vazio → nenhuma pendência."""
        result = R068().execute(pd.DataFrame(), engine_context)
        assert len(result) == 0

    def test_uma_classe_ausente_gera_um_alerta(
        self, engine_context: EngineContext
    ) -> None:
        """Apenas classe 8 ausente → exatamente 1 pendência."""
        contas = [f"{c}11110100" for c in range(1, 8)]
        df = _df_completo(contas, ["0"] * 7, ["0"] * 7)
        result = R068().execute(df, engine_context)
        assert len(result) == 1
        assert "Classe 8" in result.iloc[0]["conta_contabil"]


# ---------------------------------------------------------------------------
# R074 — Chave com SF ou PC
# ---------------------------------------------------------------------------


class TestR074:
    def test_linha_com_sf_nao_gera_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Linha com saldo_inicial e saldo_final → nenhuma pendência."""
        df = _df_completo(
            ["111110100"], ["0"], ["0"],
            si_d=[1000.0], sf_d=[1000.0],
            has_si=[True], has_sf=[True],
        )
        result = R074().execute(df, engine_context)
        assert len(result) == 0

    def test_linha_com_movimento_nao_gera_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Linha com saldo_inicial e movimentação → nenhuma pendência."""
        df = _df_completo(
            ["111110100"], ["0"], ["0"],
            si_d=[1000.0], mov_d=[500.0],
            has_si=[True], has_sf=[False],
        )
        result = R074().execute(df, engine_context)
        assert len(result) == 0

    def test_linha_so_com_si_gera_alerta(self, engine_context: EngineContext) -> None:
        """Linha com apenas saldo_inicial (sem SF e sem movimento) → ALERTA."""
        df = _df_completo(
            ["111110100"], ["0"], ["0"],
            si_d=[1000.0],
            has_si=[True], has_sf=[False],
        )
        result = R074().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R074"
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["conta_contabil"] == "111110100"

    def test_linha_tudo_zero_nao_gera_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Linha com todos os valores zero → sem SI, não dispara R074."""
        df = _df_completo(
            ["111110100"], ["0"], ["0"],
            has_si=[False], has_sf=[False],
        )
        result = R074().execute(df, engine_context)
        assert len(result) == 0

    def test_sf_zero_legitimo_nao_gera_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Regressão: SF=0 legítimo (linha ending_balance presente, valor zero).

        Conta encerrou zerada: SI_D=1000, todos os movimentos compensaram,
        SF_D=0.  A linha ending_balance *existe* no CSV (has_sf=True);
        comparar != 0 levaria a falso positivo.  Com o flag, não dispara.
        """
        df = _df_completo(
            ["211000000"], ["0"], ["0"],
            si_d=[1000.0], sf_d=[0.0],
            has_si=[True], has_sf=[True],  # SF existe, só está zerado
        )
        result = R074().execute(df, engine_context)
        assert len(result) == 0, (
            "R074 falso positivo: SF=0 com linha ending_balance presente "
            "não deve gerar alerta."
        )

    def test_si_zero_sem_sf_gera_alerta(
        self, engine_context: EngineContext
    ) -> None:
        """Regressão: SI_D=0 mas linha beginning_balance presente (has_si=True).

        Conta com saldo inicial zerado e sem SF nem movimentação — exportação
        incompleta independente do valor.  Comparar != 0 levaria a falso
        negativo (SI_D=0 seria tratado como 'sem SI').  Com o flag, dispara.
        """
        df = _df_completo(
            ["111110100"], ["0"], ["0"],
            si_d=[0.0],  # valor zero, mas tipo presente
            has_si=[True], has_sf=[False],
        )
        result = R074().execute(df, engine_context)
        assert len(result) == 1, (
            "R074 falso negativo: SI=0 com linha beginning_balance presente "
            "e sem SF deve gerar alerta."
        )
        assert result.iloc[0]["regra_id"] == "R074"

    def test_period_change_zero_legitimo_nao_gera_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Regressão: period_change presente com MOV=0 não deve disparar R074.

        Conta com SI e linha period_change no CSV, mas sem movimentação no
        período (valor=0) e sem SF.  O tipo está presente — exportação
        completa.  Inferir presença por != 0 levaria a falso positivo.
        Com o flag _has_period_change=True, não dispara.
        """
        df = _df_completo(
            ["311110100"], ["0"], ["0"],
            si_d=[500.0], mov_d=[0.0],  # period_change presente, valor zero
            has_si=[True], has_sf=[False], has_pc=[True],
        )
        result = R074().execute(df, engine_context)
        assert len(result) == 0, (
            "R074 falso positivo: period_change presente com valor zero "
            "não deve gerar alerta."
        )

    def test_flags_como_string_nao_geram_falso_positivo(
        self, engine_context: EngineContext
    ) -> None:
        """Regressão: flags serializados como strings pelo reader não devem
        travar o parser booleano.

        O reader_msc converte _has_* para strings "True"/"False" na passagem
        de normalização (str_cols loop).  astype(bool) trataria "False" como
        True (string não-vazia).  _parse_flag() deve resolver isso.

        Cenário: SI presente, SF ausente ("False"), MOV ausente ("False")
        → deve disparar ALERTA.
        """
        df = _df_completo(
            ["111110100"], ["0"], ["0"],
            si_d=[1000.0],
        )
        # Simula o que o reader faz: flags são strings, não bools nativos.
        df["_has_saldo_inicial"] = "True"
        df["_has_saldo_final"] = "False"   # seria True com astype(bool)!
        df["_has_period_change"] = "False"  # idem
        result = R074().execute(df, engine_context)
        assert len(result) == 1, (
            "R074: flags como string 'False' devem ser interpretados como False, "
            "não True — a regra deve disparar ALERTA."
        )
        assert result.iloc[0]["regra_id"] == "R074"

    def test_flags_numericos_string_sao_honrados(
        self, engine_context: EngineContext
    ) -> None:
        """Regressão: flags como strings "1"/"0" (round-trip CSV/export) devem
        ser interpretados corretamente por _parse_flag.

        Sem o tratamento, "1" comparado contra "true" retornaria False,
        causando falso positivo (SI presente não detectado) ou falso
        negativo (SF presente tratado como ausente).

        Cenário A: SI="1", SF="0", PC="0" → ALERTA (SI presente, SF e PC ausentes).
        Cenário B: SI="1", SF="1", PC="0" → sem alerta (SF presente).
        """
        # Cenário A: deve alertar — "1" para SI deve ser True
        df_a = _df_completo(["111110100"], ["0"], ["0"], si_d=[1000.0])
        df_a["_has_saldo_inicial"] = "1"
        df_a["_has_saldo_final"] = "0"
        df_a["_has_period_change"] = "0"
        result_a = R074().execute(df_a, engine_context)
        assert len(result_a) == 1, (
            "R074: flag '1' deve ser True — SI presente sem SF/PC deve gerar ALERTA."
        )

        # Cenário B: não deve alertar — "1" para SF deve ser True
        df_b = _df_completo(["111110100"], ["0"], ["0"], si_d=[1000.0], sf_d=[1000.0])
        df_b["_has_saldo_inicial"] = "1"
        df_b["_has_saldo_final"] = "1"
        df_b["_has_period_change"] = "0"
        result_b = R074().execute(df_b, engine_context)
        assert len(result_b) == 0, (
            "R074: flag '1' deve ser True — SI e SF presentes não deve gerar ALERTA."
        )

    def test_period_change_natureza_invalida_nao_gera_r074_no_pivot(
        self,
    ) -> None:
        """Regressão: period_change com Natureza_valor inválida não deve causar
        R074 falso positivo via _has_period_change=False.

        Cenário: uma chave tem beginning_balance válido e um period_change com
        Natureza_valor="X" (inválida).  R004 deve ser emitido para a linha
        period_change;X.  Os flags de presença devem ser calculados sobre o
        Tipo_valor *antes* do filtro df_valid, então _has_period_change=True
        — e o DataFrame pivotado não deve acionar R074 para essa chave.
        """
        from io import BytesIO

        from ranking_msc.io.reader_msc import read_msc_csv

        csv_content = (
            b"2507507EX;2025-01\n"
            b"CONTA;IC1;TIPO1;IC2;TIPO2;IC3;TIPO3;IC4;TIPO4;IC5;TIPO5;IC6;TIPO6;"
            b"Valor;Tipo_valor;Natureza_valor\n"
            b"111110200;10131;PO;;;;;;;;;;;1000.00;beginning_balance;D\n"
            b"111110200;10131;PO;;;;;;;;;;;500.00;period_change;X\n"
        )


        raw = read_msc_csv(BytesIO(csv_content))

        # R004 deve ter sido emitido para a linha period_change;X
        r004 = [i for i in raw.pre_pivot_issues if i.get("regra") == "R004"]
        assert len(r004) >= 1, "R004 deve ser emitido para Natureza_valor='X'"

        # O flag _has_period_change deve ser True — o Tipo estava presente no CSV
        assert "_has_period_change" in raw.df.columns
        assert bool(raw.df.iloc[0]["_has_period_change"]) is True, (
            "R074 regressão: _has_period_change deve ser True quando period_change "
            "está presente no CSV mesmo com Natureza_valor inválida."
        )


# ---------------------------------------------------------------------------
# R071 — Valores com > 2 decimais
# ---------------------------------------------------------------------------


class TestR071:
    def test_sem_issues_retorna_vazio(
        self, engine_context: EngineContext
    ) -> None:
        """Nenhum issue R071 em pre_pivot_issues → zero pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110100"]})
        result = R071().execute(df, engine_context)
        assert len(result) == 0

    def test_valor_com_mais_de_2_decimais_gera_info(
        self, settings: Settings
    ) -> None:
        """Issue R071 em pre_pivot_issues → pendência INFO drenada."""
        ctx = _ctx_with_issues(settings, [
            {
                "regra": "R071",
                "conta_contabil": "111110100",
                "campo": "Valor",
                "valor_encontrado": "1000.005",
                "valor_esperado": "1000.00",
                "competencia": "2024-01",
            }
        ])
        df = pd.DataFrame({"conta_contabil": ["111110100"]})
        result = R071().execute(df, ctx)
        assert len(result) == 1
        assert result.iloc[0]["regra_id"] == "R071"
        assert result.iloc[0]["severidade"] == "INFO"
        assert "1000.005" in result.iloc[0]["valor_encontrado"]

    def test_df_vazio_retorna_vazio(self, engine_context: EngineContext) -> None:
        """DataFrame vazio → nenhuma pendência (pre_pivot_issues vazio)."""
        result = R071().execute(pd.DataFrame(), engine_context)
        assert len(result) == 0

    def test_issue_de_outra_regra_ignorado(self, settings: Settings) -> None:
        """Issues de outras regras em pre_pivot_issues → R071 retorna vazio."""
        ctx = _ctx_with_issues(settings, [
            {"regra": "R005", "conta_contabil": "111110100",
             "campo": "Valor", "valor_encontrado": "abc"}
        ])
        df = pd.DataFrame({"conta_contabil": ["111110100"]})
        result = R071().execute(df, ctx)
        assert len(result) == 0

    def test_duplicatas_somadas_nao_ocultam_violacao(
        self, settings: Settings
    ) -> None:
        """Regressão: 0.005 + 0.005 = 0.01 pós-pivot não deve ocultar R071.

        O reader verifica escala no Valor bruto antes de pivot_table somar
        duplicatas.  Ambas as linhas devem gerar issues R071 independentes,
        mesmo que a soma resultante (0.01) pareça válida pós-pivot.
        """
        ctx = _ctx_with_issues(settings, [
            {
                "regra": "R071",
                "conta_contabil": "111110100",
                "campo": "Valor",
                "valor_encontrado": "0.005",
                "valor_esperado": "0.01",
                "competencia": "2024-01",
            },
            {
                "regra": "R071",
                "conta_contabil": "111110100",
                "campo": "Valor",
                "valor_encontrado": "0.005",
                "valor_esperado": "0.01",
                "competencia": "2024-01",
            },
        ])
        df = pd.DataFrame({"conta_contabil": ["111110100"]})
        result = R071().execute(df, ctx)
        assert len(result) == 2, (
            "R071 deve reportar ambas as linhas 0.005 individualmente; "
            "a soma pós-pivot (0.01) não deve suprimir os alertas."
        )
        assert all(r == "INFO" for r in result["severidade"])


# ---------------------------------------------------------------------------
# R072 — Registros atípicos por conta (outlier estatístico)
# ---------------------------------------------------------------------------


class TestR072:
    def test_distribuicao_uniforme_sem_pendencia(
        self, engine_context: EngineContext
    ) -> None:
        """Todas as contas com o mesmo número de registros → nenhuma pendência."""
        contas = [f"11111010{i}" for i in range(5)] * 3
        df = _df_completo(contas, ["0"] * 15, ["0"] * 15)
        result = R072().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_com_outlier_gera_info(self, engine_context: EngineContext) -> None:
        """Conta com muito mais registros que a média → pendência INFO."""
        # 20 contas com 1 registro cada + 1 conta com 100 registros
        # limiar = media(~5.7) + 3*std(~21.6) ≈ 70 → 100 é flagrado
        contas_base = [f"{i:09d}" for i in range(1, 21)]
        conta_outlier = ["999999999"] * 100
        contas = contas_base + conta_outlier
        df = _df_completo(contas, ["0"] * len(contas), ["0"] * len(contas))
        result = R072().execute(df, engine_context)
        assert len(result) >= 1
        assert result.iloc[0]["regra_id"] == "R072"
        assert result.iloc[0]["severidade"] == "INFO"
        assert "999999999" in result.iloc[0]["conta_contabil"]

    def test_menos_de_2_contas_retorna_vazio(
        self, engine_context: EngineContext
    ) -> None:
        """Apenas 1 conta distinta → sem outliers possíveis."""
        df = _df_completo(["111110100"] * 5, ["0"] * 5, ["0"] * 5)
        result = R072().execute(df, engine_context)
        assert len(result) == 0

    def test_df_vazio_retorna_vazio(self, engine_context: EngineContext) -> None:
        """DataFrame vazio → nenhuma pendência."""
        result = R072().execute(pd.DataFrame(), engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R073 — Valores outliers extremos (> p99 × 10)
# ---------------------------------------------------------------------------


class TestR073:
    def test_valores_normais_sem_pendencia(self, engine_context: EngineContext) -> None:
        """Valores dentro da faixa normal → nenhuma pendência."""
        contas = [f"11111010{i}" for i in range(15)]
        valores = [float(i * 1000) for i in range(1, 16)]
        df = _df_completo(contas, ["0"] * 15, ["0"] * 15, sf_d=valores)
        result = R073().execute(df, engine_context)
        assert len(result) == 0

    def test_valor_outlier_extremo_gera_info(
        self, engine_context: EngineContext
    ) -> None:
        """Valor muito acima de p99 × 10 → pendência INFO."""
        # 100 valores normais de 1000 fazem p99 ≈ 1000; limiar = 10000
        # 1 valor de 1B >> 10000 → flagrado
        contas = [f"{i:09d}" for i in range(1, 101)] + ["999999999"]
        valores = [1000.0] * 100 + [1_000_000_000.0]
        df = _df_completo(contas, ["0"] * 101, ["0"] * 101, sf_d=valores)
        result = R073().execute(df, engine_context)
        assert len(result) >= 1
        assert result.iloc[0]["regra_id"] == "R073"
        assert result.iloc[0]["severidade"] == "INFO"

    def test_menos_de_10_valores_retorna_vazio(
        self, engine_context: EngineContext
    ) -> None:
        """< 10 valores não-zero → sem threshold útil, retorna vazio."""
        df = _df_completo(["111110100"] * 5, ["0"] * 5, ["0"] * 5, sf_d=[100.0] * 5)
        result = R073().execute(df, engine_context)
        assert len(result) == 0

    def test_df_vazio_retorna_vazio(self, engine_context: EngineContext) -> None:
        """DataFrame vazio → nenhuma pendência."""
        result = R073().execute(pd.DataFrame(), engine_context)
        assert len(result) == 0
