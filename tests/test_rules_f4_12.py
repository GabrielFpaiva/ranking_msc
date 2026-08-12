"""Testes das regras F4-12: R039, R044, R045, R046, R047, R048, R063, R064, R065."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ranking_msc.rules.r039 import R039
from ranking_msc.rules.r044 import R044
from ranking_msc.rules.r045 import R045
from ranking_msc.rules.r046 import R046
from ranking_msc.rules.r047 import R047
from ranking_msc.rules.r048 import R048
from ranking_msc.rules.r063 import R063
from ranking_msc.rules.r064 import R064
from ranking_msc.rules.r065 import R065

# ---------------------------------------------------------------------------
# R039 — PO compatível com esfera do ente
# ---------------------------------------------------------------------------

def _tabela_po_mock() -> pd.DataFrame:
    """Subset representativo de tabela_po.csv com cross-esfera + ranges padrão."""
    return pd.DataFrame({
        "codigo": [
            # Federal puro
            "10101", "10102", "10111",
            # Cross-esfera municipal (dentro do range federal)
            "10131", "10132",
            # Estadual puro
            "20201", "20202",
            # Cross-esfera municipal (dentro do range estadual)
            "20231", "20232",
            # Municipal puro
            "30301", "30302", "30310",
        ],
    })


def _patch_tabela_po(mock_df: pd.DataFrame | None = None):
    """Helper para patch padronizado de load_tabela_po."""
    return patch(
        "ranking_msc.rules.r039.load_tabela_po",
        return_value=mock_df if mock_df is not None else _tabela_po_mock(),
    )


class TestR039:
    def test_po_municipal_30xxx_valido(self, engine_context):
        """PO com prefixo '3' (municipal puro) em ente municipal → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": ["30301"]})
        with _patch_tabela_po():
            result = R039().execute(df, engine_context)
        assert len(result) == 0

    def test_po_cross_municipal_10131_valido(self, engine_context):
        """PO 10131 (Município Executivo no range federal) é VÁLIDO para municipal."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": ["10131"]})
        with _patch_tabela_po():
            result = R039().execute(df, engine_context)
        assert len(result) == 0

    def test_po_cross_municipal_20231_valido(self, engine_context):
        """PO 20231 (Município no range estadual) é VÁLIDO para municipal."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": ["20231"]})
        with _patch_tabela_po():
            result = R039().execute(df, engine_context)
        assert len(result) == 0

    def test_po_federal_puro_em_municipal_gera_alerta(self, engine_context):
        """PO 10101 (Federal puro) em ente municipal → ALERTA."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": ["10101"]})
        with _patch_tabela_po():
            result = R039().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R039"

    def test_po_estadual_puro_em_municipal_gera_alerta(self, engine_context):
        """PO 20201 (Estadual puro) em ente municipal → ALERTA."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": ["20201"]})
        with _patch_tabela_po():
            result = R039().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"

    def test_po_cross_municipal_em_estadual_gera_alerta(self):
        """PO 20231 (cross-municipal) em ente estadual → ALERTA."""
        from ranking_msc.config.settings import AppSettings, Settings
        from ranking_msc.engine.executor import EngineContext
        ctx = EngineContext(
            competencia="2024-01", siconfi="250400",
            settings=Settings(app=AppSettings(esfera="estadual")),
            usuario="teste",
        )
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": ["20231"]})
        with _patch_tabela_po():
            result = R039().execute(df, ctx)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"

    def test_po_cross_municipal_em_federal_gera_alerta(self):
        """PO 10131 (cross-municipal) em ente federal → ALERTA."""
        from ranking_msc.config.settings import AppSettings, Settings
        from ranking_msc.engine.executor import EngineContext
        ctx = EngineContext(
            competencia="2024-01", siconfi="250400",
            settings=Settings(app=AppSettings(esfera="federal")),
            usuario="teste",
        )
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": ["10131"]})
        with _patch_tabela_po():
            result = R039().execute(df, ctx)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"

    def test_po_ausente_da_tabela_nao_gera_pendencia(self, engine_context):
        """PO não presente na tabela → R021 cobre; R039 não duplica."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": ["99999"]})
        with _patch_tabela_po():
            result = R039().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_po_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'po' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        assert len(R039().execute(df, engine_context)) == 0

    def test_po_vazio_ignorado(self, engine_context):
        """PO vazio/nan → ignorado, sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": [""]})
        with _patch_tabela_po():
            assert len(R039().execute(df, engine_context)) == 0

    def test_esfera_invalida_ignorada(self):
        """Esfera não reconhecida em settings → regra ignorada."""
        from ranking_msc.config.settings import AppSettings, Settings
        from ranking_msc.engine.executor import EngineContext
        ctx = EngineContext(
            competencia="2024-01", siconfi="250400",
            settings=Settings(app=AppSettings(esfera="nacional")),
            usuario="teste",
        )
        df = pd.DataFrame({"conta_contabil": ["111110200"], "po": ["10101"]})
        assert len(R039().execute(df, ctx)) == 0

    def test_multiplos_pos_detecta_invalidos(self, engine_context):
        """30301 e 10131 válidos, 10101 e 20201 inválidos para municipal."""
        df = pd.DataFrame({
            "conta_contabil": ["111110200", "111110201", "111110202", "111110203"],
            "po": ["30301", "10131", "10101", "20201"],
        })
        with _patch_tabela_po():
            result = R039().execute(df, engine_context)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# R044 — NR valorizável
