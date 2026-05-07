"""Testes das regras F4-17: R089, R090, R091, R092, R093.

Cobre as 5 regras SIGEF de IC detalhamento faltante:
    - R089: Receita (classe 4 / VPA) sem FR (SIGEF V13)
    - R090: Receita (classe 4 / VPA) sem NR (SIGEF V14)
    - R091: Despesa (classe 3 / VPD) sem ND (SIGEF V15)
    - R092: Despesa (classe 3 / VPD) sem FS (SIGEF V16)
    - R093: Despesa (classe 3 / VPD) sem FR (SIGEF V17)
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
        "conta_contabil": ["411000000", "311000000"],
        "nivel": ["Último", "Último"],
        "status": ["Ativa", "Ativa"],
    })


# ---------------------------------------------------------------------------
# R089 — Receita sem FR (classe 4, id_ic com FR obrigatório)
# ---------------------------------------------------------------------------

class TestR089:
    # id_ic=6 -> IC_MAP[6] = ["PO","FR","CO","NR"] → exige FR
    # id_ic=4 -> IC_MAP[4] = ["PO","FP","FR","CO"]  → exige FR
    # id_ic=1 -> IC_MAP[1] = ["PO"]               → NÃO exige FR

    def test_receita_com_fr_preenchido_sem_pendencia(self, engine_context):
        """Conta de receita (classe 4) com FR preenchido → sem pendências."""
        pcasp = _pcasp_com_id_ic(["411000000"], ["6"])
        df = pd.DataFrame({"conta_contabil": ["411000000"], "fr": ["1500"]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 0

    def test_receita_sem_fr_gera_alerta(self, engine_context):
        """Conta de receita com id_ic exigindo FR e FR vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic(["411000000"], ["6"])
        df = pd.DataFrame({"conta_contabil": ["411000000"], "fr": [""]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R089"
        assert "411000000" in result.iloc[0]["conta_contabil"]

    def test_receita_fr_zero_gera_alerta(self, engine_context):
        """FR '0' é considerado vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic(["411000000"], ["4"])
        df = pd.DataFrame({"conta_contabil": ["411000000"], "fr": ["0"]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 1

    def test_receita_id_ic_sem_fr_nao_gera_pendencia(self, engine_context):
        """Conta de receita com id_ic=1 (só PO, sem FR) → sem pendências."""
        pcasp = _pcasp_com_id_ic(["411000000"], ["1"])
        df = pd.DataFrame({"conta_contabil": ["411000000"], "fr": [""]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 0

    def test_despesa_sem_fr_nao_afeta_r089(self, engine_context):
        """Conta de despesa (classe 3) com FR vazio → R089 não flagra."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["7"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "fr": [""]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_coluna_fr_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'fr' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["411000000"]})
        assert len(R089().execute(df, engine_context)) == 0

    def test_pcasp_sem_id_ic_ignora_regra(self, engine_context):
        """PCASP sem coluna 'id_ic' → regra desativada graciosamente."""
        df = pd.DataFrame({"conta_contabil": ["411000000"], "fr": [""]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=_pcasp_sem_id_ic()):
            result = R089().execute(df, engine_context)
        assert len(result) == 0

    def test_df_sem_contas_receita_retorna_vazio(self, engine_context):
        """DataFrame só com contas classe 1/2 → sem pendências."""
        pcasp = _pcasp_com_id_ic(["111000000"], ["4"])
        df = pd.DataFrame({"conta_contabil": ["111000000"], "fr": [""]})
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 0

    def test_multiplas_contas_detecta_apenas_violadoras(self, engine_context):
        """Duas contas: uma com FR, uma sem → apenas a sem FR é flagrada."""
        pcasp = _pcasp_com_id_ic(["411000000", "411000001"], ["6", "6"])
        df = pd.DataFrame({
            "conta_contabil": ["411000000", "411000001"],
            "fr": ["1500", ""],
        })
        with patch("ranking_msc.rules.r089.load_pcasp", return_value=pcasp):
            result = R089().execute(df, engine_context)
        assert len(result) == 1
        assert "411000001" in result.iloc[0]["conta_contabil"]


# ---------------------------------------------------------------------------
# R090 — Receita sem NR (classe 4, id_ic com NR obrigatório)
# ---------------------------------------------------------------------------

class TestR090:
    # id_ic=6 -> IC_MAP[6] = ["PO","FR","CO","NR"] → exige NR
    # id_ic=9 -> IC_MAP[9] = [...,"NR",...,"AI"]   → exige NR
    # id_ic=4 -> IC_MAP[4] = ["PO","FP","FR","CO"] → NÃO exige NR

    def test_receita_com_nr_preenchida_sem_pendencia(self, engine_context):
        """Conta de receita com NR preenchida → sem pendências."""
        pcasp = _pcasp_com_id_ic(["411000000"], ["6"])
        df = pd.DataFrame({"conta_contabil": ["411000000"], "nr": ["17000000"]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=pcasp):
            result = R090().execute(df, engine_context)
        assert len(result) == 0

    def test_receita_sem_nr_gera_alerta(self, engine_context):
        """Conta de receita com id_ic exigindo NR e NR vazia → ALERTA."""
        pcasp = _pcasp_com_id_ic(["411000000"], ["6"])
        df = pd.DataFrame({"conta_contabil": ["411000000"], "nr": [""]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=pcasp):
            result = R090().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R090"

    def test_receita_id_ic_sem_nr_nao_gera_pendencia(self, engine_context):
        """Conta com id_ic=4 (sem NR) → sem pendências mesmo com NR vazia."""
        pcasp = _pcasp_com_id_ic(["411000000"], ["4"])
        df = pd.DataFrame({"conta_contabil": ["411000000"], "nr": [""]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=pcasp):
            result = R090().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_coluna_nr_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'nr' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["411000000"]})
        assert len(R090().execute(df, engine_context)) == 0

    def test_pcasp_sem_id_ic_ignora_regra(self, engine_context):
        """PCASP sem coluna 'id_ic' → regra desativada graciosamente."""
        df = pd.DataFrame({"conta_contabil": ["411000000"], "nr": [""]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=_pcasp_sem_id_ic()):
            result = R090().execute(df, engine_context)
        assert len(result) == 0

    def test_nr_nan_string_gera_alerta(self, engine_context):
        """NR 'nan' (string) é considerado vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic(["411000000"], ["6"])
        df = pd.DataFrame({"conta_contabil": ["411000000"], "nr": ["nan"]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=pcasp):
            result = R090().execute(df, engine_context)
        assert len(result) == 1

    def test_despesa_sem_nr_nao_afeta_r090(self, engine_context):
        """Conta de despesa (classe 3) → R090 não flagra."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["9"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "nr": [""]})
        with patch("ranking_msc.rules.r090.load_pcasp", return_value=pcasp):
            result = R090().execute(df, engine_context)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# R091 — Despesa sem ND (classe 3, id_ic com ND obrigatório)
# ---------------------------------------------------------------------------

class TestR091:
    # id_ic=7 -> IC_MAP[7] = ["PO","FS","FR","CO","ND"] → exige ND
    # id_ic=9 -> IC_MAP[9] = [...,"ND","AI"]            → exige ND
    # id_ic=4 -> IC_MAP[4] = ["PO","FP","FR","CO"]      → NÃO exige ND

    def test_despesa_com_nd_preenchida_sem_pendencia(self, engine_context):
        """Conta de despesa com ND preenchida → sem pendências."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["7"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "nd": ["33900000"]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=pcasp):
            result = R091().execute(df, engine_context)
        assert len(result) == 0

    def test_despesa_sem_nd_gera_alerta(self, engine_context):
        """Conta de despesa com id_ic exigindo ND e ND vazia → ALERTA."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["7"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "nd": [""]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=pcasp):
            result = R091().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R091"
        assert "311000000" in result.iloc[0]["conta_contabil"]

    def test_despesa_id_ic_sem_nd_nao_gera_pendencia(self, engine_context):
        """Conta com id_ic=4 (sem ND) → sem pendências."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["4"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "nd": [""]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=pcasp):
            result = R091().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_coluna_nd_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'nd' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["311000000"]})
        assert len(R091().execute(df, engine_context)) == 0

    def test_pcasp_sem_id_ic_ignora_regra(self, engine_context):
        """PCASP sem coluna 'id_ic' → regra desativada graciosamente."""
        df = pd.DataFrame({"conta_contabil": ["311000000"], "nd": [""]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=_pcasp_sem_id_ic()):
            result = R091().execute(df, engine_context)
        assert len(result) == 0

    def test_receita_sem_nd_nao_afeta_r091(self, engine_context):
        """Conta de receita (classe 4) → R091 não flagra."""
        pcasp = _pcasp_com_id_ic(["411000000"], ["7"])
        df = pd.DataFrame({"conta_contabil": ["411000000"], "nd": [""]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=pcasp):
            result = R091().execute(df, engine_context)
        assert len(result) == 0

    def test_id_ic_9_com_nd_vazia_gera_alerta(self, engine_context):
        """id_ic=9 também exige ND → ALERTA quando ND vazia."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["9"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "nd": ["0"]})
        with patch("ranking_msc.rules.r091.load_pcasp", return_value=pcasp):
            result = R091().execute(df, engine_context)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# R092 — Despesa sem FS (classe 3, id_ic com FS obrigatório)
# ---------------------------------------------------------------------------

class TestR092:
    # id_ic=7 -> IC_MAP[7] = ["PO","FS","FR","CO","ND"] → exige FS
    # id_ic=9 -> IC_MAP[9] = ["PO","FS","FR","CO","ND","AI"] → exige FS
    # id_ic=4 -> IC_MAP[4] = ["PO","FP","FR","CO"]          → NÃO exige FS

    def test_despesa_com_fs_preenchida_sem_pendencia(self, engine_context):
        """Conta de despesa com FS preenchida → sem pendências."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["7"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "fs": ["08244"]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=pcasp):
            result = R092().execute(df, engine_context)
        assert len(result) == 0

    def test_despesa_sem_fs_gera_alerta(self, engine_context):
        """Conta de despesa com id_ic exigindo FS e FS vazia → ALERTA."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["7"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "fs": [""]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=pcasp):
            result = R092().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R092"

    def test_despesa_id_ic_sem_fs_nao_gera_pendencia(self, engine_context):
        """Conta com id_ic=4 (sem FS) → sem pendências."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["4"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "fs": [""]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=pcasp):
            result = R092().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_coluna_fs_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'fs' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["311000000"]})
        assert len(R092().execute(df, engine_context)) == 0

    def test_pcasp_sem_id_ic_ignora_regra(self, engine_context):
        """PCASP sem coluna 'id_ic' → regra desativada graciosamente."""
        df = pd.DataFrame({"conta_contabil": ["311000000"], "fs": [""]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=_pcasp_sem_id_ic()):
            result = R092().execute(df, engine_context)
        assert len(result) == 0

    def test_receita_sem_fs_nao_afeta_r092(self, engine_context):
        """Conta de receita (classe 4) → R092 não flagra."""
        pcasp = _pcasp_com_id_ic(["411000000"], ["7"])
        df = pd.DataFrame({"conta_contabil": ["411000000"], "fs": [""]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=pcasp):
            result = R092().execute(df, engine_context)
        assert len(result) == 0

    def test_fs_zero_gera_alerta(self, engine_context):
        """FS '0' é considerada vazia → ALERTA."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["9"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "fs": ["0"]})
        with patch("ranking_msc.rules.r092.load_pcasp", return_value=pcasp):
            result = R092().execute(df, engine_context)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# R093 — Despesa sem FR (classe 3, id_ic com FR obrigatório)
# ---------------------------------------------------------------------------

class TestR093:
    # id_ic=7 -> IC_MAP[7] = ["PO","FS","FR","CO","ND"] → exige FR
    # id_ic=4 -> IC_MAP[4] = ["PO","FP","FR","CO"]      → exige FR
    # id_ic=1 -> IC_MAP[1] = ["PO"]                     → NÃO exige FR

    def test_despesa_com_fr_preenchido_sem_pendencia(self, engine_context):
        """Conta de despesa com FR preenchido → sem pendências."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["7"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "fr": ["1500"]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 0

    def test_despesa_sem_fr_gera_alerta(self, engine_context):
        """Conta de despesa com id_ic exigindo FR e FR vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["7"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "fr": [""]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ALERTA"
        assert result.iloc[0]["regra_id"] == "R093"
        assert "311000000" in result.iloc[0]["conta_contabil"]

    def test_despesa_id_ic_sem_fr_nao_gera_pendencia(self, engine_context):
        """Conta com id_ic=1 (sem FR) → sem pendências mesmo com FR vazio."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["1"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "fr": [""]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 0

    def test_sem_coluna_fr_retorna_vazio(self, engine_context):
        """DataFrame sem coluna 'fr' → sem pendências."""
        df = pd.DataFrame({"conta_contabil": ["311000000"]})
        assert len(R093().execute(df, engine_context)) == 0

    def test_pcasp_sem_id_ic_ignora_regra(self, engine_context):
        """PCASP sem coluna 'id_ic' → regra desativada graciosamente."""
        df = pd.DataFrame({"conta_contabil": ["311000000"], "fr": [""]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=_pcasp_sem_id_ic()):
            result = R093().execute(df, engine_context)
        assert len(result) == 0

    def test_receita_sem_fr_nao_afeta_r093(self, engine_context):
        """Conta de receita (classe 4) com FR vazio → R093 não flagra."""
        pcasp = _pcasp_com_id_ic(["411000000"], ["7"])
        df = pd.DataFrame({"conta_contabil": ["411000000"], "fr": [""]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 0

    def test_fr_zero_gera_alerta(self, engine_context):
        """FR '0' é considerado vazio → ALERTA."""
        pcasp = _pcasp_com_id_ic(["311000000"], ["4"])
        df = pd.DataFrame({"conta_contabil": ["311000000"], "fr": ["0"]})
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 1

    def test_multiplas_despesas_detecta_violadoras(self, engine_context):
        """3 despesas: uma com FR, duas sem → apenas as sem FR são flagradas."""
        pcasp = _pcasp_com_id_ic(
            ["311000000", "311000001", "311000002"],
            ["7", "7", "7"],
        )
        df = pd.DataFrame({
            "conta_contabil": ["311000000", "311000001", "311000002"],
            "fr": ["1500", "", "nan"],
        })
        with patch("ranking_msc.rules.r093.load_pcasp", return_value=pcasp):
            result = R093().execute(df, engine_context)
        assert len(result) == 2
