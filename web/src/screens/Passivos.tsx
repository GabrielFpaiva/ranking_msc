import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { ContaListSection } from '../components/ContaListSection';
import { useMCRA } from '../store/useMCRA';
import type { ContaList } from '../types';

export function Passivos() {
  const { siconfi, competencia } = useMCRA();
  const [list, setList] = useState<ContaList | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!siconfi || !competencia) return;
    let cancelled = false;
    // Limpa o payload anterior antes da nova busca para não exibir dados de
    // outra competência sob o cabeçalho já trocado (request lenta ou com erro).
    setList(null);
    setError(null);
    api
      .passivos(siconfi, competencia)
      .then((l) => !cancelled && setList(l))
      .catch((err: Error) => {
        if (!cancelled) {
          setList(null);
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
        <div className="samid-eyebrow">Passivos</div>
        <h2 className="samid-card-title" style={{ marginTop: 8 }}>
          Sem competência ativa
        </h2>
        <p className="samid-muted">
          Volte para Início e processe um CSV MSC para popular esta tela.
        </p>
      </div>
    );
  }

  return (
    <div className="samid-stack">
      {error && <p className="samid-pill samid-pill-erro">{error}</p>}
      {list?.groups.map((g) => (
        <ContaListSection key={g.label} group={g} />
      ))}
      {!list && !error && <p className="samid-muted">Carregando obrigações...</p>}
    </div>
  );
}