# ---------------------------------------------------------------------------

def _tabela_nr_mock() -> pd.DataFrame:
    return pd.DataFrame({
        "codigo": ["10000000", "11000000", "11100000", "11110000"],
        "valorizavel": ["NÃO", "NÃO", "NÃO", "SIM"],
    })


class TestR044:
    def test_nr_valorizavel_sem_pendencia(self, engine_context):
        """NR valorizável → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["511100200"], "nr": ["11110000"]})
        with patch("ranking_msc.rules.r044.load_tabela_nr", return_value=_tabela_nr_mock()):
            result = R044().execute(df, engine_context)
        assert len(result) == 0

    def test_nr_sintetica_gera_alerta(self, engine_context):
        """NR sintética (valorizavel=NÃO) → ALERTA."""
        df = pd.DataFrame({"conta_contabil": ["511100200"], "nr": ["11000000"]})
        with patch("ranking_msc.rules.r044.load_tabela_nr", return_value=_tabela_nr_mock()):
            result = R044().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R044"

    def test_sem_nr_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'nr' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["511100200"]})
        assert len(R044().execute(df, engine_context)) == 0

    def test_nr_vazio_ignorado(self, engine_context):
        """NR vazia → ignorada."""
        df = pd.DataFrame({"conta_contabil": ["511100200"], "nr": [""]})
        with patch("ranking_msc.rules.r044.load_tabela_nr", return_value=_tabela_nr_mock()):
            assert len(R044().execute(df, engine_context)) == 0

    def test_nr_ausente_na_tabela_nao_gera_pendencia(self, engine_context):
        """NR não presente na tabela → R026 já cobre; R044 não gera pendência adicional."""
        df = pd.DataFrame({"conta_contabil": ["511100200"], "nr": ["99999999"]})
        with patch("ranking_msc.rules.r044.load_tabela_nr", return_value=_tabela_nr_mock()):
            assert len(R044().execute(df, engine_context)) == 0


# ---------------------------------------------------------------------------
# R045 — ND último nível
# ---------------------------------------------------------------------------

def _tabela_nd_mock() -> pd.DataFrame:
    return pd.DataFrame({
        "codigo": ["30000000", "31000000", "31200000", "31300000", "33504300", "33504399"],
        "nivel": [
            "Superior 1º Nível - Classe",
            "Superior 2º Nível - Grupo",
            "Último 3º Nível - Modalidade",
            "Superior 3º Nível - Modalidade",
            "Superior 4º Nível - Elemento",
            "Superior 5º Nível - Subelemento",
        ],
        "nome": [
            "DESPESAS CORRENTES",
            "PESSOAL E ENCARGOS",
            "TRANSF. À UNIÃO",
            "TRANSF. A ESTADOS",
            "SUBVENÇÕES SOCIAIS",
            "SUBELEMENTO DESCONHECIDO",
        ],
    })


class TestR045:
    def test_nd_ultimo_nivel_sem_pendencia(self, engine_context):
        """ND de último nível → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["631200000"], "nd": ["31200000"]})
        with patch("ranking_msc.rules.r045.load_tabela_nd", return_value=_tabela_nd_mock()):
            result = R045().execute(df, engine_context)
        assert len(result) == 0

    def test_nd_superior_gera_alerta(self, engine_context):
        """ND de nível Superior → ALERTA."""
        df = pd.DataFrame({"conta_contabil": ["631200000"], "nd": ["30000000"]})
        with patch("ranking_msc.rules.r045.load_tabela_nd", return_value=_tabela_nd_mock()):
            result = R045().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R045"

    def test_sem_nd_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'nd' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["631200000"]})
        assert len(R045().execute(df, engine_context)) == 0

    def test_nd_ausente_na_tabela_nao_gera_pendencia(self, engine_context):
        """ND ausente na tabela → R027 cobre; R045 ignora."""
        df = pd.DataFrame({"conta_contabil": ["631200000"], "nd": ["99999999"]})
        with patch("ranking_msc.rules.r045.load_tabela_nd", return_value=_tabela_nd_mock()):
            assert len(R045().execute(df, engine_context)) == 0

    def test_nd_superior_de_elemento_nao_gera_pendencia(self, engine_context):
        """ND de elemento com subelemento 00 é envio válido para o Siconfi."""
        df = pd.DataFrame({"conta_contabil": ["633350430"], "nd": ["33504300"]})
        with patch("ranking_msc.rules.r045.load_tabela_nd", return_value=_tabela_nd_mock()):
            result = R045().execute(df, engine_context)
        assert len(result) == 0

    def test_nd_superior_de_modalidade_gera_alerta(self, engine_context):
        """ND parada na modalidade continua sendo envio indevido."""
        df = pd.DataFrame({"conta_contabil": ["631300000"], "nd": ["31300000"]})
        with patch("ranking_msc.rules.r045.load_tabela_nd", return_value=_tabela_nd_mock()):
            result = R045().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"

    def test_nd_superior_desconhecido_gera_alerta(self, engine_context):
        """Nível 'Superior' fora da lista de conhecidos cai do lado seguro (pendência)."""
        df = pd.DataFrame({"conta_contabil": ["633350439"], "nd": ["33504399"]})
        with patch("ranking_msc.rules.r045.load_tabela_nd", return_value=_tabela_nd_mock()):
            result = R045().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"


