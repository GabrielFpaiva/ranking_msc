-- F7-05: schema inicial do MCRA web (Supabase Postgres).
--
-- Sem schema qualificado de propósito: as tabelas caem no primeiro schema do
-- search_path (public em produção, um schema descartável nos testes).
--
-- RLS ligado sem nenhuma policy em todas as tabelas: o Supabase expõe o schema
-- public pela API REST com a chave anon. Sem policy, ninguém de fora lê nada; a
-- API do MCRA conecta como dono das tabelas e não é afetada.

-- Usuários (F7-07 migra os do settings.yaml para cá).
create table usuarios (
    username        text primary key,
    hashed_password text not null,
    criado_em       timestamptz not null default now()
);

-- Uma matriz por ente × competência × origem. Substituir a prévia = apagar e
-- inserir de novo (o cascade leva linhas, execuções e pendências junto).
create table matrizes (
    id              bigint generated always as identity primary key,
    siconfi         text not null,
    competencia     text not null check (competencia ~ '^\d{4}-(0[1-9]|1[0-3])$'),
    origem          text not null check (origem in ('previa', 'homologada')),
    arquivo_storage text,           -- caminho do CSV original no Storage (só prévia)
    enviado_por     text,           -- null na homologada (vem da API do SICONFI)
    enviado_em      timestamptz not null default now(),
    unique (siconfi, competencia, origem)
);

-- Linhas da matriz já normalizadas: mesmas colunas do snapshot msc_normalizado
-- (FACT_MSC_COLUMNS + ic1..ic6/tipo1..tipo6, cuja ordem as regras de leiaute leem).
-- Valores em double precision para a volta ao DataFrame ser bit a bit igual ao float64.
create table matriz_linhas (
    matriz_id             bigint not null references matrizes (id) on delete cascade,
    linha                 integer not null,
    conta_contabil        text not null,
    ic1 text, tipo1 text, ic2 text, tipo2 text, ic3 text, tipo3 text,
    ic4 text, tipo4 text, ic5 text, tipo5 text, ic6 text, tipo6 text,
    po text, fp text, dc text, fs text, fr text, co text, nr text, nd text, ai text,
    saldo_inicial_debito  double precision not null default 0,
    saldo_inicial_credito double precision not null default 0,
    movimento_debito      double precision not null default 0,
    movimento_credito     double precision not null default 0,
    saldo_final_debito    double precision not null default 0,
    saldo_final_credito   double precision not null default 0,
    has_saldo_inicial     boolean not null,
    has_saldo_final       boolean not null,
    has_period_change     boolean not null,
    primary key (matriz_id, linha)
);
create index matriz_linhas_conta_idx on matriz_linhas (matriz_id, conta_contabil);

-- Uma execução do motor sobre uma matriz. regras_executadas substitui o
-- scoring_metadata.json (estabilidade histórica do score).
create table execucoes (
    id                uuid primary key,
    matriz_id         bigint not null references matrizes (id) on delete cascade,
    usuario           text not null,
    inicio            timestamptz not null,
    fim               timestamptz,
    status            text not null check (status in ('OK', 'ERRO', 'PARCIAL')),
    erro_msg          text,
    regras_executadas text[] not null default '{}'
);
create index execucoes_matriz_idx on execucoes (matriz_id, inicio desc);

-- Resultado das regras: FACT_RESULTADO_REGRAS_COLUMNS de uma execução.
create table pendencias (
    execucao_id      uuid not null references execucoes (id) on delete cascade,
    regra_id         text not null,
    regra_nome       text not null,
    dimensao         text not null,
    severidade       text not null,
    conta_contabil   text not null default '',
    descricao        text not null,
    valor_esperado   text,
    valor_encontrado text,
    competencia      text not null
);
create index pendencias_execucao_idx on pendencias (execucao_id);
create index pendencias_regra_conta_idx on pendencias (regra_id, conta_contabil);

-- Pendência dispensada para sempre, por regra + conta ('' = regra global).
-- Desfazer = apagar a linha.
create table dispensadas (
    regra_id       text not null,
    conta_contabil text not null default '',
    motivo         text not null check (btrim(motivo) <> ''),
    usuario        text not null,
    dispensada_em  timestamptz not null default now(),
    primary key (regra_id, conta_contabil)
);

-- Registro de envio, substituição, exclusão e busca de matriz. Sem FK: o
-- registro sobrevive à matriz apagada.
create table registros_envio (
    id          bigint generated always as identity primary key,
    siconfi     text not null,
    competencia text not null,
    origem      text not null check (origem in ('previa', 'homologada')),
    acao        text not null check (acao in ('envio', 'substituicao', 'exclusao', 'busca')),
    usuario     text,
    em          timestamptz not null default now(),
    detalhe     text
);
create index registros_envio_comp_idx on registros_envio (siconfi, competencia, em desc);

-- Histórico do nosso score por mês. Sem FK: sobrevive à prévia substituída ou apagada.
create table historico_score (
    id           bigint generated always as identity primary key,
    siconfi      text not null,
    competencia  text not null,
    origem       text not null check (origem in ('previa', 'homologada')),
    execucao_id  uuid not null,
    pontuacao    double precision not null,
    banda        text not null,
    dimensoes    jsonb not null default '{}',
    calculado_em timestamptz not null default now()
);
create index historico_score_comp_idx
    on historico_score (siconfi, competencia, origem, calculado_em desc);

-- Tempo de uso por usuário/dia/rota (hoje em data/uso/<AAAA-MM>.jsonl).
create table uso (
    usuario  text not null,
    dia      date not null,
    rota     text not null,
    aberto_s integer not null default 0 check (aberto_s >= 0),
    ativo_s  integer not null default 0 check (ativo_s >= 0),
    primary key (usuario, dia, rota)
);

alter table usuarios        enable row level security;
alter table matrizes        enable row level security;
alter table matriz_linhas   enable row level security;
alter table execucoes       enable row level security;
alter table pendencias      enable row level security;
alter table dispensadas     enable row level security;
alter table registros_envio enable row level security;
alter table historico_score enable row level security;
alter table uso             enable row level security;
