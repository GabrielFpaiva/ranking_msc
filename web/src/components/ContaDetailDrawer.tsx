import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { Drawer } from './Drawer';
import { useMCRA } from '../store/mcra';
import type { ContaDetail } from '../types';

interface ContaDetailDrawerProps {
  contaContabil: string;
}

function fmtBRL(v: number): string {
  return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

export function ContaDetailDrawer({ contaContabil }: ContaDetailDrawerProps) {
  const { siconfi, competencia } = useMCRA();
  const [conta, setConta] = useState<ContaDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setConta(null);
    if (!siconfi || !competencia) {
      setError('Sem competência ativa — execute uma run em Início primeiro.');
      return;
    }
    api
      .conta(contaContabil, siconfi, competencia)
      .then((c) => !cancelled && setConta(c))
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [contaContabil, siconfi, competencia]);

  if (error) {
    return (
      <Drawer title={contaContabil} eyebrow="Conta · erro">
        <p className="samid-pill samid-pill-erro">{error}</p>
      </Drawer>
    );
  }

  if (!conta) {
    return (
      <Drawer title={contaContabil} eyebrow="Conta · carregando">
        <p className="samid-muted">Carregando detalhes da conta...</p>
      </Drawer>
    );
  }

  const s = conta.saldos;
  const meta = (
    <>
      <span className="mono" style={{ fontWeight: 600 }}>
        {conta.competencia} · {conta.siconfi}
      </span>
      {conta.pendencias_count > 0 && (
        <span className="samid-chip samid-chip-warn">{conta.pendencias_count} pendência(s)</span>
      )}
    </>
  );

  return (
    <Drawer title={conta.conta_contabil} eyebrow="Detalhe da Conta" meta={meta}>
      <section className="samid-drawer-section">
        <div className="samid-eyebrow">Saldos · {conta.competencia}</div>
        <div className="samid-grid-3" style={{ marginTop: 12 }}>
          <Metric label="Saldo Inicial Dev." value={fmtBRL(s.saldo_inicial_devedor)} />
          <Metric label="Saldo Inicial Cred." value={fmtBRL(s.saldo_inicial_credor)} />
          <Metric label="Movimento Dev." value={fmtBRL(s.movimento_devedor)} />
          <Metric label="Movimento Cred." value={fmtBRL(s.movimento_credor)} />
          <Metric label="Saldo Final Dev." value={fmtBRL(s.saldo_final_devedor)} />
          <Metric label="Saldo Final Cred." value={fmtBRL(s.saldo_final_credor)} />
        </div>
      </section>

      {conta.pcasp && Object.keys(conta.pcasp).length > 0 && (
        <section className="samid-drawer-section">
          <div className="samid-eyebrow">PCASP</div>
          <div className="samid-conta-ic">
            {Object.entries(conta.pcasp).map(([k, v]) => (
              <div key={k} className="samid-conta-icitem">
                <div className="samid-eyebrow" style={{ marginBottom: 4 }}>
                  {k}
                </div>
                <div className="mono" style={{ fontWeight: 600 }}>
                  {v}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {Object.keys(conta.classificadores).length > 0 && (
        <section className="samid-drawer-section">
          <div className="samid-eyebrow">Classificadores informados</div>
          <div className="samid-conta-ic">
            {Object.entries(conta.classificadores).map(([k, v]) => (
              <div key={k} className="samid-conta-icitem">
                <div className="samid-eyebrow" style={{ marginBottom: 4 }}>
                  {k.toUpperCase()}
                </div>
                <div className="mono" style={{ fontWeight: 600 }}>
                  {v}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </Drawer>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="samid-metric">
      <div className="samid-metric-lbl">{label}</div>
      <div className="samid-metric-val mono" style={{ fontSize: 18 }}>
        {value}
      </div>
    </div>
  );
}
