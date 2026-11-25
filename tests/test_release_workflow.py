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


_NOME_DA_INSTALACAO = "Instalar o rclone"


def _passo_de_instalacao() -> dict[str, Any]:
    """Acha o passo que instala o rclone."""
    achados = [p for p in _passos() if p.get("name") == _NOME_DA_INSTALACAO]
    assert len(achados) == 1, f"esperado um passo '{_NOME_DA_INSTALACAO}', achei {len(achados)}"
    return achados[0]


def test_rclone_e_instalado_entre_o_artefato_e_o_envio() -> None:
    """Instala depois do artefato (falha não toca o instalador) e antes de publicar."""
    nomes = [p.get("name") for p in _passos()]
    indice_artefato = next(
        i for i, p in enumerate(_passos()) if "upload-artifact" in str(p.get("uses", ""))
    )
    indice_instalacao = nomes.index(_NOME_DA_INSTALACAO)
    assert indice_artefato < indice_instalacao < nomes.index(_NOME_DO_PASSO)


def test_instalacao_do_rclone_nao_ve_segredo_e_nao_derruba_o_release() -> None:
    """Script de instalação nunca roda com as credenciais do Drive no ambiente."""
    passo = _passo_de_instalacao()
    assert "secrets." not in str(passo)
    assert passo.get("continue-on-error") is True
    assert passo.get("if") == _passo_do_drive_sem_dependencia_da_instalacao()


def _passo_do_drive_sem_dependencia_da_instalacao() -> str:
    """O ``if`` do envio sem a cláusula que exige a instalação ter dado certo."""
    condicao = str(_passo_do_drive()["if"])
    return condicao.replace(" && steps.rclone.outcome == 'success' }}", " }}")


def test_rclone_vem_do_release_oficial_com_versao_e_hash_fixos() -> None:
    """Zip oficial em versão fixa, conferido por SHA-256 antes de rodar; nada de choco."""
    passo = _passo_de_instalacao()
    env = passo["env"]
    assert str(env["MCRA_RCLONE_VERSAO"]).startswith("v")
    assert len(str(env["MCRA_RCLONE_SHA256"])) == 64
    assert "github.com/rclone/rclone/releases/download" in passo["run"]
    assert "Get-FileHash" in passo["run"]
    assert "GITHUB_PATH" in passo["run"]
    for p in _passos():
        assert "choco" not in str(p.get("run", "")), p.get("name")


def test_instalacao_nao_usa_variavel_que_o_rclone_le_como_flag() -> None:
    """O rclone lê toda RCLONE_* do ambiente como flag (RCLONE_VERSION vira --version)."""
    assert not [k for k in _passo_de_instalacao()["env"] if k.startswith("RCLONE_")]


def test_envio_so_roda_se_o_rclone_foi_instalado() -> None:
    """Instalação falhou (com continue-on-error) → o envio é pulado, não quebra no PATH."""
    assert "steps.rclone.outcome == 'success'" in str(_passo_do_drive()["if"])
    assert _passo_de_instalacao().get("id") == "rclone"


def _passo_da_release() -> dict[str, Any]:
    achados = [p for p in _passos() if p.get("name") == "Publicar na Release do GitHub"]
    assert len(achados) == 1
    return achados[0]


def test_release_do_github_vem_depois_do_artefato_e_so_em_tag() -> None:
    """O e-mail do convite aponta para releases/latest: a tag precisa publicar a Release."""
    nomes = [p.get("uses", p.get("name")) for p in _passos()]
    artefato = next(i for i, n in enumerate(nomes) if str(n).startswith("actions/upload-artifact"))
    assert nomes.index("Publicar na Release do GitHub") > artefato
    assert "refs/tags/v" in str(_passo_da_release()["if"])


def test_release_publica_o_nome_fixo_do_link_do_convite() -> None:
    """installer_url usa releases/latest/download/MCRA-Setup.exe: o nome não pode mudar."""
    passo = _passo_da_release()
    assert "MCRA-Setup.exe" in passo["run"]
    assert "--clobber" in passo["run"]
    invites = yaml.safe_load(
        (_WORKFLOW.parents[2] / "config" / "invites.yaml").read_text(encoding="utf-8")
    )
    assert invites["installer_url"].endswith("/releases/latest/download/MCRA-Setup.exe")


def test_release_confere_tag_contra_a_versao_e_tem_permissao_de_escrita() -> None:
    passo = _passo_da_release()
    assert "steps.versao.outputs.valor" in passo["env"]["VERSAO"]
    assert _job()["permissions"]["contents"] == "write"
