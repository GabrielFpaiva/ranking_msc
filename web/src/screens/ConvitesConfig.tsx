import { type FormEvent, useState } from 'react';

import { ApiError, api } from '../api/client';
import type { InviteAccess } from '../api/client';

// Configuração dos convites pelo próprio app, para quem convida não precisar de
// Python nem do clone do repositório (era o que travava o convite no computador
// do P.O.): ativar com o código de ativação e trocar a conta do Gmail.

const MSG_SEM_CONEXAO = 'Não foi possível conectar ao servidor. Tente novamente.';
const MIN_SENHA_CHAVE = 12;

/** Usa o `detail` da API (já em português, dizendo o que fazer); 5xx/rede viram "sem conexão". */
function mensagemDeErro(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0 || err.status >= 500) return MSG_SEM_CONEXAO;
    return err.detail || 'Erro inesperado. Tente novamente.';
  }
  if (err instanceof TypeError) return MSG_SEM_CONEXAO;
  return 'Erro inesperado. Tente novamente.';
}

function AjudaSenhaDeApp() {
  return (
    <p className="samid-muted">
      A senha de app é uma senha própria para aplicativos, gerada na conta do Google em
      myaccount.google.com/apppasswords (a verificação em duas etapas precisa estar ligada). Não é
      a senha normal do Gmail.
    </p>
  );
}

interface AtivarProps {
  /** Já estava ativado: é a reativação de quem esqueceu a senha da chave. */
  reativacao?: boolean;
  onAtivado: (acesso: InviteAccess) => void;
  onCancelar?: () => void;
}