# ---------------------------------------------------------------------------
# R046 — ND não genérica
# ---------------------------------------------------------------------------

def _tabela_nd_generica_mock() -> pd.DataFrame:
    return pd.DataFrame({
        "codigo": ["33300000", "33390000", "33391000"],
        "nivel": ["Superior 1º Nível", "Último", "Último"],
        "nome": ["OUTRAS DESP. CORRENTES", "Outras Desp. Correntes", "Modalidade Genérica"],
    })


class TestR046:
    def test_nd_especifica_sem_pendencia(self, engine_context):
        """ND específica (nome sem 'Genéric') → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["633390000"], "nd": ["33390000"]})
        with patch(
            "ranking_msc.rules.r046.load_tabela_nd",
            return_value=_tabela_nd_generica_mock(),
        ):
            result = R046().execute(df, engine_context)
        assert len(result) == 0

    def test_nd_generica_gera_alerta(self, engine_context):
        """ND com 'Genérica' no nome → INFO."""
        df = pd.DataFrame({"conta_contabil": ["633391000"], "nd": ["33391000"]})
        with patch(
            "ranking_msc.rules.r046.load_tabela_nd",
            return_value=_tabela_nd_generica_mock(),
        ):
            result = R046().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "INFO"
        assert result.iloc[0]["regra_id"] == "R046"

    def test_sem_nd_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'nd' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["633391000"]})
        assert len(R046().execute(df, engine_context)) == 0

    def test_r046_fora_da_pontuacao(self):
        """A regra não penaliza o score — falso positivo confirmado em 11/08/2026."""
        assert R046.is_scoring is False


# ---------------------------------------------------------------------------
# R047 — Soma subelementos ND = elemento pai
# ---------------------------------------------------------------------------

class TestR047:
    def _df_base(
        self,
        nd_element: str,
        val_elem: float,
        nd_subs: list[str],
        vals_subs: list[float],
    ) -> pd.DataFrame:
        rows = []
        rows.append({
            "nd": nd_element,
            "saldo_final_debito": val_elem,
            "saldo_final_credito": 0.0,
        })
        for nd, val in zip(nd_subs, vals_subs, strict=True):
            rows.append({
                "nd": nd,
                "saldo_final_debito": val,
                "saldo_final_credito": 0.0,
            })
        return pd.DataFrame(rows)

    def test_subs_iguais_elemento_sem_pendencia(self, engine_context):
        """Subelementos somam exatamente ao elemento pai → sem pendências."""
        df = self._df_base(
            "33100100", 1000.0,
            ["33100101", "33100102"], [600.0, 400.0],
        )
        result = R047().execute(df, engine_context)
        assert len(result) == 0

    def test_subs_divergem_gera_alerta(self, engine_context):
        """Subelementos somam valor diferente do elemento pai → INFO."""
        df = self._df_base(
            "33100100", 1000.0,
            ["33100101", "33100102"], [600.0, 300.0],
        )
        result = R047().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "INFO"
        assert result.iloc[0]["regra_id"] == "R047"

    def test_r047_fora_da_pontuacao(self):
        """Não há relação aritmética exigível entre elemento e subelementos."""
        assert R047.is_scoring is False

    def test_apenas_elemento_sem_subs_sem_pendencia(self, engine_context):
        """Elemento pai sem subelementos → sem pendências (regra não se aplica)."""
        df = pd.DataFrame({
            "nd": ["33100100"],
            "saldo_final_debito": [1000.0],
            "saldo_final_credito": [0.0],
        })
        result = R047().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_nd_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'nd' → sem pendências."""
        df = pd.DataFrame({"saldo_final_debito": [100.0], "saldo_final_credito": [0.0]})
        assert len(R047().execute(df, engine_context)) == 0

    def test_tolerancia_centavo_aceita(self, engine_context):
        """Diferença ≤ 0.01 dentro da tolerância → sem pendências."""
        df = self._df_base(
            "33100100", 1000.00,
            ["33100101", "33100102"], [600.00, 400.005],
        )
        result = R047().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R048 — FR 1º dígito
