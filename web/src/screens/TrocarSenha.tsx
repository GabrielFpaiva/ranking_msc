import { type FormEvent, useState } from 'react';

import { ApiError, api } from '../api/client';

// Troca de senha pelo próprio usuário. As senhas iniciais vão por e-mail no
// convite de acesso; sem esta tela, o único jeito de trocar era pedir um
// convite novo.

const MIN_CHARS = 8;

function mensagemDeErro(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0 || err.status >= 500) {
      return 'Não foi possível conectar ao servidor. Tente novamente.';
    }
    return err.detail || 'Erro inesperado. Tente novamente.';
  }
  if (err instanceof TypeError) return 'Não foi possível conectar ao servidor. Tente novamente.';
  return 'Erro inesperado. Tente novamente.';
}

export function TrocarSenha() {
  const [atual, setAtual] = useState('');
  const [nova, setNova] = useState('');
  const [confirmacao, setConfirmacao] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setOk(false);
    if (nova.length < MIN_CHARS) {
      setErro(`A senha nova deve ter no mínimo ${MIN_CHARS} caracteres.`);
      return;
    }
    if (nova !== confirmacao) {
      setErro('A confirmação não é igual à senha nova. Digite de novo.');
      return;
    }
    setEnviando(true);
    try {
      await api.changePassword(atual, nova);
      setOk(true);
    } catch (err: unknown) {
      setErro(mensagemDeErro(err));
    } finally {
      // As senhas não ficam no estado depois do envio, deu certo ou não.
      setAtual('');
      setNova('');
      setConfirmacao('');
      setEnviando(false);
    }
  }

  return (
    <form className="samid-card samid-convidar-form" onSubmit={(e) => void handleSubmit(e)}>
      <div>
        <div className="samid-eyebrow">Conta</div>
        <h2 className="samid-card-title">Trocar senha</h2>
        <p className="samid-muted">
          Digite a senha que você usa hoje e escolha uma nova (no mínimo {MIN_CHARS} caracteres).
          Você continua conectado depois da troca.
        </p>
      </div>

      <label className="samid-convidar-field">
        <span className="samid-convidar-label">Senha atual</span>
        <input
          type="password"
          autoComplete="current-password"
          value={atual}
          onChange={(e) => setAtual(e.target.value)}
          required
          className="samid-input"
        />
      </label>

      <label className="samid-convidar-field">
        <span className="samid-convidar-label">Senha nova</span>
        <input
          type="password"
          autoComplete="new-password"
          value={nova}
          onChange={(e) => setNova(e.target.value)}
          required
          className="samid-input"
        />
      </label>

      <label className="samid-convidar-field">
        <span className="samid-convidar-label">Repita a senha nova</span>
        <input
          type="password"
          autoComplete="new-password"
          value={confirmacao}
          onChange={(e) => setConfirmacao(e.target.value)}
          required
          className="samid-input"
        />
      </label>

      {erro && (
        <p role="alert" className="samid-convidar-erro">
          {erro}
        </p>
      )}
      {ok && (
        <p role="status" className="samid-convidar-ok">
          Senha trocada. Use a senha nova da próxima vez que entrar.
        </p>
      )}

      <button
        type="submit"
        disabled={enviando}
        aria-busy={enviando}
        className="samid-btn samid-btn-primary"
      >
        {enviando ? 'Salvando…' : 'Trocar senha'}
      </button>
    </form>
  );
}
