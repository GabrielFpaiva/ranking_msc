/**
 * Mapa rota → título amigável do SPA.
 *
 * Vivia dentro de `TopBar.tsx`, mas isso disparava o aviso do eslint
 * `react-refresh/only-export-components` (fast refresh só funciona direito
 * quando um arquivo de componente só exporta componentes) — `MeuTempo.tsx`
 * importava este mapa de um arquivo de componente que não é o dele. Mora
 * aqui, num módulo compartilhado sem componente nenhum, no mesmo espírito de
 * `format.ts`.
 *
 * `TopBar` usa para o breadcrumb/título do cabeçalho; `MeuTempo` reaproveita
 * para rotular "Por tela" — um só lugar de verdade evita duplicar o mesmo
 * mapa rota → nome amigável.
 */
export const ROUTE_TITLES: Record<string, { breadcrumb: string; title: string }> = {
  '/inicio': { breadcrumb: 'Análise', title: 'Início' },
  '/pendencias': { breadcrumb: 'Análise', title: 'Pendências' },
  '/caixa': { breadcrumb: 'Contas', title: 'Caixa' },
  '/passivos': { breadcrumb: 'Contas', title: 'Passivos' },
  '/superavit': { breadcrumb: 'Contas', title: 'Superávit' },
  '/executivo': { breadcrumb: 'Visões', title: 'Visão Executiva' },
  '/comparar': { breadcrumb: 'Visões', title: 'Comparar Competências' },
  '/entregas': { breadcrumb: 'Visões', title: 'Entregas' },
  '/regras': { breadcrumb: 'Referência', title: 'Regras' },
  '/execucao': { breadcrumb: 'Referência', title: 'Execução' },
  '/uso': { breadcrumb: 'Minha conta', title: 'Meu tempo de uso' },
  '/convidar': { breadcrumb: 'Administração', title: 'Convidar colaborador' },
};
