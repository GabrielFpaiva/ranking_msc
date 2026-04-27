import { Placeholder } from '../components/Placeholder';

export function Execucao() {
  return (
    <Placeholder
      fatia="F0-00.E"
      description="Pipeline (Ingestão → Validação → Pontuação → Snapshot), métricas da última run e log JSON-lines — wired via GET /api/run/:id e GET /api/log."
    />
  );
}
