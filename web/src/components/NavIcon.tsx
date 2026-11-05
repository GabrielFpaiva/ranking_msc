/**
 * Conjunto minimalista de ícones SVG inline para a navegação.
 *
 * Mantido sem dependência externa (segue o padrão de SVGs inline do projeto).
 * Cada ícone usa `currentColor` para herdar a cor do item de navegação.
 */

export type IconName =
  | 'inicio'
  | 'pendencias'
  | 'caixa'
  | 'passivos'
  | 'superavit'
  | 'executivo'
  | 'comparar'
  | 'entregas'
  | 'regras'
  | 'execucao'
  | 'ajuda'
  | 'sair';

const PATHS: Record<IconName, string> = {
  // casa
  inicio: 'M3 10.5 12 3l9 7.5M5 10v10h14V10',
  // lista de itens
  pendencias: 'M8 6h12M8 12h12M8 18h12M3.5 6h.01M3.5 12h.01M3.5 18h.01',
  // carteira / caixa
  caixa: 'M3 7a2 2 0 0 1 2-2h12v3M3 7v11a2 2 0 0 0 2 2h14V9H5a2 2 0 0 1-2-2m14.5 6h.01',
  // documento (passivos)
  passivos: 'M6 2h8l4 4v16H6zM14 2v4h4',
  // tendência de alta (superávit)
  superavit: 'M3 17l6-6 4 4 7-7M17 8h4v4',
  // prancheta (executivo)
  executivo: 'M9 4h6v3H9zM7 5H5v16h14V5h-2',
  // comparar (duas setas)
  comparar: 'M7 4v16M3 8l4-4 4 4M17 20V4M13 16l4 4 4-4',
  // calendário com check (entregas)
  entregas: 'M5 4h14v16H5zM5 9h14M8 2v4M16 2v4M8.5 14l2 2 4-4',
  // livro (regras)
  regras: 'M5 4a2 2 0 0 1 2-2h11v18H7a2 2 0 0 0-2 2zM9 2v18',
  // pulso / atividade (execução)
  execucao: 'M3 12h4l3 8 4-16 3 8h4',
  // interrogação (ajuda)
  ajuda: 'M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 1-1 1.7M12 17h.01M3 12a9 9 0 1 0 18 0 9 9 0 0 0-18 0',
  // logout (sair)
  sair: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
};

interface NavIconProps {
  name: IconName;
  size?: number;
}

export function NavIcon({ name, size = 18 }: NavIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      style={{ flexShrink: 0 }}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
