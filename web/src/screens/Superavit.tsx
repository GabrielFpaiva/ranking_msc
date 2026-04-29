import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { useMCRA } from '../store/mcra';

interface NotImplementedPayload {
  detail: string;
  code?: string;
  see?: string;
}

export function Superavit() {
  const { siconfi, competencia } = useMCRA();
  const [payload, setPayload] = useState<NotImplementedPayload | null>(null);

  useEffect(() => {
    if (!siconfi || !competencia) return;
    let cancelled = false;
    api
      .superavit(siconfi, competencia)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!cancelled) setPayload(body);
      })
      .catch(() => {
        if (!cancelled) setPayload({ detail: 'Falha ao consultar /api/superavit' });
      });
    return () => {
      cancelled = true;
    };
  }, [siconfi, competencia]);

  return (
    <div className="samid-card">
      <div className="samid-card-head">
        <div>
          <div className="samid-eyebrow">Superávit · resultado financeiro por FR</div>
          <h2 className="samid-card-title">A ser implementado</h2>
        </div>
      </div>
      <p style={{ marginTop: 12 }}>
        {payload?.detail ??
          'Esta tela depende da derivação contábil de resultado financeiro por fonte de recurso, ainda não implementada no motor ranking_msc.'}
      </p>
      <p className="samid-muted" style={{ marginTop: 12 }}>
        Acompanhamento: <span className="mono">F0-04</span> em <span className="mono">doc/fase0_plan.md</span>.
      </p>
    </div>
  );
}
