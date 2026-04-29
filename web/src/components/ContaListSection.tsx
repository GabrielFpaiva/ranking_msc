import { useDrawer } from '../store/drawer';
import type { ContaListGroup } from '../types';

function fmtBRL(v: number): string {
  return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function summarizeFR(fr: string | null): string {
  if (!fr) return '—';
  const parts = fr.split(',').map((s) => s.trim()).filter(Boolean);
  if (parts.length <= 1) return fr;
  return `${parts[0]} (+${parts.length - 1})`;
}

interface ContaListSectionProps {
  group: ContaListGroup;
}

export function ContaListSection({ group }: ContaListSectionProps) {
  const { openConta } = useDrawer();
  return (
    <section className="samid-card">
      <div className="samid-card-head">
        <div>
          <div className="samid-eyebrow">{group.prefixes.join(' · ')}</div>
          <h2 className="samid-card-title">{group.label}</h2>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="samid-eyebrow">Total saldo final</div>
          <div className="mono" style={{ fontWeight: 700, fontSize: 18 }}>
            {fmtBRL(group.total_saldo_final)}
          </div>
        </div>
      </div>

      {group.items.length === 0 ? (
        <p className="samid-muted">Nenhuma conta neste grupo na competência ativa.</p>
      ) : (
        <table className="samid-table samid-table-dense">
          <thead>
            <tr>
              <th>Conta</th>
              <th style={{ textAlign: 'right' }}>Saldo Inicial</th>
              <th style={{ textAlign: 'right' }}>Movimento Líquido</th>
              <th style={{ textAlign: 'right' }}>Saldo Final</th>
              <th>FR</th>
            </tr>
          </thead>
          <tbody>
            {group.items.map((c) => (
              <tr
                key={c.conta_contabil}
                onClick={() => openConta(c.conta_contabil)}
                title="Abrir detalhe da conta"
              >
                <td className="mono" style={{ fontWeight: 600 }}>
                  {c.conta_contabil}
                </td>
                <td className="mono" style={{ textAlign: 'right' }}>
                  {fmtBRL(c.saldo_inicial)}
                </td>
                <td className="mono" style={{ textAlign: 'right' }}>
                  {fmtBRL(c.movimento_liquido)}
                </td>
                <td className="mono" style={{ textAlign: 'right', fontWeight: 600 }}>
                  {fmtBRL(c.saldo_final)}
                </td>
                <td className="mono samid-muted" title={c.fr ?? ''}>
                  {summarizeFR(c.fr)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