# ---------------------------------------------------------------------------

class TestR048:
    def test_fr_prefixo_1_valido(self, engine_context):
        """FR com prefixo '1' (corrente) → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "fr": ["1500"]})
        result = R048().execute(df, engine_context)
        assert len(result) == 0

    def test_fr_prefixo_2_valido(self, engine_context):
        """FR com prefixo '2' (anterior) → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "fr": ["2100"]})
        assert len(R048().execute(df, engine_context)) == 0

    def test_fr_prefixo_9_valido(self, engine_context):
        """FR com prefixo '9' (condicionado) → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "fr": ["9001"]})
        assert len(R048().execute(df, engine_context)) == 0

    def test_fr_prefixo_invalido_gera_alerta(self, engine_context):
        """FR com prefixo '3' (inválido) → ALERTA."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "fr": ["3500"]})
        result = R048().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R048"

    def test_sem_fr_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'fr' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        assert len(R048().execute(df, engine_context)) == 0

    def test_fr_vazio_ignorado(self, engine_context):
        """FR vazio → ignorado."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "fr": [""]})
        assert len(R048().execute(df, engine_context)) == 0


# ---------------------------------------------------------------------------
# R063 — DC só em contas permitidas (ID_IC=8)
# ---------------------------------------------------------------------------

def _pcasp_com_id_ic() -> pd.DataFrame:
    return pd.DataFrame({
        "conta_contabil": ["211410102", "211410600", "111110200"],
        "id_ic": ["8", "8", "0"],
        "nat_saldo": ["Credora", "Credora", "Devedora"],
        "status": ["Ativa", "Ativa", "Ativa"],
        "nivel": ["Último", "Último", "Superior"],
        "ind_sf": ["-", "-", "-"],
    })


class TestR063:
    def test_dc_em_conta_permitida_sem_pendencia(self, engine_context):
        """DC em conta com ID_IC=8 → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["211410102"], "dc": ["1"]})
        with patch("ranking_msc.rules.r063.load_pcasp", return_value=_pcasp_com_id_ic()):
            result = R063().execute(df, engine_context)
        assert len(result) == 0

    def test_dc_em_conta_nao_permitida_gera_erro(self, engine_context):
        """DC em conta sem ID_IC=8 → ERRO."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "dc": ["1"]})
        with patch("ranking_msc.rules.r063.load_pcasp", return_value=_pcasp_com_id_ic()):
            result = R063().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"
        assert result.iloc[0]["regra_id"] == "R063"

    def test_sem_dc_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'dc' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110200"]})
        assert len(R063().execute(df, engine_context)) == 0

    def test_dc_vazio_ignorado(self, engine_context):
        """DC vazio → ignorado."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "dc": [""]})
        with patch("ranking_msc.rules.r063.load_pcasp", return_value=_pcasp_com_id_ic()):
            assert len(R063().execute(df, engine_context)) == 0

    def test_pcasp_sem_id_ic_ignora_regra(self, engine_context):
        """PCASP sem coluna 'id_ic' → regra ignorada sem erro."""
        pcasp_sem_id = pd.DataFrame({"conta_contabil": ["211410102"]})
        df = pd.DataFrame({"conta_contabil": ["111110200"], "dc": ["1"]})
        with patch("ranking_msc.rules.r063.load_pcasp", return_value=pcasp_sem_id):
            result = R063().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R064 — CO × tipo de conta
# ---------------------------------------------------------------------------

