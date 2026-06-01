import { type FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { apiLogin } from '../api/client';

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
      const msg = err instanceof Error ? err.message : 'Erro ao autenticar';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--samid-midnight)',
      }}
    >
      <form
        aria-labelledby="login-title"
        onSubmit={(e) => void handleSubmit(e)}
        style={{
          width: 320,
          borderRadius: 8,
          background: 'var(--samid-paper)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: 'var(--shadow-raised)',
        }}
      >
        <div style={{ height: 4, background: 'var(--samid-gold)' }} />

        <div style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ textAlign: 'center', marginBottom: '0.25rem' }}>
            <h1
              id="login-title"
              style={{
                fontSize: '1.1rem',
                marginBottom: '0.25rem',
                color: 'var(--fg-1)',
                fontFamily: 'var(--font-display)',
              }}
            >
              MCRA PMJP — Mapeamento Contábil Ranking A
            </h1>
            <p style={{ fontSize: '0.8rem', color: 'var(--fg-2)', margin: 0 }}>
              Sistema de validação contábil
            </p>
          </div>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--fg-2)' }}>Usuário</span>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              style={{
                padding: '0.5rem',
                borderRadius: 4,
                border: '1px solid var(--border-default)',
                background: 'var(--bg-canvas)',
                color: 'var(--fg-1)',
              }}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--fg-2)' }}>Senha</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{
                padding: '0.5rem',
                borderRadius: 4,
                border: '1px solid var(--border-default)',
                background: 'var(--bg-canvas)',
                color: 'var(--fg-1)',
              }}
            />
          </label>

          {error && (
            <p role="alert" style={{ color: 'var(--samid-erro)', fontSize: '0.85rem', margin: 0 }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            aria-busy={loading}
            style={{
              padding: '0.6rem',
              borderRadius: 4,
              background: 'var(--samid-gold)',
              color: 'var(--fg-invert)',
              border: 'none',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
              fontWeight: 600,
            }}
          >
            {loading ? 'Entrando…' : 'Entrar'}
          </button>
        </div>
      </form>
    </div>
  );
}