export function AtivarConvites({ reativacao = false, onAtivado, onCancelar }: AtivarProps) {
  const [codigo, setCodigo] = useState('');
  const [senha, setSenha] = useState('');
  const [confirmacao, setConfirmacao] = useState('');
  const [smtpUser, setSmtpUser] = useState('');
  const [smtpSenha, setSmtpSenha] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    if (senha.length < MIN_SENHA_CHAVE) {
      setErro(`A senha da chave precisa ter ${MIN_SENHA_CHAVE} caracteres ou mais.`);
      return;
    }
    if (senha !== confirmacao) {
      setErro('As duas senhas da chave são diferentes. Digite de novo.');
      return;
    }
    setEnviando(true);
    try {
      const acesso = await api.activateInvites(codigo, {
        keyPassword: senha,
        smtpUser,
        smtpPassword: smtpSenha,
      });
      onAtivado(acesso);
    } catch (err: unknown) {
      setErro(mensagemDeErro(err));
    } finally {
      setSenha('');
      setConfirmacao('');
      setSmtpSenha('');
      setEnviando(false);
    }
  }

  return (
    <form className="samid-card samid-convidar-form" onSubmit={(e) => void handleSubmit(e)}>
      <div>
        <div className="samid-eyebrow">Convites</div>
        <h2 className="samid-card-title">
          {reativacao ? 'Escolher uma nova senha da chave' : 'Ativar os convites neste computador'}
        </h2>
        <p className="samid-muted">
          Cole o código de ativação que o responsável técnico enviou (começa com MCRA-ATIVACAO1),
          escolha a senha da chave e informe a conta do Gmail que vai enviar os convites. Isso é
          feito uma vez; depois é só convidar. Guarde o código de ativação: com ele você ativa de
          novo se trocar de computador ou esquecer a senha da chave.
        </p>
      </div>

      <label className="samid-convidar-field">
        <span className="samid-convidar-label">Código de ativação</span>
        <textarea
          rows={3}
          spellCheck={false}
          autoComplete="off"
          value={codigo}
          onChange={(e) => setCodigo(e.target.value)}
          required
          className="samid-input samid-convidar-code"
        />
      </label>

      <label className="samid-convidar-field">
        <span className="samid-convidar-label">Nova senha da chave (12 caracteres ou mais)</span>
        <input
          type="password"
          autoComplete="new-password"
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          required
          className="samid-input"
        />
      </label>

      <label className="samid-convidar-field">
        <span className="samid-convidar-label">Repita a senha da chave</span>
        <input
          type="password"
          autoComplete="new-password"
          value={confirmacao}
          onChange={(e) => setConfirmacao(e.target.value)}
          required
          className="samid-input"
        />
      </label>

      <label className="samid-convidar-field">
        <span className="samid-convidar-label">Conta do Gmail que envia os convites</span>
        <input
          type="email"
          autoComplete="off"
          value={smtpUser}
          onChange={(e) => setSmtpUser(e.target.value)}
          required
          className="samid-input"
        />
      </label>

      <label className="samid-convidar-field">
        <span className="samid-convidar-label">Senha de app do Gmail</span>
        <input
          type="password"
          autoComplete="off"
          value={smtpSenha}
          onChange={(e) => setSmtpSenha(e.target.value)}
          required
          className="samid-input"
        />
      </label>
      <AjudaSenhaDeApp />

      {erro && (
        <p role="alert" className="samid-convidar-erro">
          {erro}
        </p>
      )}

      <div className="samid-convidar-acoes">
        <button
          type="submit"
          disabled={enviando}
          aria-busy={enviando}
          className="samid-btn samid-btn-primary"
        >
          {enviando ? 'Ativando…' : 'Ativar convites'}
        </button>
        {onCancelar && (
          <button type="button" className="samid-btn samid-btn-ghost" onClick={onCancelar}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}

interface ContaProps {
  smtpUser: string | null;
  podeReativar: boolean;
  onAtualizado: (acesso: InviteAccess) => void;
  onReativar: () => void;
}

export function ContaDeEnvio({ smtpUser, podeReativar, onAtualizado, onReativar }: ContaProps) {
  const [aberto, setAberto] = useState(false);
  const [novaConta, setNovaConta] = useState('');
  const [smtpSenha, setSmtpSenha] = useState('');
  const [senhaChave, setSenhaChave] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  function abrir() {
    setNovaConta(smtpUser ?? '');
    setErro(null);
    setOk(false);
    setAberto(true);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      const acesso = await api.updateInviteSender({
        keyPassword: senhaChave,
        smtpUser: novaConta,
        smtpPassword: smtpSenha,
      });
      onAtualizado(acesso);
      setAberto(false);
      setOk(true);
    } catch (err: unknown) {
      setErro(mensagemDeErro(err));
    } finally {
      setSenhaChave('');
      setSmtpSenha('');
      setEnviando(false);
    }
  }

  return (
    <section className="samid-card" aria-label="Conta de envio">
      <div className="samid-card-head">
        <h2 className="samid-card-title">Conta de envio</h2>
      </div>
      <p className="samid-muted">
        Os convites saem pelo Gmail <b>{smtpUser ?? '—'}</b>.
      </p>
      {ok && (
        <p role="status" className="samid-convidar-ok">
          Conta de envio atualizada.
        </p>
      )}

      {!aberto && (
        <div className="samid-convidar-acoes">
          <button type="button" className="samid-btn samid-btn-ghost" onClick={abrir}>
            Trocar conta ou senha de app do Gmail
          </button>
          {podeReativar && (
            <button type="button" className="samid-btn samid-btn-ghost" onClick={onReativar}>
              Esqueci a senha da chave
            </button>
          )}
        </div>
      )}

      {aberto && (
        <form className="samid-convidar-form" onSubmit={(e) => void handleSubmit(e)}>
          <label className="samid-convidar-field">
            <span className="samid-convidar-label">Conta do Gmail</span>
            <input
              type="email"
              autoComplete="off"
              value={novaConta}
              onChange={(e) => setNovaConta(e.target.value)}
              required
              className="samid-input"
            />
          </label>
          <label className="samid-convidar-field">
            <span className="samid-convidar-label">Nova senha de app do Gmail</span>
            <input
              type="password"
              autoComplete="off"
              value={smtpSenha}
              onChange={(e) => setSmtpSenha(e.target.value)}
              required
              className="samid-input"
            />
          </label>
          <AjudaSenhaDeApp />
          <label className="samid-convidar-field">
            <span className="samid-convidar-label">Senha da chave (para autorizar)</span>
            <input
              type="password"
              autoComplete="off"
              value={senhaChave}
              onChange={(e) => setSenhaChave(e.target.value)}
              required
              className="samid-input"
            />
          </label>
          {erro && (
            <p role="alert" className="samid-convidar-erro">
              {erro}
            </p>
          )}
          <div className="samid-convidar-acoes">
            <button
              type="submit"
              disabled={enviando}
              aria-busy={enviando}
              className="samid-btn samid-btn-primary"
            >
              {enviando ? 'Salvando…' : 'Salvar conta de envio'}
            </button>
            <button
              type="button"
              className="samid-btn samid-btn-ghost"
              onClick={() => setAberto(false)}
            >
              Cancelar
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