class TestR064:
    def test_co_despesa_em_classe1_sem_pendencia(self, engine_context):
        """CO de despesa (1500) em conta classe 1 (Ativo) → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "co": ["1500"]})
        result = R064().execute(df, engine_context)
        assert len(result) == 0

    def test_co_despesa_em_classe3_gera_alerta(self, engine_context):
        """CO de despesa (1500) em conta classe 3 (VPD) → INFO."""
        df = pd.DataFrame({"conta_contabil": ["311110200"], "co": ["1500"]})
        result = R064().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "INFO"
        assert result.iloc[0]["regra_id"] == "R064"

    def test_co_despesa_em_classe5_sem_pendencia(self, engine_context):
        """CO de despesa em conta classe 5 (orçamentário) → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["511110200"], "co": ["2001"]})
        assert len(R064().execute(df, engine_context)) == 0

    def test_co_despesa_em_classe4_gera_alerta(self, engine_context):
        """CO de despesa (1500) em conta classe 4 (VPA) → INFO."""
        df = pd.DataFrame({"conta_contabil": ["411110200"], "co": ["1500"]})
        result = R064().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "INFO"
        assert result.iloc[0]["regra_id"] == "R064"

    def test_co_receita_em_classe4_sem_pendencia(self, engine_context):
        """CO de receita (5001) em conta classe 4 (VPA) → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["411110200"], "co": ["5001"]})
        assert len(R064().execute(df, engine_context)) == 0

    def test_co_receita_em_classe3_gera_alerta(self, engine_context):
        """CO de receita (5001) em conta classe 3 (VPD) → INFO."""
        df = pd.DataFrame({"conta_contabil": ["311110200"], "co": ["5001"]})
        result = R064().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "INFO"

    def test_co_fora_dos_blocos_monitorados_nao_gera_pendencia(self, engine_context):
        """CO fora das faixas monitoradas → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["111110200"], "co": ["3001"]})
        assert len(R064().execute(df, engine_context)) == 0

    def test_sem_co_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'co' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["311110200"]})
        assert len(R064().execute(df, engine_context)) == 0

    def test_r064_fora_da_pontuacao(self):
        """O leiaute prevê CO em conta de controle (ex.: 721900000, ID_IC 5)."""
        assert R064.is_scoring is False


# ---------------------------------------------------------------------------
# R065 — FS combinação atípica
# ---------------------------------------------------------------------------

def _tabela_fs_mock() -> pd.DataFrame:
    return pd.DataFrame({
        "funcao": ["01", "01", "02", "02"],
        "subfuncao": ["031", "032", "061", "062"],
    })


class TestR065:
    def test_combinacao_tipica_sem_pendencia(self, engine_context):
        """Combinação (01, 031) típica → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["311110200"], "fs": ["01031"]})
        with patch("ranking_msc.rules.r065.load_tabela_fs", return_value=_tabela_fs_mock()):
            result = R065().execute(df, engine_context)
        assert len(result) == 0

    def test_combinacao_atipica_gera_info(self, engine_context):
        """Combinação (01, 061) atípica mas individualmente válida → INFO."""
        df = pd.DataFrame({"conta_contabil": ["311110200"], "fs": ["01061"]})
        with patch("ranking_msc.rules.r065.load_tabela_fs", return_value=_tabela_fs_mock()):
            result = R065().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "INFO"
        assert result.iloc[0]["regra_id"] == "R065"

    def test_fs_invalida_nao_gera_pendencia_aqui(self, engine_context):
        """FS com função/subfunção inválidos → coberta por R028, não por R065."""
        df = pd.DataFrame({"conta_contabil": ["311110200"], "fs": ["99999"]})
        with patch("ranking_msc.rules.r065.load_tabela_fs", return_value=_tabela_fs_mock()):
            assert len(R065().execute(df, engine_context)) == 0

    def test_sem_fs_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'fs' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["311110200"]})
        with patch("ranking_msc.rules.r065.load_tabela_fs", return_value=_tabela_fs_mock()):
            assert len(R065().execute(df, engine_context)) == 0

    def test_fs_vazio_ignorado(self, engine_context):
        """FS vazio → ignorado."""
        df = pd.DataFrame({"conta_contabil": ["311110200"], "fs": [""]})
        with patch("ranking_msc.rules.r065.load_tabela_fs", return_value=_tabela_fs_mock()):
            assert len(R065().execute(df, engine_context)) == 0

    def test_is_scoring_false(self):
        """R065 é INFO-only: deve estar excluída do cálculo de pontuação."""
        assert R065.is_scoring is False
