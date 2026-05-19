import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { useMCRA } from '../store/useMCRA';
import type { LogEntry } from '../types';

const STEPS = [
  { id: 'ingestao', label: 'Ingestão' },
  { id: 'validacao', label: 'Validação' },
  { id: 'pontuacao', label: 'Pontuação' },
  { id: 'snapshot', label: 'Snapshot' },
];

export function Execucao() {
  const { lastRun } = useMCRA();
  const [log, setLog] = useState<LogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .log({ execucao_id: lastRun?.execucao_id, limit: 80 })
      .then((p) => !cancelled && setLog(p.items))
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [lastRun?.execucao_id]);

  // Pipeline status: se há lastRun, todas as etapas concluídas.
  const allDone = !!lastRun;

  return (
    <div className="samid-stack">
      <section className="samid-card">
        <div className="samid-card-head">
          <div>
            <div className="samid-eyebrow">Pipeline · última execução</div>
            <h2 className="samid-card-title">
              {lastRun ? `${lastRun.competencia} · ${lastRun.siconfi}` : 'Nenhuma execução nesta sessão'}
            </h2>
          </div>
          {lastRun && (
            <span
              className={`samid-pill ${
                lastRun.status === 'OK'
                  ? 'samid-pill-ok'
                  : lastRun.status === 'PARCIAL'
                    ? 'samid-pill-alerta'
                    : 'samid-pill-erro'
              }`}
            >
              {lastRun.status}
            </span>
          )}
        </div>

        <div className="samid-pipe">
          {STEPS.map((step, i) => (
            <span key={step.id} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
              <div className={`samid-step${allDone ? ' done' : ''}`}>
                <div className="samid-step-circle">{i + 1}</div>
                <div className="samid-step-label">{step.label}</div>
              </div>
              {i < STEPS.length - 1 && <div className={`samid-step-line${allDone ? ' done' : ''}`} />}
            </span>
          ))}
        </div>

        {lastRun && (
          <dl className="samid-kv">
            <div>
              <dt>Execução</dt>
              <dd className="mono">{lastRun.execucao_id}</dd>
            </div>
            <div>
              <dt>Início</dt>
              <dd className="mono">{lastRun.inicio}</dd>
            </div>
            <div>
              <dt>Fim</dt>
              <dd className="mono">{lastRun.fim}</dd>
            </div>
            <div>
              <dt>Regras executadas</dt>
              <dd className="mono">{lastRun.regras_executadas}</dd>
            </div>
            <div>
              <dt>Regras com erro</dt>
              <dd className="mono">{lastRun.regras_com_erro}</dd>
            </div>
            <div>
              <dt>Pendências</dt>
              <dd className="mono">{lastRun.total_pendencias.toLocaleString('pt-BR')}</dd>
            </div>
          </dl>
        )}
      </section>

      <section className="samid-card">
        <div className="samid-card-head">
          <div>
            <div className="samid-eyebrow">Log JSON Lines</div>
            <h2 className="samid-card-title">
              {lastRun
                ? `Filtrado por execucao_id ${lastRun.execucao_id.slice(0, 8)}…`
                : 'Tail das últimas 80 entradas'}
            </h2>
          </div>
        </div>
        {error && <p className="samid-pill samid-pill-erro">{error}</p>}
        <div className="samid-log">
          {log.length === 0 ? (
            <div style={{ color: 'rgba(255,255,255,.6)' }}>Sem entradas para o filtro atual.</div>
          ) : (
            log.map((e, i) => (
              <div
                key={`${e.ts}-${i}`}
                className={`samid-log-row samid-log-${e.level.toLowerCase()}`}
              >
                <span className="samid-log-t">{e.ts.slice(11, 19)}</span>
                <span className="samid-log-lvl">{e.level}</span>
                <span className="samid-log-msg">{e.msg}</span>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
