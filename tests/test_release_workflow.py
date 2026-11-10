"""Testes do workflow de release — o passo que publica o instalador no Drive."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"
_NOME_DO_PASSO = "Publicar o instalador no Drive"


def _job() -> dict[str, Any]:
    """Lê o job ``windows`` do workflow de release."""
    raw = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    job: dict[str, Any] = raw["jobs"]["windows"]
    return job


def _passos() -> list[dict[str, Any]]:
    """Devolve os passos do job, na ordem do arquivo."""
    passos: list[dict[str, Any]] = _job()["steps"]
    return passos


def _passo_do_drive() -> dict[str, Any]:
    """Acha o passo que publica o instalador no Drive."""
    achados = [p for p in _passos() if p.get("name") == _NOME_DO_PASSO]
    assert len(achados) == 1, f"esperado um passo '{_NOME_DO_PASSO}', achei {len(achados)}"
    return achados[0]


def test_passo_do_drive_vem_depois_do_artefato() -> None:
    """O instalador vira artefato do Actions antes de qualquer tentativa de envio."""
    nomes_ou_uses = [p.get("name") or p.get("uses", "") for p in _passos()]
    indice_artefato = next(
        i for i, p in enumerate(_passos()) if "upload-artifact" in str(p.get("uses", ""))
    )
    assert nomes_ou_uses.index(_NOME_DO_PASSO) > indice_artefato


def test_passo_do_drive_nunca_derruba_o_release() -> None:
    """Falha no envio (credencial vencida, Drive fora) não pode invalidar o instalador gerado."""
    assert _passo_do_drive().get("continue-on-error") is True


def test_passo_do_drive_so_roda_quando_configurado_sem_ler_segredo_no_if() -> None:
    """O contexto ``secrets`` não vale em ``if`` de passo: a condição usa ``vars`` e ``env``."""
    condicao = str(_passo_do_drive().get("if", ""))
    assert condicao, "o passo precisa de 'if' para ser pulado enquanto não há credencial"
    assert "secrets." not in condicao
    assert "vars.GDRIVE_FOLDER_ID" in condicao
    assert "env.GDRIVE_CONFIGURED" in condicao


def test_job_expoe_so_o_sinal_de_configurado_nao_o_segredo() -> None:
    """No nível do job vai só verdadeiro/falso; os segredos ficam restritos ao passo do Drive."""
    env_do_job = _job().get("env", {})
    assert set(env_do_job) == {"GDRIVE_CONFIGURED"}
    assert "!= ''" in str(env_do_job["GDRIVE_CONFIGURED"])
    for passo in _passos():
        if passo.get("name") == _NOME_DO_PASSO:
            continue
        assert "secrets.GDRIVE" not in str(passo), passo.get("name") or passo.get("uses")


def test_passo_do_drive_usa_nome_fixo_e_a_pasta_da_variavel() -> None:
    """Nome de arquivo fixo: o link do convite não muda a cada versão."""
    passo = _passo_do_drive()
    env = passo["env"]
    assert env["RCLONE_CONFIG_MCRADRIVE_TYPE"] == "drive"
    assert "vars.GDRIVE_FOLDER_ID" in str(env["RCLONE_CONFIG_MCRADRIVE_ROOT_FOLDER_ID"])
    assert "secrets.GDRIVE_TOKEN" in str(env["RCLONE_CONFIG_MCRADRIVE_TOKEN"])
    assert "secrets.GDRIVE_CLIENT_ID" in str(env["RCLONE_CONFIG_MCRADRIVE_CLIENT_ID"])
    assert "secrets.GDRIVE_CLIENT_SECRET" in str(env["RCLONE_CONFIG_MCRADRIVE_CLIENT_SECRET"])
    assert "mcradrive:MCRA-Setup.exe" in passo["run"]
    assert "copyto" in passo["run"]
