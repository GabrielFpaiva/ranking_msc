// Tela de Entregas — extrato de entregas ao Siconfi (Dimensão I).
//
// Consome GET /api/entregas?ano=YYYY, que devolve sempre HTTP 200. Os três
// campos `origem`, `aviso` e `buscado_em` respondem perguntas independentes
// — ver a documentação em app/api/routes/entregas.py. O gatilho do banner de
// degradação é `aviso !== null`, nunca `origem !== 'api'`.

import { useEffect, useState } from 'react';

import { ApiError, api } from '../api/client';
import type { Entrega, EntregasResponse } from '../types';

const ANO_ATUAL = new Date().getFullYear();
const ANOS = Array.from({ length: 5 }, (_, i) => ANO_ATUAL - i);

/** Formata uma data ISO (`YYYY-MM-DD...`) como `DD/MM/AAAA`.
 *
 * Faz isso por fatiamento de string, não com `new Date(...).toLocaleDateString`
 * — o backend guarda `data_status` naive de propósito (ver `_parse_data` em
 * `siconfi/entregas.py`), e `Date` interpretaria um sufixo `Z` como UTC,
 * arriscando deslocar o dia por fuso. Ver o mesmo cuidado no domínio Python.
 */
function formatarData(iso: string): string {
  const [ano, mes, dia] = iso.slice(0, 10).split('-');
  return `${dia}/${mes}/${ano}`;
}

/** Rótulo da situação de prazo.
 *
 * `atrasada === null` significa "sem base para julgar" (prazo não configurado
 * ou período indecifrável) — NUNCA renderizar "no prazo" a partir disso.
 * Mostrar apenas o fato: quantos dias se passaram.
 *
 * Para RETIFICADO, `dias_apos_fim_periodo` mede distância até a
 * RETIFICAÇÃO, não até a entrega original — não é a mesma grandeza que para
 * HOMOLOGADO. Por isso nunca aparece como "N dias" aqui: mostramos a data da
 * retificação em vez do contador, para não sugerir que aquele número é o
 * atraso da entrega original (ver C1 em `siconfi/entregas.py::classificar`).
 */
function situacaoPrazo(e: Entrega): string {
  if (e.status === 'RETIFICADO') {
    return e.data_status ? `retificado em ${formatarData(e.data_status)}` : 'retificado';
  }
  if (e.dias_apos_fim_periodo === null) return '—';
  const dias = `${e.dias_apos_fim_periodo} dias`;
  if (e.atrasada === null) return dias;
  return e.atrasada ? `${dias} (fora do prazo)` : `${dias} (no prazo)`;
}

/** Banner de degradação.
 *
 * O gatilho é `aviso`, NÃO `origem`. Os três campos respondem perguntas
 * independentes: `origem` diz de onde o dado veio, `aviso` diz se houve
 * degradação, `buscado_em` diz a idade. Cache dentro do TTL tem
 * `origem === 'cache'` com `aviso === null` — é dado válido, não degradação,
 * e não deve gerar banner.
 */
function BannerDegradacao({ data }: { data: EntregasResponse }) {
  if (data.aviso === null) return null;
  const quando =
    data.buscado_em !== null
      ? new Date(data.buscado_em).toLocaleString('pt-BR')
      : null;
  return (
    <p className="samid-pill samid-pill-alerta" role="status" style={{ height: 'auto', padding: '8px 14px' }}>
      {data.aviso}
      {quando !== null && ` Últimos dados obtidos em ${quando}.`}
    </p>
  );
}

/** Idade do dado, mostrada sempre que houver carimbo — inclusive no caminho
 * feliz. É o que impede dado de algumas horas de se passar por instantâneo,
 * sem precisar de banner de alerta para isso. */
function idadeDoDado(buscadoEm: string | null): string | null {
  if (buscadoEm === null) return null;
  const horas = Math.floor((Date.now() - new Date(buscadoEm).getTime()) / 3_600_000);
  if (horas < 1) return 'atualizado agora';
  return `atualizado há ${horas}h`;
}

function isPrefeitura(instituicao: string): boolean {
  return instituicao.toLowerCase().includes('prefeitura');
}

function agruparPorInstituicao(entregas: Entrega[]): { instituicao: string; itens: Entrega[] }[] {
  const grupos = new Map<string, Entrega[]>();
  for (const e of entregas) {
    const lista = grupos.get(e.instituicao) ?? [];
    lista.push(e);
    grupos.set(e.instituicao, lista);
  }
  return Array.from(grupos.entries())
    .map(([instituicao, itens]) => ({ instituicao, itens }))
    .sort((a, b) => {
      if (isPrefeitura(a.instituicao) === isPrefeitura(b.instituicao)) {
        return a.instituicao.localeCompare(b.instituicao);
      }
      return isPrefeitura(a.instituicao) ? -1 : 1;
    });
}

