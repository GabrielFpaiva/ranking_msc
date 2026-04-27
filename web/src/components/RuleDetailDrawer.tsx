import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { DimTag } from './DimTag';
import { Drawer } from './Drawer';
import { Sev } from './Sev';
import { useMCRA } from '../store/mcra';
import type { HeatmapCell, RuleDetail } from '../types';

interface RuleDetailDrawerProps {
  ruleId: string;
}

export function RuleDetailDrawer({ ruleId }: RuleDetailDrawerProps) {
  const { siconfi } = useMCRA();
  const [rule, setRule] = useState<RuleDetail | null>(null);
  const [history, setHistory] = useState<HeatmapCell[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .rule(ruleId)
      .then((r) => {
        if (!cancelled) setRule(r);
      })
      .catch((err: Error) => !cancelled && setError(err.message));
    if (siconfi) {
      api
        .ruleHistory(siconfi, ruleId, 6)
        .then((h) => {
          if (!cancelled) setHistory(h.cells);
        })
        .catch(() => {
          if (!cancelled) setHistory([]);
        });
    }
    return () => {
      cancelled = true;
    };
  }, [ruleId, siconfi]);

  if (error) {
    return (
      <Drawer title={ruleId} eyebrow="Regra · erro">
        <p className="samid-pill samid-pill-erro">{error}</p>
      </Drawer>
    );
  }

  if (!rule) {
    return (
      <Drawer title={ruleId} eyebrow="Regra · carregando">
        <p className="samid-muted">Carregando detalhes da regra...</p>
      </Drawer>
    );
  }

  const meta = (
    <>
      <span className="mono" style={{ fontWeight: 600 }}>
        {rule.rule_id}
      </span>
      <DimTag name={rule.dimensao} />
      {!rule.is_scoring && <span className="samid-chip">INFO-only (não pontua)</span>}
    </>
  );

  return (
    <Drawer title={rule.rule_name} eyebrow="Detalhe da Regra" meta={meta}>
      <section className="samid-drawer-section">
        <div className="samid-eyebrow">Descrição</div>
        <p>{rule.descricao}</p>
      </section>

      {rule.formula && (
        <section className="samid-drawer-section">
          <div className="samid-eyebrow">Lógica</div>
          <pre className="samid-formula" style={{ whiteSpace: 'pre-wrap' }}>
            {rule.formula}
          </pre>
        </section>
      )}

      <section className="samid-drawer-section">
        <div className="samid-eyebrow">Histórico · 6 meses</div>
        {history.length === 0 ? (
          <p className="samid-muted">Sem histórico para este ente.</p>
        ) : (
          <div className="samid-bars" style={{ marginTop: 8 }}>
            {history.map((c) => {
              const max = Math.max(1, ...history.map((h) => h.pendencias));
              const pct = (c.pendencias / max) * 100;
              const fillClass =
                c.severidade_max === 'ERRO'
                  ? 'samid-bar-erro'
                  : c.severidade_max === 'ALERTA'
                    ? 'samid-bar-alerta'
                    : 'samid-bar-info';
              return (
                <div key={c.competencia} className="samid-bar-row" style={{ cursor: 'default' }}>
                  <div className="samid-bar-rid">{c.competencia}</div>
                  <div className="samid-bar-nome">
                    {c.pendencias === 0 ? 'sem pendências' : `${c.pendencias} pendência(s)`}
                  </div>
                  <span className="samid-dim" style={{ visibility: 'hidden' }}>—</span>
                  {c.severidade_max ? <Sev level={c.severidade_max} /> : <span className="samid-muted">—</span>}
                  <div className="samid-bar-track">
                    <div className={`samid-bar-fill ${fillClass}`} style={{ width: `${pct}%` }} />
                  </div>
                  <div className="samid-bar-qty">{c.pendencias.toLocaleString('pt-BR')}</div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </Drawer>
  );
}
