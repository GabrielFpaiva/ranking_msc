"""Testes da regra R020 — Conjunto de IC correto para a conta."""

from __future__ import annotations

import pandas as pd
import pytest

from ranking_msc.rules.r020 import R020


def _pcasp_stub(contas: list[tuple[str, str]]) -> pd.DataFrame:
    """Gera um PCASP mínimo para testes.

    Args:
        contas: lista de tuplas (conta_contabil, id_ic).

    Returns:
        DataFrame com colunas conta_contabil e id_ic.
    """
    return pd.DataFrame(
        {
            "conta_contabil": [c for c, _ in contas],
            "id_ic": [i for _, i in contas],
        }
    )


def _df_com_ics(**kwargs: str) -> pd.DataFrame:
    """Cria DataFrame de teste com colunas IC pré-definidas.

    Args:
        **kwargs: colunas IC a preencher (po, fp, dc, fs, fr, co, nr, nd, ai).
                  Colunas não passadas ficam vazias ("").

    Returns:
        DataFrame de uma linha com todas as colunas IC.
    """
    ic_cols = ("po", "fp", "dc", "fs", "fr", "co", "nr", "nd", "ai")
    row: dict[str, object] = {"conta_contabil": kwargs.pop("conta_contabil", "111110200")}
    for col in ic_cols:
        row[col] = kwargs.get(col, "")
    return pd.DataFrame([row])


