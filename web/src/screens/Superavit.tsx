import { useEffect, useState } from 'react';

import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useMCRA } from '../store/useMCRA';
import { fmtBRL } from '../format';
import type { SuperavitData } from '../types';

export function Superavit() {
  const { siconfi, competencia } = useMCRA();
  const [payload, setPayload] = useState<SuperavitData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!siconfi || !competencia) return;
    let cancelled = false;
    api
      .superavit(siconfi, competencia)
      .then((body) => {
        if (!cancelled) {
          setPayload(body);
          setError(null);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setPayload(null);
          setError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [siconfi, competencia]);

  if (!siconfi || !competencia) {
    return (
      <div className="samid-card">
        <div className="samid-eyebrow">Superávit</div>
        <h2 className="samid-card-title" style={{ marginTop: 8 }}>
          Sem competência ativa
        </h2>
        <p className="samid-muted">
          Processe um CSV MSC para popular esta tela.
        </p>
        <Link to="/inicio" className="samid-btn samid-btn-primary" style={{ marginTop: 12, display: 'inline-flex' }}>
          Ir para Início
        </Link>
      </div>
    );
  }

  return (
    <div className="samid-stack">
      {error && <p className="samid-pill samid-pill-erro">{error}</p>}

      {payload && (
        <section className="samid-card">
          <div className="samid-card-head">
            <div>
              <div className="samid-eyebrow">Superávit · resultado financeiro por FR</div>
              <h2 className="samid-card-title">Consolidado da competência ativa</h2>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="samid-eyebrow">Resultado total</div>
              <div className="mono" style={{ fontWeight: 700, fontSize: 18 }}>
                {fmtBRL(payload.total_resultado_financeiro)}
              </div>
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
              gap: 12,
              marginTop: 16,
            }}
          >
            <div className="samid-kpi">
              <div className="samid-eyebrow">Ativo Financeiro</div>
              <div className="mono" style={{ fontWeight: 700 }}>
                {fmtBRL(payload.total_ativo_financeiro)}
              </div>
            </div>
            <div className="samid-kpi">
              <div className="samid-eyebrow">Passivo Financeiro</div>
              <div className="mono" style={{ fontWeight: 700 }}>
                {fmtBRL(payload.total_passivo_financeiro)}
              </div>
            </div>
            <div className="samid-kpi">
              <div className="samid-eyebrow">Escopo</div>
              <div className="mono" style={{ fontWeight: 700 }}>
                {payload.contas_consideradas} conta(s) · {payload.linhas_consideradas} linha(s)
              </div>
            </div>
          </div>
        </section>
      )}

      {payload?.items.length ? (
        <section className="samid-card">
          <div className="samid-card-head">
            <div>
              <div className="samid-eyebrow">Fonte de recurso</div>
              <h2 className="samid-card-title">Detalhamento por FR</h2>
            </div>
          </div>

          <table className="samid-table samid-table-dense" style={{ marginTop: 12 }}>
            <thead>
              <tr>
                <th>FR</th>
                <th style={{ textAlign: 'right' }}>Ativo</th>
                <th style={{ textAlign: 'right' }}>Passivo</th>
                <th style={{ textAlign: 'right' }}>Resultado</th>
              </tr>
            </thead>
            <tbody>
              {payload.items.map((item) => (
                <tr key={item.fr}>
                  <td className="mono" style={{ fontWeight: 600 }}>{item.fr}</td>
                  <td className="mono" style={{ textAlign: 'right' }}>
                    {fmtBRL(item.ativo_financeiro)}
                  </td>
                  <td className="mono" style={{ textAlign: 'right' }}>
                    {fmtBRL(item.passivo_financeiro)}
                  </td>
                  <td className="mono" style={{ textAlign: 'right', fontWeight: 700 }}>
                    {fmtBRL(item.resultado_financeiro)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {payload && payload.items.length === 0 && !error && (
        <div className="samid-card">
          <div className="samid-eyebrow">Sem linhas elegíveis</div>
          <h2 className="samid-card-title" style={{ marginTop: 8 }}>
            Nenhum resultado financeiro por FR nesta competência
          </h2>
          <p className="samid-muted" style={{ marginTop: 12 }}>
            O cálculo considera apenas contas com <span className="mono">ind_sf = Financeiro</span>,
            natureza devedora ou credora, e <span className="mono">FR</span> preenchida.
          </p>
        </div>
      )}

      {!payload && !error && <p className="samid-muted">Carregando resultado financeiro por FR...</p>}
    </div>
  );
}
