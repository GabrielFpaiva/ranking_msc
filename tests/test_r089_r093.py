"""Testes das regras F4-17: R089, R090, R091, R092, R093.

Cobre as 5 regras SIGEF de IC detalhamento faltante:
    - R089: Receita orçamentária (id_ic=6) sem FR (SIGEF V13)
    - R090: Receita orçamentária (id_ic=6) sem NR (SIGEF V14)
    - R091: Despesa orçamentária (id_ic=7/9) sem ND (SIGEF V15)
    - R092: Despesa orçamentária (id_ic=7/9) sem FS (SIGEF V16)
    - R093: Despesa orçamentária (id_ic=7/9) sem FR (SIGEF V17)

As contas-alvo são das classes 5/6 (orçamentárias), não classes 3/4.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from ranking_msc.rules.r089 import R089
from ranking_msc.rules.r090 import R090
from ranking_msc.rules.r091 import R091
from ranking_msc.rules.r092 import R092
from ranking_msc.rules.r093 import R093

# ---------------------------------------------------------------------------
# Helpers compartilhados
# ---------------------------------------------------------------------------

# Contas reais do PCASP com id_ic=6 (receita orçamentária, classes 5/6)
_CONTA_RECEITA_1 = "521110000"
_CONTA_RECEITA_2 = "621100000"

# Contas reais do PCASP com id_ic=7 (despesa orçamentária, classes 5/6/7)
_CONTA_DESPESA_7_1 = "522110100"
_CONTA_DESPESA_7_2 = "622110100"

# Conta com id_ic=9 (despesa com RP)
_CONTA_DESPESA_9 = "622310100"

# Conta patrimonial (classe 1) com id_ic=0 — fora do escopo de todas as regras
_CONTA_PATRIMONIAL = "111110100"


def _pcasp_com_id_ic(contas: list[str], id_ics: list[str]) -> pd.DataFrame:
    """Constrói stub de PCASP com colunas conta_contabil e id_ic."""
    return pd.DataFrame({
        "conta_contabil": contas,
        "id_ic": id_ics,
        "nivel": ["Último"] * len(contas),
        "status": ["Ativa"] * len(contas),
    })


def _pcasp_sem_id_ic() -> pd.DataFrame:
    """PCASP sem coluna id_ic para testar graceful degradation."""
    return pd.DataFrame({
        "conta_contabil": [_CONTA_RECEITA_1, _CONTA_DESPESA_7_1],
        "nivel": ["Último", "Último"],
        "status": ["Ativa", "Ativa"],
    })


# ---------------------------------------------------------------------------
# R089 — Receita orçamentária sem FR (id_ic=6)
# ---------------------------------------------------------------------------

class TestR089:

    def test_receita_com_fr_preenchido_sem_pendencia(self, engine_context):
        """Conta de receita (id_ic=6) com FR preenchido → sem pendências."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["6"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "fr": ["1500"]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 0

    def test_receita_sem_fr_gera_alerta(self, engine_context):
        """Conta de receita com id_ic=6 e FR vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["6"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "fr": [""]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R089"
        assert _CONTA_RECEITA_1 in result.iloc[0]["conta_contabil"]

    def test_receita_fr_zero_gera_alerta(self, engine_context):
        """FR '0' é considerado vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["6"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "fr": ["0"]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 1

    def test_conta_id_ic_diferente_nao_gera_pendencia(self, engine_context):
        """Conta com id_ic=1 (fora do escopo R089) → sem pendências."""
        pcasp = _pcasp_com_id_ic([_CONTA_PATRIMONIAL], ["1"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_PATRIMONIAL], "fr": [""]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 0

    def test_conta_despesa_com_id_ic_7_nao_afeta_r089(self, engine_context):
        """Conta de despesa (id_ic=7) com FR vazio → R089 não flagra."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["7"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "fr": [""]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_coluna_fr_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'fr' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1]})
        assert len(R089().execute(df, engine_context)) == 0

    def test_pcasp_sem_id_ic_ignora_regra(self, engine_context):
        """PCASP sem coluna 'id_ic' → regra desativada graciosamente."""
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "fr": [""]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=_pcasp_sem_id_ic()):
            result = R089().execute(df, engine_context)
        assert len(result) == 0

    def test_receita_id_ic_4_fora_do_escopo(self, engine_context):
        """Conta com id_ic=4 (não é leiaute receita) → sem pendências."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["4"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "fr": [""]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 0

    def test_multiplas_contas_detecta_apenas_violadoras(self, engine_context):
        """Duas contas: uma com FR, uma sem → apenas a sem FR é flagrada."""
        pcasp = _pcasp_com_id_ic(
            [_CONTA_RECEITA_1, _CONTA_RECEITA_2], ["6", "6"],
        )
        df = pd.DataFrame({
            "conta_contabil": [_CONTA_RECEITA_1, _CONTA_RECEITA_2],
            "fr": ["1500", ""],
        })
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 1
        assert _CONTA_RECEITA_2 in result.iloc[0]["conta_contabil"]


# ---------------------------------------------------------------------------
# R090 — Receita orçamentária sem NR (id_ic com NR obrigatório)
# ---------------------------------------------------------------------------

class TestR090:

    def test_receita_com_nr_preenchida_sem_pendencia(self, engine_context):
        """Conta de receita com NR preenchida → sem pendências."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["6"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "nr": ["17000000"]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=pcasp):
            result = R090().execute(df, engine_context)
        assert len(result) == 0

    def test_receita_sem_nr_gera_alerta(self, engine_context):
        """Conta de receita com id_ic exigindo NR e NR vazia → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["6"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "nr": [""]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=pcasp):
            result = R090().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R090"

    def test_conta_id_ic_sem_nr_nao_gera_pendencia(self, engine_context):
        """Conta com id_ic=4 (sem NR) → sem pendências mesmo com NR vazia."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["4"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "nr": [""]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=pcasp):
            result = R090().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_coluna_nr_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'nr' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1]})
        assert len(R090().execute(df, engine_context)) == 0

    def test_pcasp_sem_id_ic_ignora_regra(self, engine_context):
        """PCASP sem coluna 'id_ic' → regra desativada graciosamente."""
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "nr": [""]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=_pcasp_sem_id_ic()):
            result = R090().execute(df, engine_context)
        assert len(result) == 0

    def test_nr_nan_string_gera_alerta(self, engine_context):
        """NR 'nan' (string) é considerado vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["6"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "nr": ["nan"]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=pcasp):
            result = R090().execute(df, engine_context)
        assert len(result) == 1

    def test_despesa_sem_nr_nao_afeta_r090(self, engine_context):
        """Conta de despesa (id_ic=7, não exige NR) → R090 não flagra."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["7"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "nr": [""]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=pcasp):
            result = R090().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R091 — Despesa orçamentária sem ND (id_ic com ND obrigatório)
# ---------------------------------------------------------------------------

class TestR091:

    def test_despesa_com_nd_preenchida_sem_pendencia(self, engine_context):
        """Conta de despesa com ND preenchida → sem pendências."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["7"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "nd": ["33900000"]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=pcasp):
            result = R091().execute(df, engine_context)
        assert len(result) == 0

    def test_despesa_sem_nd_gera_alerta(self, engine_context):
        """Conta de despesa com id_ic exigindo ND e ND vazia → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["7"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "nd": [""]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=pcasp):
            result = R091().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R091"
        assert _CONTA_DESPESA_7_1 in result.iloc[0]["conta_contabil"]

    def test_conta_id_ic_sem_nd_nao_gera_pendencia(self, engine_context):
        """Conta com id_ic=4 (sem ND) → sem pendências."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["4"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "nd": [""]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=pcasp):
            result = R091().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_coluna_nd_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'nd' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1]})
        assert len(R091().execute(df, engine_context)) == 0

    def test_pcasp_sem_id_ic_ignora_regra(self, engine_context):
        """PCASP sem coluna 'id_ic' → regra desativada graciosamente."""
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "nd": [""]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=_pcasp_sem_id_ic()):
            result = R091().execute(df, engine_context)
        assert len(result) == 0

    def test_receita_com_id_ic_6_nao_afeta_r091(self, engine_context):
        """Conta de receita (id_ic=6, não exige ND) → R091 não flagra."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["6"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "nd": [""]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=pcasp):
            result = R091().execute(df, engine_context)
        assert len(result) == 0

    def test_id_ic_9_com_nd_vazia_gera_alerta(self, engine_context):
        """id_ic=9 também exige ND → ALERTA quando ND vazia."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_9], ["9"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_9], "nd": ["0"]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=pcasp):
            result = R091().execute(df, engine_context)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# R092 — Despesa orçamentária sem FS (id_ic com FS obrigatório)
