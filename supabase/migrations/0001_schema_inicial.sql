-- =============================================================================
-- 0001 · Schema inicial do Painel Pessoal
--
-- Modelo relacional:
--
--   categorias 1──N feeds N──1 fontes
--        │                      │
--        └──────1──N noticias N─┘
--                       │
--   coletas 1───────────N (coleta_id)
--
--   indicadores 1──N indicador_valores
--
-- Segurança: RLS ligado em todas as tabelas. O papel `anon` (chave publishable,
-- usada pelo site) recebe APENAS SELECT nas tabelas de leitura pública. A escrita
-- é feita exclusivamente pelo pipeline, que conecta como `postgres` via secret.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Domínio
-- -----------------------------------------------------------------------------
create table if not exists public.categorias (
    slug   text     primary key check (slug ~ '^[a-z][a-z_]*$'),
    nome   text     not null,
    ordem  smallint not null default 0
);

comment on table public.categorias is 'Editorias usadas para agrupar as notícias no painel.';

create table if not exists public.fontes (
    id         smallint    generated always as identity primary key,
    slug       text        not null unique check (slug ~ '^[a-z0-9][a-z0-9_-]*$'),
    nome       text        not null,
    site_url   text        not null check (site_url ~ '^https?://'),
    ativa      boolean     not null default true,
    criado_em  timestamptz not null default now()
);

comment on table public.fontes is 'Veículos de imprensa monitorados.';

create table if not exists public.feeds (
    id              integer     generated always as identity primary key,
    fonte_id        smallint    not null references public.fontes (id) on delete cascade,
    categoria_slug  text        not null references public.categorias (slug),
    url             text        not null unique check (url ~ '^https?://'),
    ativo           boolean     not null default true,
    criado_em       timestamptz not null default now()
);

create index if not exists feeds_fonte_id_idx on public.feeds (fonte_id);

comment on table public.feeds is 'Feeds RSS/Atom de cada fonte, cada um ligado a uma categoria.';

-- -----------------------------------------------------------------------------
-- Execuções do pipeline (auditoria / observabilidade)
-- -----------------------------------------------------------------------------
create table if not exists public.coletas (
    id               bigint      generated always as identity primary key,
    data_referencia  date        not null,
    iniciada_em      timestamptz not null default now(),
    finalizada_em    timestamptz,
    status           text        not null default 'em_andamento'
                                 check (status in ('em_andamento', 'sucesso', 'parcial', 'falha')),
    feeds_ok         integer     not null default 0,
    feeds_falha      integer     not null default 0,
    noticias_lidas   integer     not null default 0,
    noticias_novas   integer     not null default 0,
    erros            jsonb       not null default '[]'::jsonb
);

create index if not exists coletas_data_referencia_idx on public.coletas (data_referencia desc);

comment on table public.coletas is 'Uma linha por execução do pipeline diário.';

-- -----------------------------------------------------------------------------
-- Notícias
-- -----------------------------------------------------------------------------
create table if not exists public.noticias (
    id               bigint      generated always as identity primary key,
    fonte_id         smallint    not null references public.fontes (id),
    categoria_slug   text        not null references public.categorias (slug),
    coleta_id        bigint      references public.coletas (id) on delete set null,
    titulo           text        not null check (char_length(titulo) between 1 and 500),
    resumo           text        check (resumo is null or char_length(resumo) <= 1000),
    url              text        not null unique check (url ~ '^https?://'),
    imagem_url       text        check (imagem_url is null or imagem_url ~ '^https?://'),
    publicado_em     timestamptz,
    data_referencia  date        not null,
    -- Identificador do agrupamento de manchetes equivalentes entre fontes.
    grupo            text        not null,
    -- Nº de fontes distintas que noticiaram o mesmo fato (proxy de importância).
    relevancia       smallint    not null default 1 check (relevancia >= 1),
    criado_em        timestamptz not null default now(),
    atualizado_em    timestamptz not null default now()
);

