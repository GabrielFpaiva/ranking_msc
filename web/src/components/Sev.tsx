import type { Severidade } from '../types';

const CLASS_BY_LEVEL: Record<Severidade, string> = {
  ERRO: 'samid-pill-erro',
  ALERTA: 'samid-pill-alerta',
  INFO: 'samid-pill-info',
};

const DOT_BY_LEVEL: Record<Severidade, string> = {
  ERRO: 'samid-dot-erro',
  ALERTA: 'samid-dot-alerta',
  INFO: 'samid-dot-info',
};

export function Sev({ level }: { level: Severidade }) {
  return (
    <span className={`samid-pill ${CLASS_BY_LEVEL[level]}`}>
      <span className={`samid-dot ${DOT_BY_LEVEL[level]}`} aria-hidden />
      {level}
    </span>
  );
}
