"""Persistência no PostgreSQL do Supabase."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from pipeline.modelos import Fonte, Noticia, ValorIndicador

log = logging.getLogger(__name__)

DIR_MIGRACOES = Path(__file__).resolve().parent.parent / "supabase" / "migrations"


def conectar(dsn: str) -> psycopg.Connection:
    # prepare_threshold=None: obrigatório no pooler em modo transação (porta 6543),
    # que não suporta prepared statements.
    return psycopg.connect(
        dsn,
        prepare_threshold=None,
        connect_timeout=15,
        sslmode="require",
        application_name="painel-pessoal-pipeline",
    )


def aplicar_migracoes(conn: psycopg.Connection, diretorio: Path = DIR_MIGRACOES) -> list[str]:
    """Aplica, em ordem e numa única transação, os arquivos .sql ainda não aplicados."""
    arquivos = sorted(diretorio.glob("*.sql"))
    aplicadas: list[str] = []
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("select pg_advisory_xact_lock(hashtext('painel_pessoal_migracoes'))")
        cur.execute("create schema if not exists pipeline")
        cur.execute("revoke all on schema pipeline from public")
        cur.execute(
            """
            create table if not exists pipeline.migracoes (
                nome        text primary key,
                aplicada_em timestamptz not null default now()
            )
            """
        )
        cur.execute("select nome from pipeline.migracoes")
        ja_aplicadas = {r[0] for r in cur.fetchall()}
        for arquivo in arquivos:
            if arquivo.name in ja_aplicadas:
                continue
            log.info("aplicando migração %s", arquivo.name)
            cur.execute(arquivo.read_text(encoding="utf-8"))
            cur.execute("insert into pipeline.migracoes (nome) values (%s)", (arquivo.name,))
            aplicadas.append(arquivo.name)
    return aplicadas


def sincronizar_fontes(conn: psycopg.Connection, fontes: Sequence[Fonte]) -> dict[str, int]:
    """Espelha fontes.toml nas tabelas fontes/feeds. Retorna slug -> id."""
    with conn.transaction(), conn.cursor() as cur:
        ids: dict[str, int] = {}
        for f in fontes:
            cur.execute(
                """
                insert into public.fontes (slug, nome, site_url, ativa)
                values (%s, %s, %s, true)
                on conflict (slug) do update
                    set nome = excluded.nome, site_url = excluded.site_url, ativa = true
                returning id
                """,
                (f.slug, f.nome, f.site_url),
            )
            ids[f.slug] = cur.fetchone()[0]
            for feed in f.feeds:
                cur.execute(
                    """
                    insert into public.feeds (fonte_id, categoria_slug, url, ativo)
                    values (%s, %s, %s, true)
                    on conflict (url) do update
                        set fonte_id = excluded.fonte_id,
                            categoria_slug = excluded.categoria_slug,
                            ativo = true
                    """,
                    (ids[f.slug], feed.categoria, feed.url),
                )
        cur.execute(
            "update public.fontes set ativa = false where not (slug = any(%s))",
            (list(ids),),
        )
        cur.execute(
            "update public.feeds set ativo = false where not (url = any(%s))",
            ([feed.url for f in fontes for feed in f.feeds],),
        )
    return ids


def iniciar_coleta(conn: psycopg.Connection, data_ref: date) -> int:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "insert into public.coletas (data_referencia) values (%s) returning id", (data_ref,)
        )
        return cur.fetchone()[0]


def gravar_noticias(
    conn: psycopg.Connection,
    noticias: Sequence[Noticia],
    fonte_ids: dict[str, int],
    coleta_id: int,
    data_ref: date,
) -> int:
    """Upsert idempotente. Retorna quantas notícias são novas nesta coleta.

    URL já existente de outro dia não é alterada (a notícia pertence ao dia em que
    apareceu pela 1ª vez). Reexecuções no mesmo dia atualizam grupo/relevância.
    """
    linhas = [
        (
            fonte_ids[n.fonte_slug],
            n.categoria,
            coleta_id,
            n.titulo,
            n.resumo,
            n.url,
            n.imagem_url,
            n.publicado_em,
            data_ref,
            n.grupo,
            n.relevancia,
        )
        for n in noticias
    ]
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            """
            insert into public.noticias
                (fonte_id, categoria_slug, coleta_id, titulo, resumo, url, imagem_url,
                 publicado_em, data_referencia, grupo, relevancia)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (url) do update
                set grupo = excluded.grupo,
                    relevancia = excluded.relevancia,
                    titulo = excluded.titulo,
                    atualizado_em = now()
                where noticias.data_referencia = excluded.data_referencia
            """,
            linhas,
        )
        cur.execute("select count(*) from public.noticias where coleta_id = %s", (coleta_id,))
        return cur.fetchone()[0]


def gravar_indicadores(conn: psycopg.Connection, valores: Sequence[ValorIndicador]) -> None:
    if not valores:
        return
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            """
            insert into public.indicador_valores (indicador_codigo, data, valor)
            values (%s, %s, %s)
            on conflict (indicador_codigo, data) do update
                set valor = excluded.valor, coletado_em = now()
            """,
            [(v.codigo, v.data, v.valor) for v in valores],
        )


def remover_antigas(conn: psycopg.Connection, data_ref: date, dias: int) -> int:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "delete from public.noticias where data_referencia < %s::date - %s::int",
            (data_ref, dias),
        )
        return cur.rowcount


def finalizar_coleta(
    conn: psycopg.Connection,
    coleta_id: int,
    *,
    status: str,
    feeds_ok: int,
    feeds_falha: int,
    lidas: int,
    novas: int,
    erros: list[str],
) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """
            update public.coletas
               set finalizada_em = now(), status = %s, feeds_ok = %s, feeds_falha = %s,
                   noticias_lidas = %s, noticias_novas = %s, erros = %s
             where id = %s
            """,
            (status, feeds_ok, feeds_falha, lidas, novas, Jsonb(erros), coleta_id),
        )