create index if not exists noticias_dia_relevancia_idx
    on public.noticias (data_referencia desc, relevancia desc, publicado_em desc);
create index if not exists noticias_grupo_idx on public.noticias (grupo);
create index if not exists noticias_fonte_id_idx on public.noticias (fonte_id);
create index if not exists noticias_categoria_idx on public.noticias (categoria_slug);
create index if not exists noticias_coleta_id_idx on public.noticias (coleta_id);

comment on table public.noticias is 'Manchetes coletadas diariamente. URL é a chave natural (deduplicação).';

-- -----------------------------------------------------------------------------
-- Indicadores econômicos (Banco Central – SGS)
-- -----------------------------------------------------------------------------
create table if not exists public.indicadores (
    codigo     text     primary key check (codigo ~ '^[a-z][a-z0-9_]*$'),
    nome       text     not null,
    unidade    text     not null,
    serie_sgs  integer  not null unique,
    ordem      smallint not null default 0
);

create table if not exists public.indicador_valores (
    indicador_codigo  text          not null references public.indicadores (codigo) on delete cascade,
    data              date          not null,
    valor             numeric(16,6) not null,
    coletado_em       timestamptz   not null default now(),
    primary key (indicador_codigo, data)
);

create index if not exists indicador_valores_data_idx on public.indicador_valores (data desc);

-- -----------------------------------------------------------------------------
-- Dados de referência
-- -----------------------------------------------------------------------------
insert into public.categorias (slug, nome, ordem) values
    ('geral',              'Brasil',               1),
    ('economia',           'Economia',             2),
    ('politica',           'Governo e leis',       3),
    ('saude',              'Saúde',                4),
    ('educacao',           'Educação',             5),
    ('ciencia_tecnologia', 'Ciência e tecnologia', 6),
    ('mundo',              'Mundo',                7)
on conflict (slug) do update set nome = excluded.nome, ordem = excluded.ordem;

insert into public.indicadores (codigo, nome, unidade, serie_sgs, ordem) values
    ('dolar_ptax', 'Dólar (PTAX venda)', 'R$',      1,     1),
    ('euro_ptax',  'Euro (PTAX venda)',  'R$',      21619, 2),
    ('selic_meta', 'Selic (meta)',       '% a.a.',  432,   3),
    ('ipca_12m',   'IPCA 12 meses',      '%',       13522, 4)
on conflict (codigo) do update
    set nome = excluded.nome, unidade = excluded.unidade,
        serie_sgs = excluded.serie_sgs, ordem = excluded.ordem;

-- -----------------------------------------------------------------------------
-- Segurança: Row Level Security + privilégios mínimos
-- -----------------------------------------------------------------------------
alter table public.categorias        enable row level security;
alter table public.fontes            enable row level security;
alter table public.feeds             enable row level security;
alter table public.coletas           enable row level security;
alter table public.noticias          enable row level security;
alter table public.indicadores       enable row level security;
alter table public.indicador_valores enable row level security;

-- Remove qualquer privilégio padrão concedido pelo Supabase e concede só leitura.
revoke all on public.categorias, public.fontes, public.feeds, public.coletas,
              public.noticias, public.indicadores, public.indicador_valores
    from anon, authenticated;

grant select on public.categorias, public.fontes, public.coletas,
                public.noticias, public.indicadores, public.indicador_valores
    to anon, authenticated;
-- `feeds` fica sem grant/policy: detalhe interno, não exposto pela API.

do $$
declare
    t text;
begin
    foreach t in array array['categorias', 'fontes', 'coletas', 'noticias',
                             'indicadores', 'indicador_valores']
    loop
        execute format('drop policy if exists leitura_publica on public.%I', t);
        execute format(
            'create policy leitura_publica on public.%I for select to anon, authenticated using (true)',
            t
        );
    end loop;
end
$$;
