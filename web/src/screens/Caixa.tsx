import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { ContaListSection } from '../components/ContaListSection';
import { useMCRA } from '../store/mcra';
import type { ContaList } from '../types';

export function Caixa() {
  const { siconfi, competencia } = useMCRA();
  const [list, setList] = useState<ContaList | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!siconfi || !competencia) return;
    let cancelled = false;
    api
      .caixa(siconfi, competencia)
      .then((l) => !cancelled && setList(l))
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [siconfi, competencia]);

  if (!siconfi || !competencia) {
    return (
      <div className="samid-card">
        <div className="samid-eyebrow">Caixa</div>
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
      {!list && !error && <p className="samid-muted">Carregando disponibilidades...</p>}
    </div>
  );
}
