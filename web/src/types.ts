// Tipos compartilhados — espelham app/api/schemas.py.
// Mantenha em sincronia: ao mudar pydantic schema, atualize aqui.

export type Severidade = 'ERRO' | 'ALERTA' | 'INFO';
export type Banda = 'A' | 'B' | 'C' | 'D' | 'E';
export type RunStatus = 'OK' | 'PARCIAL' | 'ERRO';

export interface DimensionScore {
  dimension: string;
  score: number;
  weight_normalized: number;
  rules_total: number;
  rules_passed: number;
  rules_failed_alerta: number;
  rules_failed_erro: number;
}

export interface Score {
  pontuacao: number;
  banda: Banda;
  dimensions: Record<string, DimensionScore>;
  regras_executadas: number;
  regras_falhas_erro: number;
  regras_falhas_alerta: number;
}

export interface Summary {
  siconfi: string;
  competencia: string;
  total_pendencias: number;
  score: Score;
  top_regras: TopRule[];
}

export interface TopRule {
  regra_id: string;
  regra_nome: string;
  dimensao: string;
  severidade_max: Severidade;
  pendencias: number;
}

export interface Competencia {
  siconfi: string;
  competencia: string;
  has_resultado: boolean;
}

export interface RunSummary {
  execucao_id: string;
  siconfi: string;
  competencia: string;
  status: RunStatus;
  regras_executadas: number;
  regras_com_erro: number;
  total_pendencias: number;
  score: Score;
  top_regras: TopRule[];
  inicio: string;
  fim: string;
}

export interface Pendencia {
  regra_id: string;
  regra_nome: string;
  dimensao: string;
  severidade: Severidade;
  conta_contabil: string;
  descricao: string;
  valor_esperado: string | null;
  valor_encontrado: string | null;
  competencia: string;
}

export interface PendenciasPage {
  competencia: string;
  siconfi: string;
  total: number;
  items: Pendencia[];
}

export interface ScoreHistoryPoint {
  competencia: string;
  pontuacao: number;
  banda: Banda;
  total_pendencias: number;
}

export interface ScoreHistory {
  siconfi: string;
  points: ScoreHistoryPoint[];
}

// ---------- Regras / Heatmap / Drawer Regra (fatia C) ----------

export interface Rule {
  rule_id: string;
  rule_name: string;
  dimensao: string;
  is_scoring: boolean;
}

export interface RuleDetail extends Rule {
  descricao: string;
  formula: string | null;
}

export interface HeatmapCell {
  regra_id: string;
  competencia: string;
  pendencias: number;
  severidade_max: Severidade | null;
}

export interface HeatmapRegra {
  id: string;
  nome: string;
  dimensao: string;
}

export interface Heatmap {
  siconfi: string;
  competencias: string[];
  regras: HeatmapRegra[];
  cells: HeatmapCell[];
}

export interface RuleHistory {
  siconfi: string;
  rule_id: string;
  cells: HeatmapCell[];
}

// ---------- Drawer Conta ----------

export interface ContaSaldos {
  saldo_inicial_devedor: number;
  saldo_inicial_credor: number;
  movimento_devedor: number;
  movimento_credor: number;
  saldo_final_devedor: number;
  saldo_final_credor: number;
}

export interface ContaDetail {
  conta_contabil: string;
  competencia: string;
  siconfi: string;
  saldos: ContaSaldos;
  classificadores: Record<string, string>;
  pcasp: Record<string, string> | null;
  pendencias_count: number;
}

// ---------- Caixa / Passivos (fatia D) ----------

export interface ContaResumo {
  conta_contabil: string;
  saldo_inicial: number;
  saldo_final: number;
  movimento_liquido: number;
  fr: string | null;
}

export interface ContaListGroup {
  label: string;
  prefixes: string[];
  total_saldo_final: number;
  items: ContaResumo[];
}

export interface ContaList {
  siconfi: string;
  competencia: string;
  groups: ContaListGroup[];
}

export interface SuperavitRow {
  fr: string;
  ativo_financeiro: number;
  passivo_financeiro: number;
  resultado_financeiro: number;
}

export interface SuperavitData {
  siconfi: string;
  competencia: string;
  total_ativo_financeiro: number;
  total_passivo_financeiro: number;
  total_resultado_financeiro: number;
  linhas_consideradas: number;
  contas_consideradas: number;
  items: SuperavitRow[];
}

// ---------- Visões / Executivo / Comparar / Log (fatia E) ----------

export interface Recommendation {
  titulo: string;
  descricao: string;
  severidade: Severidade;
  referencia: string | null;
}

export interface Recommendations {
  siconfi: string;
  competencia: string;
  items: Recommendation[];
}

export interface CompareDimension {
  dimension: string;
  score_a: number;
  score_b: number;
  delta: number;
}

export interface CompareSide {
  competencia: string;
  pontuacao: number;
  banda: Banda;
  total_pendencias: number;
}

export interface Compare {
  siconfi: string;
  a: CompareSide;
  b: CompareSide;
  delta_score: number;
  delta_pendencias: number;
  dimensions: CompareDimension[];
}

export interface LogEntry {
  ts: string;
  level: string;
  msg: string;
  execucao_id: string | null;
  competencia: string | null;
  modulo: string | null;
  regra_id: string | null;
  siconfi: string | null;
}

export interface LogPage {
  total: number;
  items: LogEntry[];
}

// ---------- Entregas / Gestão da Informação (Dimensão I) ----------

export interface Entrega {
  instituicao: string;
  entregavel: string;
  periodo: number;
  periodicidade: string;
  status: 'HOMOLOGADO' | 'RETIFICADO' | 'SEM_STATUS';
  data_status: string | null;
  fim_periodo: string | null;
  dias_apos_fim_periodo: number | null;
  prazo_dias: number | null;
  /** null = sem base para julgar. Nunca renderizar como "no prazo". */
  atrasada: boolean | null;
}

export interface ResumoEntregas {
  total: number;
  homologadas: number;
  retificadas: number;
}

export interface EntregasResponse {
  ano: number;
  id_ente: number;
  origem: 'api' | 'cache' | 'indisponivel';
  buscado_em: string | null;
  aviso: string | null;
  resumo: ResumoEntregas;
  entregas: Entrega[];
}

// ---------- Tempo de uso ----------

export interface UsoHoje {
  aberto_s: number;
  ativo_s: number;
}

export interface UsoDia {
  dia: string;
  aberto_s: number;
  ativo_s: number;
}

export interface UsoRota {
  rota: string;
  aberto_s: number;
  ativo_s: number;
}

export type EscalaUso = 'dia' | 'semana' | 'mes';

export interface UsoHistorico {
  escala: EscalaUso;
  ref: string;
  inicio: string;
  fim: string;
  total_aberto_s: number;
  total_ativo_s: number;
  dias: UsoDia[];
  rotas: UsoRota[];
}

export interface UsoMes {
  mes: string;
  aberto_s: number;
  ativo_s: number;
}

export interface UsoAnual {
  ano: number;
  total_aberto_s: number;
  total_ativo_s: number;
  meses: UsoMes[];
}
