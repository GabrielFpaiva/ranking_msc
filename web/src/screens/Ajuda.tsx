import { type ReactElement, useState } from 'react';
import { Link } from 'react-router-dom';

import faq from '../ajuda/faq.json';
import { authStore } from '../store/auth';

/**
 * Tela pública de ajuda: FAQ em acordeão, uma pergunta aberta por vez.
 *
 * Não chama a API (funciona sem login e sem rede). O conteúdo vem de
 * `ajuda/faq.json`, fonte única também usada pelo FAQ em HTML do e-mail.
 */
export function Ajuda(): ReactElement {
  const [aberta, setAberta] = useState<string | null>(null);
  const voltar = authStore.isAuthenticated() ? '/inicio' : '/login';

  return (
    <div className="samid-ajuda-page">
      <header className="samid-ajuda-head">
        <Link to={voltar} className="samid-ajuda-back">
          ← Voltar
        </Link>
        <h1 className="samid-ajuda-title">Ajuda</h1>
        <p className="samid-ajuda-sub">Perguntas frequentes sobre o uso do MCRA.</p>
      </header>

      <ul className="samid-ajuda-list">
        {faq.map((item) => {
          const isOpen = aberta === item.id;
          return (
            <li key={item.id} className="samid-ajuda-item">
              <button
                type="button"
                className="samid-ajuda-q"
                aria-expanded={isOpen}
                aria-controls={`ajuda-${item.id}`}
                onClick={() => setAberta(isOpen ? null : item.id)}
              >
                {item.pergunta}
              </button>
              {isOpen && (
                <div id={`ajuda-${item.id}`} className="samid-ajuda-a">
                  <ol className="samid-ajuda-steps">
                    {item.passos.map((passo) => (
                      <li key={passo}>{passo}</li>
                    ))}
                  </ol>
                  {'gif' in item && (
                    <img
                      className="samid-ajuda-gif"
                      src={`/ajuda/${item.gif}`}
                      alt={item.pergunta}
                      loading="lazy"
                    />
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