function TabelaEntregas({ itens }: { itens: Entrega[] }) {
  return (
    <table className="samid-table samid-table-dense">
      <thead>
        <tr>
          <th>Entregável</th>
          <th>Período</th>
          <th>Status</th>
          <th>Data</th>
          <th>Dias após o fim do período</th>
        </tr>
      </thead>
      <tbody>
        {itens.map((e, i) => (
          <tr key={`${e.entregavel}-${e.periodo}-${i}`}>
            <td>{e.entregavel}</td>
            <td className="mono">{e.periodo}</td>
            <td>{e.status}</td>
            <td className="mono">{e.data_status ? formatarData(e.data_status) : '—'}</td>
            <td className="mono">{situacaoPrazo(e)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function Entregas() {
  const [ano, setAno] = useState(ANO_ATUAL);
  const [data, setData] = useState<EntregasResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setError(null);
    api
      .getEntregas(ano)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          // Descartar o resultado anterior. Sem isto, uma falha ao trocar de
          // exercício deixaria o seletor no ano novo e a tabela/resumo no ano
          // antigo — contagens de retificação de 2025 apresentadas como se
          // fossem de 2026.
          setData(null);
          setError(err instanceof ApiError ? err.userMessage : 'Erro ao carregar entregas.');
        }
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ano]);

  const idade = data ? idadeDoDado(data.buscado_em) : null;
  const comPrazoAcompanhado = data
    ? data.entregas.filter((e) => e.prazo_dias !== null && e.fim_periodo !== null)
    : [];
  const grupos = data ? agruparPorInstituicao(data.entregas) : [];

  return (
    <div className="samid-stack">
      <section className="samid-card">
        <div className="samid-card-head">
          <div>
            <div className="samid-eyebrow">Gestão da Informação</div>
            <h2 className="samid-card-title">
              {busy ? 'Carregando...' : 'Entregas ao Siconfi'}
            </h2>
          </div>
          <div className="samid-competencia">
            <div className="samid-competencia-lbl">EXERCÍCIO</div>
            <select
              className="samid-select samid-competencia-select"
              aria-label="Trocar exercício"
              value={ano}
              onChange={(e) => setAno(Number(e.target.value))}
            >
              {ANOS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && (
          <p className="samid-pill samid-pill-erro" role="alert">
            {error}
          </p>
        )}

        {data && <BannerDegradacao data={data} />}

        {idade !== null && (
          <p className="samid-muted" style={{ fontSize: 12, margin: '8px 0 0' }}>
            {idade}
          </p>
        )}

        {data && data.origem !== 'indisponivel' && (
          <div style={{ display: 'flex', gap: 24, marginTop: 16 }}>
            <div>
              <div className="samid-eyebrow">Total</div>
              <div
                className="mono"
                data-testid="resumo-total"
                style={{ fontSize: 22, fontWeight: 700 }}
              >
                {data.resumo.total}
              </div>
            </div>
            <div>
              <div className="samid-eyebrow">Homologadas</div>
              <div
                className="mono"
                data-testid="resumo-homologadas"
                style={{ fontSize: 22, fontWeight: 700 }}
              >
                {data.resumo.homologadas}
              </div>
            </div>
            <div>
              <div className="samid-eyebrow">Retificadas</div>
              <div
                className="mono"
                data-testid="resumo-retificadas"
                style={{ fontSize: 22, fontWeight: 700, color: 'var(--samid-alerta)' }}
              >
                {data.resumo.retificadas}
              </div>
            </div>
          </div>
        )}
      </section>

      {data && data.origem === 'indisponivel' ? null : data ? (
        <>
          <section className="samid-card">
            <div className="samid-eyebrow">Entregas com prazo acompanhado</div>
            {comPrazoAcompanhado.length === 0 ? (
              <p className="samid-muted">nenhuma entrega com prazo configurado neste exercício</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <TabelaEntregas itens={comPrazoAcompanhado} />
              </div>
            )}
          </section>

          <section className="samid-card">
            <div className="samid-eyebrow">Como estamos</div>
            {grupos.map((g) => (
              <details key={g.instituicao} open={isPrefeitura(g.instituicao)} style={{ marginTop: 12 }}>
                <summary className="samid-card-title" style={{ fontSize: 16, cursor: 'pointer' }}>
                  {g.instituicao} ({g.itens.length})
                </summary>
                <div style={{ overflowX: 'auto', marginTop: 8 }}>
                  <TabelaEntregas itens={g.itens} />
                </div>
              </details>
            ))}

            <p className="samid-muted" style={{ fontSize: 12, marginTop: 16 }}>
              Prazos conforme configuração — confirmar com a contabilidade.
            </p>
          </section>
        </>
      ) : null}
    </div>
  );
}
