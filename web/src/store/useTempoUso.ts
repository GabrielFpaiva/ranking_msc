// Liga o RelogioUso aos eventos do browser e à API.
//
// Montado uma única vez, no Layout — que só renderiza para rotas autenticadas,
// então /login nunca conta.

import { useEffect, useRef } from 'react';

import { useLocation } from 'react-router-dom';

import { api } from '../api/client';
import { RelogioUso } from './relogioUso';

const INTERVALO_HEARTBEAT_MS = 60_000;
const EVENTOS_DE_INTERACAO = ['pointerdown', 'keydown', 'wheel', 'touchstart'] as const;

export function useTempoUso(): void {
  const { pathname } = useLocation();
  const relogioRef = useRef<RelogioUso | null>(null);

  if (relogioRef.current === null) {
    relogioRef.current = new RelogioUso(pathname, Date.now());
  }

  // Troca de rota fecha o balde anterior.
  useEffect(() => {
    relogioRef.current?.setRota(pathname, Date.now());
  }, [pathname]);

  useEffect(() => {
    const relogio = relogioRef.current;
    if (!relogio) return;

    // `manterVivo` só é passado como `true` a partir do handler de
    // `pagehide` — ver o comentário de `api.usoHeartbeat` em `api/client.ts`
    // sobre por que esse envio específico precisa de `keepalive` e por que
    // não é `sendBeacon`. Os demais chamadores (intervalo, visibilitychange,
    // cleanup de desmontagem — que não é descarregamento de página) seguem
    // com o `fetch` normal.
    function enviar(manterVivo = false): void {
      if (!relogio) return;
      relogio.tick(Date.now());
      for (const balde of relogio.colher()) {
        void api.usoHeartbeat(balde.rota, balde.aberto_s, balde.ativo_s, { manterVivo }).catch(() => {
          // Tempo de uso não é dado crítico: falha de rede não pode virar erro
          // na tela nem bloquear o trabalho. O intervalo perdido é descartado.
        });
      }
    }

    function aoInteragir(): void {
      relogio?.marcarInteracao(Date.now());
    }

    function aoTrocarVisibilidade(): void {
      const visivel = document.visibilityState === 'visible';
      relogio?.setVisivel(visivel, Date.now());
      if (!visivel) enviar();
    }

    function aoDescarregar(): void {
      enviar(true);
    }

    const timer = window.setInterval(() => enviar(), INTERVALO_HEARTBEAT_MS);
    for (const evento of EVENTOS_DE_INTERACAO) {
      window.addEventListener(evento, aoInteragir, { passive: true });
    }
    document.addEventListener('visibilitychange', aoTrocarVisibilidade);
    window.addEventListener('pagehide', aoDescarregar);

    return () => {
      window.clearInterval(timer);
      for (const evento of EVENTOS_DE_INTERACAO) {
        window.removeEventListener(evento, aoInteragir);
      }
      document.removeEventListener('visibilitychange', aoTrocarVisibilidade);
      window.removeEventListener('pagehide', aoDescarregar);
      enviar();
    };
  }, []);
}
