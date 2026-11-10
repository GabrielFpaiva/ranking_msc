import { type FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import {
  ApiError,
  apiAcceptInvite,
  apiInviteStatus,
  apiLogin,
  apiSetup,
  apiSetupStatus,
} from '../api/client';

const MSG_SEM_CONEXAO = 'Não foi possível conectar ao servidor. Tente novamente.';

const MSG_CONTA_CRIADA_SEM_LOGIN =
  'Sua conta já foi criada, mas não foi possível entrar agora. Volte ao login e entre com o seu e-mail e a senha que você acabou de escolher.';

// Usa o `detail` da API (já em português e dizendo o que fazer), como
// `friendlyLoginError`. NÃO usa `ApiError.userMessage`: ele traduz 409 como
// "processamento em andamento", que aqui quer dizer "convite já usado".
function friendlyInviteError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0 || err.status >= 500) return MSG_SEM_CONEXAO;
    switch (err.status) {
      case 400:
        return (
          err.detail ||
          'Código de convite inválido. Copie o código inteiro do e-mail e cole de novo, ou peça um novo convite.'
        );
      case 403:
        return (
          err.detail ||
          'Convites não estão ativados nesta versão do MCRA. Procure o responsável técnico.'
        );
      case 409:
        return (
          err.detail ||
          'Este convite já foi usado neste computador. Peça um novo convite ao responsável técnico.'
        );
      case 410:
        return err.detail || 'Este convite venceu. Peça um novo convite ao responsável técnico.';
      default:
        return err.detail || 'Erro inesperado. Tente novamente.';
    }
  }
  // fetch rejeitou (TypeError): sem rede ou servidor fora do ar.
  if (err instanceof TypeError) return MSG_SEM_CONEXAO;
  return 'Erro inesperado. Tente novamente.';
}

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
  const [codigo, setCodigo] = useState('');
  const [needsSetup, setNeedsSetup] = useState(false);
  const [conviteLigado, setConviteLigado] = useState(false);
  const [modo, setModo] = useState<'login' | 'convite'>('login');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // As duas consultas entram juntas: assim "Tenho um convite" não pisca na
    // tela do primeiro acesso. Falha em qualquer uma (API indisponível ou
    // versão antiga) mantém o login normal, sem o convite.
    void Promise.all([
      apiSetupStatus().catch(() => false),
      apiInviteStatus().catch(() => false),
    ]).then(([needs, convites]) => {
      if (cancelled) return;
      setNeedsSetup(needs);
      setConviteLigado(convites);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const emModoConvite = modo === 'convite' && !needsSetup;
  const mostraTenhoConvite = conviteLigado && !needsSetup && !emModoConvite;

  function trocarModo(novo: 'login' | 'convite') {
    setModo(novo);
    setError(null);
    setPassword('');
    setConfirm('');
    setCodigo('');
  }

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

  async function handleInvite() {
    if (password.length < 8 || password.length > 72) {
      setError('A senha deve ter entre 8 e 72 caracteres.');
      return;
    }
    if (password !== confirm) {
      setError('As senhas não conferem.');
      return;
    }
    let conta: string;
    try {
      conta = (await apiAcceptInvite(codigo, password)).username;
    } catch (err: unknown) {
      setError(friendlyInviteError(err));
      return;
    }
    // O convite já criou (ou trocou a senha de) a conta: se o login falhar
    // agora, repetir o convite não adianta. Guarda o e-mail para o login normal.
    setUsername(conta);
    try {
      await apiLogin(conta, password);
      navigate('/inicio', { replace: true });
    } catch {
      setError(MSG_CONTA_CRIADA_SEM_LOGIN);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (emModoConvite) {
        await handleInvite();
      } else if (needsSetup) {
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
                : emModoConvite
                  ? 'Entrar com convite — cole o código que você recebeu por e-mail'
                  : 'Sistema de validação contábil'}
            </p>
          </div>

          {emModoConvite ? (
            <>
              <label className="samid-login-field">
                <span className="samid-login-label">Código do convite</span>
                <textarea
                  rows={4}
                  autoComplete="off"
                  spellCheck={false}
                  value={codigo}
                  onChange={(e) => setCodigo(e.target.value)}
                  required
                  className="samid-login-input samid-login-code"
                />
              </label>

              <label className="samid-login-field">
                <span className="samid-login-label">Nova senha</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="samid-login-input"
                />
              </label>
            </>
          ) : (
            <>
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
            </>
          )}

          {(needsSetup || emModoConvite) && (
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
                : emModoConvite
                  ? 'Entrar com convite'
                  : 'Entrar'}
          </button>

          {mostraTenhoConvite && (
            <button
              type="button"
              className="samid-login-switch"
              onClick={() => trocarModo('convite')}
            >
              Tenho um convite
            </button>
          )}
          {emModoConvite && (
            <button
              type="button"
              className="samid-login-switch"
              onClick={() => trocarModo('login')}
            >
              Voltar ao login
            </button>
          )}

          <Link to="/ajuda" className="samid-login-help">
            Precisa de ajuda?
          </Link>
        </div>
      </form>
    </div>
  );
}
