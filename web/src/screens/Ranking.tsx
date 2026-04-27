import { useEffect, useState } from 'react';

import { api } from '../api/client';

interface NotImplementedPayload {
  detail: string;
  code?: string;
  see?: string;
}

export function Ranking() {
  const [payload, setPayload] = useState<NotImplementedPayload | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .ranking()
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!cancelled) setPayload(body);
      })
      .catch(() => {
        if (!cancelled) setPayload({ detail: 'Falha ao consultar /api/ranking' });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="samid-card">
      <div className="samid-card-head">
        <div>
          <div className="samid-eyebrow">Ranking Regional · PMJP vs outros entes</div>
          <h2 className="samid-card-title">A ser implementado</h2>
        </div>
      </div>
      <p style={{ marginTop: 12 }}>
        {payload?.detail ??
          'Tela depende de fonte de dados regional (planilha SICONFI, API STN ou import de CSVs de outros entes) ainda não integrada ao motor.'}
      </p>
      <p className="samid-muted" style={{ marginTop: 12 }}>
        Acompanhamento: <span className="mono">F0-03</span> em <span className="mono">doc/fase0_plan.md</span>.
      </p>
    </div>
  );
}
