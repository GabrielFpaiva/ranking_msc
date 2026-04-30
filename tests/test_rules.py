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
