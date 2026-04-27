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
