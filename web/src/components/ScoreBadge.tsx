import type { CSSProperties } from 'react';

import type { Banda } from '../types';

const BAND_COLOR: Record<Banda, string> = {
  A: 'var(--samid-band-a)',
  B: 'var(--samid-band-b)',
  C: 'var(--samid-band-c)',
  D: 'var(--samid-band-d)',
  E: 'var(--samid-band-e)',
};

interface ScoreBadgeProps {
  pontuacao: number;
  banda: Banda;
  size?: 'md' | 'lg';
}

export function ScoreBadge({ pontuacao, banda, size = 'md' }: ScoreBadgeProps) {
  const ringStyle: CSSProperties = {
    background: `conic-gradient(${BAND_COLOR[banda]} ${Math.max(0, Math.min(100, pontuacao))}%, var(--bg-sunken) 0)`,
  };
  return (
    <div className={`samid-score${size === 'lg' ? ' samid-score-lg' : ''}`}>
      <div className="samid-score-ring" style={ringStyle}>
        <div className="samid-score-inner">
          <div className="samid-score-num">{pontuacao.toFixed(1).replace('.', ',')}</div>
          <div className="samid-score-of">/ 100</div>
        </div>
      </div>
      <div>
        <div className="samid-score-band" style={{ color: BAND_COLOR[banda] }}>
          BANDA {banda}
        </div>
        <div className="samid-score-name">Conformidade MSC</div>
      </div>
    </div>
  );
}
