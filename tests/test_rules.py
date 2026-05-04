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
from ranking_msc.rules.r038 import R038
from ranking_msc.rules.r053 import R053
from ranking_msc.rules.r061 import R061
from ranking_msc.rules.r062 import R062
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