class TestR020:
    def test_conjunto_ic_correto_sem_pendencia(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ID_IC=2 → po+fp informados → nenhuma pendência."""
        pcasp = _pcasp_stub([("111110200", "2")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        # ID_IC=2 exige PO e FP
        df = _df_com_ics(conta_contabil="111110200", po="10131", fp="1")
        result = R020().execute(df, engine_context)

        assert len(result) == 0

    def test_ic_faltante_gera_erro(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ID_IC=4 → po+fp informados, faltam fr e co → ERRO com detalhes."""
        pcasp = _pcasp_stub([("111110200", "4")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        # ID_IC=4 exige PO, FP, FR, CO — informamos apenas PO e FP
        df = _df_com_ics(conta_contabil="111110200", po="10131", fp="1")
        result = R020().execute(df, engine_context)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["severidade"] == "ERRO"
        assert row["regra_id"] == "R020"
        assert row["conta_contabil"] == "111110200"
        assert "FR" in row["descricao"]
        assert "CO" in row["descricao"]
        assert "faltantes" in row["descricao"].lower()

    def test_ic_informado_em_qualquer_linha_da_conta_conta_como_informado(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Uma conta decompõe-se em várias linhas com conjuntos de IC diferentes.
        Um IC informado em QUALQUER linha da conta deve contar como informado
        (união por conta) — não se pode amostrar uma única linha.

        ID_IC=4 exige PO, FP, FR, CO. A conta tem uma linha sem CO e outra com
        CO; a união satisfaz o esperado, logo não há pendência.
        """
        pcasp = _pcasp_stub([("111110200", "4")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        ic_cols = ("po", "fp", "dc", "fs", "fr", "co", "nr", "nd", "ai")
        base = {c: "" for c in ic_cols}
        linha_sem_co = {**base, "conta_contabil": "111110200",
                        "po": "10131", "fp": "1", "fr": "1500"}
        linha_com_co = {**base, "conta_contabil": "111110200",
                        "po": "10131", "fp": "1", "fr": "1500", "co": "1001"}
        df = pd.DataFrame([linha_sem_co, linha_com_co])
        result = R020().execute(df, engine_context)

        assert len(result) == 0

    def test_co_ausente_nao_gera_erro_por_ser_condicional(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CO (Código de Acompanhamento da Execução Orçamentária) é condicional:
        o leiaute MSC 2026 (Anexo II) define que CO é usado 'quando se aplicar'.
        Sua ausência não é violação, mesmo constando do conjunto do ID_IC.

        ID_IC=4 → PO, FP, FR, CO. Informados PO, FP, FR (sem CO) → sem pendência.
        """
        pcasp = _pcasp_stub([("111110200", "4")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        df = _df_com_ics(conta_contabil="111110200", po="10131", fp="1", fr="1500")
        result = R020().execute(df, engine_context)

        assert len(result) == 0

    def test_ic_obrigatorio_faltante_ainda_gera_erro_mesmo_sem_co(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CO condicional não afrouxa os demais: se falta um IC obrigatório
        (ex.: FR no ID_IC=4), ainda é ERRO — e CO não aparece como faltante."""
        pcasp = _pcasp_stub([("111110200", "4")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        # ID_IC=4 exige PO, FP, FR (+CO condicional). Falta FR.
        df = _df_com_ics(conta_contabil="111110200", po="10131", fp="1")
        result = R020().execute(df, engine_context)

        assert len(result) == 1
        assert "FR" in result.iloc[0]["descricao"]
        assert "CO" not in result.iloc[0]["descricao"].split("Esperado")[0]

    def test_ic_extra_gera_erro(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ID_IC=1 → po informado mas fp também está informado (extra) → ERRO."""
        pcasp = _pcasp_stub([("111110200", "1")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        # ID_IC=1 exige apenas PO — informamos PO e FP (FP é extra)
        df = _df_com_ics(conta_contabil="111110200", po="10131", fp="1")
        result = R020().execute(df, engine_context)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["severidade"] == "ERRO"
        assert row["regra_id"] == "R020"
        assert "FP" in row["descricao"]
        assert "não esperadas" in row["descricao"].lower()

    def test_ic_faltante_e_extra_juntos_um_unico_erro(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ID_IC=2 (PO+FP) → po informado mas co está extra → um único ERRO descrevendo ambos."""
        pcasp = _pcasp_stub([("111110200", "2")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        # ID_IC=2 exige PO e FP — informamos PO e CO (falta FP, CO é extra)
        df = _df_com_ics(conta_contabil="111110200", po="10131", co="1500")
        result = R020().execute(df, engine_context)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["severidade"] == "ERRO"
        # Deve mencionar tanto faltante (FP) quanto extra (CO)
        assert "FP" in row["descricao"]
        assert "CO" in row["descricao"]
        assert "faltantes" in row["descricao"].lower()
        assert "não esperadas" in row["descricao"].lower()

    def test_id_ic_zero_sem_ic_sem_pendencia(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ID_IC=0 → nenhuma IC esperada e nenhuma informada → sem pendência."""
        pcasp = _pcasp_stub([("111110200", "0")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        # IC_MAP[0] = [] → nenhuma IC esperada
        df = _df_com_ics(conta_contabil="111110200")
        result = R020().execute(df, engine_context)

        assert len(result) == 0

    def test_conta_sem_id_ic_no_pcasp_skip(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conta não presente no PCASP → warning logado, sem pendência, sem exceção."""
        # PCASP sem a conta "999999999"
        pcasp = _pcasp_stub([("111110200", "2")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        df = _df_com_ics(conta_contabil="999999999", po="10131", fp="1")
        result = R020().execute(df, engine_context)

        assert len(result) == 0

    def test_id_ic_desconhecido_no_ic_map_skip(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ID_IC=99 (fora do IC_MAP) → skip com warning, sem quebrar."""
        pcasp = _pcasp_stub([("111110200", "99")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        df = _df_com_ics(conta_contabil="111110200", po="10131")
        result = R020().execute(df, engine_context)

        assert len(result) == 0

    def test_id_ic_nulo_no_pcasp_skip(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ID_IC nulo/vazio no PCASP → skip com warning, sem pendência."""
        pcasp = _pcasp_stub([("111110200", "")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        df = _df_com_ics(conta_contabil="111110200", po="10131")
        result = R020().execute(df, engine_context)

        assert len(result) == 0

    def test_valor_esperado_e_encontrado_preenchidos(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Pendência deve ter valor_esperado e valor_encontrado preenchidos corretamente."""
        # ID_IC=4: PO, FP, FR, CO
        pcasp = _pcasp_stub([("111110200", "4")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        # Informa apenas PO e FP (falta FR e CO)
        df = _df_com_ics(conta_contabil="111110200", po="10131", fp="1")
        result = R020().execute(df, engine_context)

        assert len(result) == 1
        row = result.iloc[0]
        # valor_esperado deve conter as ICs esperadas ordenadas
        assert "CO" in row["valor_esperado"]
        assert "FP" in row["valor_esperado"]
        assert "FR" in row["valor_esperado"]
        assert "PO" in row["valor_esperado"]
        # valor_encontrado deve conter apenas o que foi informado
        assert "FP" in row["valor_encontrado"]
        assert "PO" in row["valor_encontrado"]

    def test_id_ic_zero_com_ic_informada_gera_erro(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ID_IC=0 → nenhuma IC esperada mas PO informado → ERRO (IC extra)."""
        pcasp = _pcasp_stub([("111110200", "0")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        # IC_MAP[0] = [] → PO informado é extra
        df = _df_com_ics(conta_contabil="111110200", po="10131")
        result = R020().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["severidade"] == "ERRO"

    def test_pcasp_sem_coluna_id_ic_skip_todas_contas(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PCASP sem coluna id_ic → todas as contas são ignoradas (sem id_ic_map)."""
        # PCASP sem a coluna id_ic
        pcasp = pd.DataFrame({"conta_contabil": ["111110200"]})
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        df = _df_com_ics(conta_contabil="111110200", po="10131", fp="1")
        result = R020().execute(df, engine_context)

        # Sem id_ic_map → conta não encontrada → skip
        assert len(result) == 0

    def test_multiplas_contas_cada_uma_avaliada_independentemente(
        self,
        engine_context: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Múltiplas contas: uma correta e outra com IC faltante → apenas a errada gera pendência."""  # noqa: E501
        pcasp = _pcasp_stub([("111110200", "2"), ("211000000", "4")])
        monkeypatch.setattr("ranking_msc.rules.r020.load_pcasp", lambda *a, **kw: pcasp)

        # Conta 111110200 com ID_IC=2: PO+FP OK
        # Conta 211000000 com ID_IC=4: apenas PO+FP, falta FR+CO
        rows = [
            {"conta_contabil": "111110200", "po": "10131", "fp": "1",
             "dc": "", "fs": "", "fr": "", "co": "", "nr": "", "nd": "", "ai": ""},
            {"conta_contabil": "211000000", "po": "10131", "fp": "1",
             "dc": "", "fs": "", "fr": "", "co": "", "nr": "", "nd": "", "ai": ""},
        ]
        df = pd.DataFrame(rows)
        result = R020().execute(df, engine_context)

        assert len(result) == 1
        assert result.iloc[0]["conta_contabil"] == "211000000"
