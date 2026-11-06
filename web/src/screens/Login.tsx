import { type FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { ApiError, apiLogin, apiSetup, apiSetupStatus } from '../api/client';

function friendlyLoginError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return 'E-mail ou senha inválidos.';
    if (err.status === 0 || err.status >= 500) return 'Não foi possível conectar ao servidor. Tente novamente.';
    return err.detail;
  }
  return 'Erro inesperado. Tente novamente.';
}

function friendlySetupError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 403) return 'Setup já concluído. Faça login com suas credenciais.';
    if (err.status === 0 || err.status >= 500) return 'Não foi possível conectar ao servidor. Tente novamente.';
    return err.detail;
  }
  return 'Erro inesperado. Tente novamente.';
}

export function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [needsSetup, setNeedsSetup] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiSetupStatus()
      .then((needs) => {
        if (!cancelled) setNeedsSetup(needs);
      })
      .catch(() => {
        // API indisponível ou versão antiga: mantém o login normal.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleLogin() {
    try {
      await apiLogin(username, password);
      navigate('/inicio', { replace: true });
    } catch (err: unknown) {
      setError(friendlyLoginError(err));
    }
  }

  async function handleSetup() {
    if (password.length < 8) {
      setError('A senha deve ter pelo menos 8 caracteres.');
      return;
    }
    if (password !== confirm) {
      setError('As senhas não conferem.');
      return;
    }
    try {
      await apiSetup(username, password);
      await apiLogin(username, password);
      navigate('/inicio', { replace: true });
    } catch (err: unknown) {
      setError(friendlySetupError(err));
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (needsSetup) {
        await handleSetup();
      } else {
        await handleLogin();
      }
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
          <div className="samid-login-logo">
            <img src="/brand/pmjp-lockup.png" alt="Prefeitura de João Pessoa" />
          </div>
          <div className="samid-login-header">
            <h1 id="login-title" className="samid-login-title">
              MCRA PMJP — Mapeamento Contábil Ranking A
            </h1>
            <p className="samid-login-subtitle">
              {needsSetup
                ? 'Primeiro acesso — crie o usuário administrador'
                : 'Sistema de validação contábil'}
            </p>
          </div>

          <label className="samid-login-field">
            <span className="samid-login-label">E-mail</span>
            <input
              type="text"
              autoComplete="email"
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
              autoComplete={needsSetup ? 'new-password' : 'current-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="samid-login-input"
            />
          </label>

          {needsSetup && (
            <label className="samid-login-field">
              <span className="samid-login-label">Confirmar senha</span>
              <input
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                className="samid-login-input"
              />
            </label>
          )}

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
            {loading
              ? needsSetup
                ? 'Criando…'
                : 'Entrando…'
              : needsSetup
                ? 'Criar administrador'
                : 'Entrar'}
          </button>

          <Link to="/ajuda" className="samid-login-help">
            Precisa de ajuda?
          </Link>
        </div>
      </form>
    </div>
  );
}
