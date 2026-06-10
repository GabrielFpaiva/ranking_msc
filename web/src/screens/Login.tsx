import { type FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError, apiLogin } from '../api/client';

function friendlyLoginError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return 'Usuário ou senha inválidos.';
    if (err.status === 0 || err.status >= 500) return 'Não foi possível conectar ao servidor. Tente novamente.';
    return err.detail;
  }
  return 'Erro inesperado. Tente novamente.';
}

export function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await apiLogin(username, password);
      navigate('/inicio', { replace: true });
    } catch (err: unknown) {
      setError(friendlyLoginError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="samid-login-page">
      <form
        aria-labelledby="login-title"
        onSubmit={(e) => void handleSubmit(e)}
        className="samid-login-form"
      >
        <div className="samid-login-stripe" />

        <div className="samid-login-body">
          <div className="samid-login-header">
            <h1 id="login-title" className="samid-login-title">
              MCRA PMJP — Mapeamento Contábil Ranking A
            </h1>
            <p className="samid-login-subtitle">Sistema de validação contábil</p>
          </div>

          <label className="samid-login-field">
            <span className="samid-login-label">Usuário</span>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="samid-login-input"
            />
          </label>

          <label className="samid-login-field">
            <span className="samid-login-label">Senha</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="samid-login-input"
            />
          </label>

          {error && (
            <p role="alert" className="samid-login-error">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            aria-busy={loading}
            className="samid-login-submit"
          >
            {loading ? 'Entrando…' : 'Entrar'}
          </button>
        </div>
      </form>
    </div>
  );
}
