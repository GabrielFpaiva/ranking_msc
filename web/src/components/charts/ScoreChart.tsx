import type { ScoreHistoryPoint } from '../../types';

interface ScoreChartProps {
  points: ScoreHistoryPoint[];
  width?: number;
  height?: number;
}

export function ScoreChart({ points, width = 540, height = 160 }: ScoreChartProps) {
  if (points.length === 0) {
    return (
      <div className="samid-muted" style={{ padding: 24, textAlign: 'center' }}>
        Sem histórico — execute uma competência para começar a linha do tempo.
      </div>
    );
  }

  const padding = { top: 12, right: 16, bottom: 28, left: 28 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const minY = 0;
  const maxY = 100;

  const x = (i: number) =>
    points.length === 1
      ? padding.left + innerW / 2
      : padding.left + (i / (points.length - 1)) * innerW;
  const y = (v: number) =>
    padding.top + innerH - ((v - minY) / (maxY - minY)) * innerH;

  const path = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(p.pontuacao)}`)
    .join(' ');

  const last = points[points.length - 1];

  return (
    <div>
      <svg width={width} height={height} role="img" aria-label="Evolução de score">
        {[0, 25, 50, 75, 100].map((v) => (
          <line
            key={v}
            x1={padding.left}
            x2={width - padding.right}
            y1={y(v)}
            y2={y(v)}
            stroke="var(--border-subtle)"
            strokeDasharray="2 4"
          />
        ))}
        <path d={path} fill="none" stroke="var(--samid-midnight)" strokeWidth={2} />
        {points.map((p, i) => (
          <circle
            key={`${p.competencia}-${i}`}
            cx={x(i)}
            cy={y(p.pontuacao)}
            r={i === points.length - 1 ? 5 : 3}
            fill={i === points.length - 1 ? 'var(--samid-gold)' : 'var(--samid-midnight)'}
          />
        ))}
        {points.map((p, i) => (
          <text
            key={`lbl-${p.competencia}-${i}`}
            x={x(i)}
            y={height - 8}
            textAnchor="middle"
            fontSize="10"
            fontFamily="var(--font-mono)"
            fill="var(--fg-2)"
          >
            {p.competencia}
          </text>
        ))}
      </svg>
      <div className="samid-evol-legend">
        <span>
          <b>{last.pontuacao.toFixed(1).replace('.', ',')}</b> · banda {last.banda}
        </span>
        <span>{last.total_pendencias} pendência(s)</span>
      </div>
    </div>
  );
}
