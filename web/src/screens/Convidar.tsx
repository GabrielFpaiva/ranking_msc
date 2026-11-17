import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, api } from '../api/client';
import type { InviteCreated, InviteSent } from '../api/client';

const MSG_SEM_CONEXAO = 'Não foi possível conectar ao servidor. Tente novamente.';

// A API devolve ISO 8601 com offset de America/Recife; mostramos sempre nesse
// fuso, o mesmo em que a validade foi calculada, e não no do computador.
const FORMATO_DATA_HORA = new Intl.DateTimeFormat('pt-BR', {
  timeZone: 'America/Recife',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

function formatarDataHora(iso: string): string {
  const partes: Record<string, string> = {};
  for (const parte of FORMATO_DATA_HORA.formatToParts(new Date(iso))) {
    partes[parte.type] = parte.value;
  }
  return `${partes.day}/${partes.month}/${partes.year} às ${partes.hour}:${partes.minute}`;
}

// Usa o `detail` da API quando existe (como `friendlyLoginError`) e NÃO
// `ApiError.userMessage`, que traduz 409 e 403 de outro jeito.
function friendlySendError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0 || err.status >= 500) return MSG_SEM_CONEXAO;
    if (err.status === 400) {
      return (
        err.detail || 'Senha da chave incorreta. Digite de novo a senha da chave de convites.'
      );
    }
    if (err.status === 422) {
      return (
        err.detail || 'O e-mail informado não parece válido. Confira o endereço e tente de novo.'
      );
    }
    return err.detail || 'Erro inesperado. Tente novamente.';
  }
  if (err instanceof TypeError) return MSG_SEM_CONEXAO;
  return 'Erro inesperado. Tente novamente.';
}

type EstadoCopia = 'copiado' | 'erro' | null;

export function Convidar() {
  const [email, setEmail] = useState('');
  // A senha da chave só vive aqui até o envio terminar: é limpa em `finally`
  // e nunca vai para storage nem para o resultado.
  const [senhaChave, setSenhaChave] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<InviteCreated | null>(null);
  const [copia, setCopia] = useState<EstadoCopia>(null);

  const [lista, setLista] = useState<InviteSent[] | null>(null);
  const [erroLista, setErroLista] = useState<string | null>(null);
  const [listaPronta, setListaPronta] = useState(false);
  const [semPermissao, setSemPermissao] = useState(false);
  const montado = useRef(true);

  const carregarLista = useCallback(async () => {
    try {
      const itens = await api.listInvites();
      if (!montado.current) return;
      setLista(itens);
      setErroLista(null);
    } catch (err: unknown) {
      if (!montado.current) return;
      if (err instanceof ApiError && err.status === 403) {
        setSemPermissao(true);
      } else {
        setErroLista('Não foi possível carregar a lista de convites. Tente novamente.');
      }
    } finally {
      if (montado.current) setListaPronta(true);
    }
  }, []);

  useEffect(() => {
    montado.current = true;
    void carregarLista();
    return () => {
      montado.current = false;
    };
  }, [carregarLista]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setResultado(null);
    setCopia(null);
    setEnviando(true);
    try {
      const convite = await api.createInvite(email, senhaChave);
      setResultado(convite);
      setEmail('');
      void carregarLista();
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 403) {
        setSemPermissao(true);
      } else {
        setErro(friendlySendError(err));
      }
    } finally {
      setSenhaChave('');
      setEnviando(false);
    }
  }

  async function copiarCodigo(codigo: string) {
    try {
      await window.navigator.clipboard.writeText(codigo);
      setCopia('copiado');
    } catch {
      setCopia('erro');
    }
  }

  if (semPermissao) {
    return (
      <div className="samid-card">
        <div className="samid-eyebrow">Convites</div>
        <h2 className="samid-card-title" style={{ marginTop: 8 }}>
          Sem permissão para convidar
        </h2>
        <p className="samid-muted">
          Só quem está cadastrado como emissor de convites, no computador que guarda a chave, pode
          usar esta tela. Se você precisa entrar no MCRA, peça um convite ao responsável técnico.
        </p>
      </div>
    );
  }

  if (!listaPronta) {
    return <p className="samid-muted">Carregando convites...</p>;
  }

  return (
    <div className="samid-stack">
      <form className="samid-card samid-convidar-form" onSubmit={(e) => void handleSubmit(e)}>
        <div>
          <div className="samid-eyebrow">Convites</div>
          <h2 className="samid-card-title">Convidar um colaborador</h2>
          <p className="samid-muted">
            O colaborador recebe por e-mail o link do instalador e um código. O convite tem prazo
            de validade: a data aparece aqui depois do envio e vai no e-mail. Ele mesmo escolhe a
            senha.
          </p>
        </div>

        <label className="samid-convidar-field">
          <span className="samid-convidar-label">E-mail do colaborador</span>
          <input
            type="email"
            autoComplete="off"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="samid-input"
          />
        </label>

        <label className="samid-convidar-field">
          <span className="samid-convidar-label">Senha da chave</span>
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

        {resultado?.email_sent && (
          <p role="status" className="samid-convidar-ok">
            Convite enviado por e-mail para {resultado.email}. Vale até{' '}
            {formatarDataHora(resultado.expires_at)}.
          </p>
        )}

        {resultado && !resultado.email_sent && (
          <div className="samid-convidar-aviso">
            <p role="alert">
              O e-mail não saiu. O convite para {resultado.email} foi criado e vale até{' '}
              {formatarDataHora(resultado.expires_at)}: copie o código abaixo e envie a ele por
              outro meio.
            </p>
            <label className="samid-convidar-field">
              <span className="samid-convidar-label">Código do convite</span>
              <textarea
                readOnly
                rows={4}
                spellCheck={false}
                value={resultado.code}
                onFocus={(e) => e.currentTarget.select()}
                className="samid-input samid-convidar-code"
              />
            </label>
            <button
              type="button"
              className="samid-btn samid-btn-ghost"
              onClick={() => void copiarCodigo(resultado.code)}
            >
              Copiar código
            </button>
            {copia === 'copiado' && <span className="samid-convidar-copia">Código copiado.</span>}
            {copia === 'erro' && (
              <span className="samid-convidar-copia">
                Não foi possível copiar sozinho. Selecione o código acima e copie com Ctrl+C.
              </span>
            )}
          </div>
        )}

        <button
          type="submit"
          disabled={enviando}
          aria-busy={enviando}
          className="samid-btn samid-btn-primary"
        >
          {enviando ? 'Enviando…' : 'Enviar convite'}
        </button>
      </form>

      <section className="samid-card" aria-label="Convites emitidos">
        <div className="samid-card-head">
          <h2 className="samid-card-title">Convites emitidos neste computador</h2>
        </div>
        {erroLista && <p className="samid-convidar-erro">{erroLista}</p>}
        {lista && lista.length === 0 && (
          <p className="samid-muted">Nenhum convite emitido neste computador.</p>
        )}
        {lista && lista.length > 0 && (
          <table className="samid-table samid-table-dense samid-convidar-table">
            <thead>
              <tr>
                <th>E-mail</th>
                <th>Emitido em</th>
                <th>Vale até</th>
                <th>E-mail enviado</th>
              </tr>
            </thead>
            <tbody>
              {lista.map((c) => (
                <tr key={`${c.email}|${c.issued_at}`}>
                  <td>{c.email}</td>
                  <td>{formatarDataHora(c.issued_at)}</td>
                  <td>{formatarDataHora(c.expires_at)}</td>
                  <td>{c.email_sent ? 'Sim' : 'Não'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
