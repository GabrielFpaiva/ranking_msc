// Badge do rodapé da sidebar: tempo total de uso hoje, com link para /uso.

import { useEffect, useState } from 'react';

import { NavLink } from 'react-router-dom';

import { api } from '../api/client';
import { formatarDuracao } from '../format';

const INTERVALO_ATUALIZACAO_MS = 60_000;

/** Bloco do rodapé da sidebar: tempo total de hoje, com link para /uso. */
export function UsoMini() {
  const [abertoS, setAbertoS] = useState<number | null>(null);

  useEffect(() => {
    let cancelado = false;

    function buscar(): void {
      api
        .usoHoje()
        .then((uso) => {
          if (!cancelado) setAbertoS(uso.aberto_s);
        })
        .catch(() => {
          if (!cancelado) setAbertoS(null);
        });
    }

    buscar();
    const timer = window.setInterval(buscar, INTERVALO_ATUALIZACAO_MS);
    return () => {
      cancelado = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <NavLink
      to="/uso"
      className={({ isActive }) => `uso-mini${isActive ? ' active' : ''}`}
      aria-label="Meu tempo de uso"
    >
      <span className="uso-mini-clock" aria-hidden />
      <span className="uso-mini-txt">
        <span className="uso-mini-val">{abertoS === null ? '—' : formatarDuracao(abertoS)}</span>
        <span className="uso-mini-lbl">hoje</span>
      </span>
      <span className="uso-mini-arrow" aria-hidden>
        ›
      </span>
    </NavLink>
  );
}