# ---------------------------------------------------------------------------

class TestR092:

    def test_despesa_com_fs_preenchida_sem_pendencia(self, engine_context):
        """Conta de despesa com FS preenchida → sem pendências."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["7"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "fs": ["08244"]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=pcasp):
            result = R092().execute(df, engine_context)
        assert len(result) == 0

    def test_despesa_sem_fs_gera_alerta(self, engine_context):
        """Conta de despesa com id_ic exigindo FS e FS vazia → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["7"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "fs": [""]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=pcasp):
            result = R092().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R092"

    def test_conta_id_ic_sem_fs_nao_gera_pendencia(self, engine_context):
        """Conta com id_ic=4 (sem FS) → sem pendências."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["4"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "fs": [""]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=pcasp):
            result = R092().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_coluna_fs_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'fs' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1]})
        assert len(R092().execute(df, engine_context)) == 0

    def test_pcasp_sem_id_ic_ignora_regra(self, engine_context):
        """PCASP sem coluna 'id_ic' → regra desativada graciosamente."""
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "fs": [""]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=_pcasp_sem_id_ic()):
            result = R092().execute(df, engine_context)
        assert len(result) == 0

    def test_receita_com_id_ic_6_nao_afeta_r092(self, engine_context):
        """Conta de receita (id_ic=6, não exige FS) → R092 não flagra."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["6"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "fs": [""]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=pcasp):
            result = R092().execute(df, engine_context)
        assert len(result) == 0

    def test_fs_zero_gera_alerta(self, engine_context):
        """FS '0' é considerada vazia → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_9], ["9"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_9], "fs": ["0"]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=pcasp):
            result = R092().execute(df, engine_context)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# R093 — Despesa orçamentária sem FR (id_ic=7/9)
# ---------------------------------------------------------------------------

class TestR093:

    def test_despesa_com_fr_preenchido_sem_pendencia(self, engine_context):
        """Conta de despesa com FR preenchido → sem pendências."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["7"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "fr": ["1500"]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 0

    def test_despesa_sem_fr_gera_alerta(self, engine_context):
        """Conta de despesa com id_ic=7 e FR vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["7"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "fr": [""]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R093"
        assert _CONTA_DESPESA_7_1 in result.iloc[0]["conta_contabil"]

    def test_conta_id_ic_sem_fr_nao_gera_pendencia(self, engine_context):
        """Conta com id_ic=1 (sem FR) → sem pendências mesmo com FR vazio."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["1"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "fr": [""]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_coluna_fr_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'fr' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1]})
        assert len(R093().execute(df, engine_context)) == 0

    def test_pcasp_sem_id_ic_ignora_regra(self, engine_context):
        """PCASP sem coluna 'id_ic' → regra desativada graciosamente."""
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "fr": [""]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=_pcasp_sem_id_ic()):
            result = R093().execute(df, engine_context)
        assert len(result) == 0

    def test_receita_com_id_ic_6_nao_afeta_r093(self, engine_context):
        """Conta de receita (id_ic=6) com FR vazio → R093 não flagra."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["6"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "fr": [""]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 0

    def test_fr_zero_gera_alerta(self, engine_context):
        """FR '0' é considerado vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["7"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "fr": ["0"]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 1

    def test_multiplas_despesas_detecta_violadoras(self, engine_context):
        """3 despesas: uma com FR, duas sem → apenas as sem FR são flagradas."""
        pcasp = _pcasp_com_id_ic(
            [_CONTA_DESPESA_7_1, _CONTA_DESPESA_7_2, _CONTA_DESPESA_9],
            ["7", "7", "9"],
        )
        df = pd.DataFrame({
            "conta_contabil": [_CONTA_DESPESA_7_1, _CONTA_DESPESA_7_2, _CONTA_DESPESA_9],
            "fr": ["1500", "", "nan"],
        })
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Regressão — IC vazia uppercase e float NaN (bug ic_mask_informada)
# ---------------------------------------------------------------------------

class TestICNormalizacaoCaseInsensitive:
    """Garante que None, float NaN e sentinelas uppercase são tratados como vazio."""

    def test_r089_fr_float_nan_gera_alerta(self, engine_context):
        """R089: FR como float NaN (pandas) deve ser tratado como vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["6"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "fr": [float("nan")]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 1

    def test_r090_nr_uppercase_nan_gera_alerta(self, engine_context):
        """R090: NR como string 'NAN' uppercase deve ser tratado como vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_RECEITA_1], ["6"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_RECEITA_1], "nr": ["NAN"]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=pcasp):
            result = R090().execute(df, engine_context)
        assert len(result) == 1

    def test_r091_nd_pd_na_gera_alerta(self, engine_context):
        """R091: ND como pd.NA deve ser tratado como vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["7"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "nd": [pd.NA]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=pcasp):
            result = R091().execute(df, engine_context)
        assert len(result) == 1

    def test_r092_fs_float_nan_gera_alerta(self, engine_context):
        """R092: FS como float NaN deve ser tratado como vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_7_1], ["7"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_7_1], "fs": [float("nan")]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=pcasp):
            result = R092().execute(df, engine_context)
        assert len(result) == 1

    def test_r093_fr_uppercase_nan_gera_alerta(self, engine_context):
        """R093: FR como string 'NAN' uppercase deve ser tratado como vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic([_CONTA_DESPESA_9], ["9"])
        df = pd.DataFrame({"conta_contabil": [_CONTA_DESPESA_9], "fr": ["NAN"]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 1
