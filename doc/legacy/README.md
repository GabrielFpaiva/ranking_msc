# Material de publicação em servidor (inativo desde 21/09/2026)

Estes arquivos serviam à entrega hospedada: contêineres, proxy Nginx e HTTPS.
Em 21/09/2026 a entrega passou a ser um aplicativo instalado na máquina de cada
pessoa da equipe, porque a Prefeitura não provisionou servidor, domínio nem
certificado institucional.

Nada aqui é usado pelo build atual. Ficam no repositório porque a decisão pode
ser revista se a PMJP disponibilizar infraestrutura.

O empacotamento vigente está em `mcra.spec`, `installer/mcra.iss` e
`.github/workflows/release.yml`.

## Cadeia de E2E de deploy

Junto com os contêineres, foi movida para cá a suíte de testes ponta a ponta
do deploy hospedado, que só faz sentido junto com o compose:

- `scripts/deploy/renew-hook.sh` — hook de renovação do certificado TLS do nginx.
- `tests/test_renew_hook.py` — testa o hook acima.
- `tests/test_e2e_deploy.py` — sobe o stack via compose; já era skipped por padrão.
- `scripts/run_e2e.py` — CLI que roda a suíte `test_e2e_deploy.py`.

O `pyproject.toml` tem `testpaths = ["tests"]`, então nada dentro de
`doc/legacy/` é coletado pelo pytest — estes testes ficam inertes, não
quebrados.
