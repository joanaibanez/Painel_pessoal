"""Ponto de entrada: `python -m pipeline [--dry-run]`."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline import coleta, config, db, indicadores
from pipeline.filtros import motivo_exclusao
from pipeline.modelos import Noticia
from pipeline.relevancia import agrupar

FUSO = ZoneInfo("America/Sao_Paulo")
log = logging.getLogger("pipeline")


def _int_env(nome: str, padrao: int) -> int:
    valor = os.environ.get(nome, "").strip()
    return int(valor) if valor else padrao


def _resumo_markdown(
    data_ref: str,
    status: str,
    resultados: list,
    noticias: list[Noticia],
    excluidas: Counter,
    novas: int | None,
    erros: list[str],
) -> str:
    ok = sum(1 for r in resultados if r.erro is None)
    linhas = [
        f"## Coleta de {data_ref} — **{status}**",
        "",
        f"- Feeds: {ok} ok / {len(resultados) - ok} com falha",
        f"- Notícias mantidas: {len(noticias)}"
        + (f" (novas no banco: {novas})" if novas is not None else ""),
        f"- Excluídas pelos filtros: {sum(excluidas.values())}",
        "",
        "| Fonte | Categoria | Itens | Erro |",
        "|---|---|---:|---|",
    ]
    for r in resultados:
        erro = (r.erro or "").replace("|", "/")[:120]
        linhas.append(f"| {r.feed.fonte_slug} | {r.feed.categoria} | {len(r.noticias)} | {erro} |")

    destaques: dict[str, Noticia] = {}
    for n in sorted(noticias, key=lambda x: -x.relevancia):
        if n.relevancia >= 2:
            destaques.setdefault(n.grupo, n)
    if destaques:
        linhas += ["", "### Destaques (cobertos por 2+ fontes)", ""]
        linhas += [f"- ({n.relevancia}) {n.titulo}" for n in list(destaques.values())[:15]]
    if erros:
        linhas += ["", "### Erros", ""] + [f"- {e}" for e in erros[:30]]
    return "\n".join(linhas) + "\n"


def executar(dry_run: bool) -> int:
    agora = datetime.now(UTC)
    data_ref = agora.astimezone(FUSO).date()
    janela_horas = _int_env("JANELA_HORAS", 30)
    retencao_dias = _int_env("RETENCAO_DIAS", 180)

    fontes, filtros = config.carregar()
    feeds = [f for fonte in fontes for f in fonte.feeds]
    log.info("data de referência %s · %d fontes · %d feeds", data_ref, len(fontes), len(feeds))

    resultados = coleta.coletar_todos(feeds)
    erros = [f"feed {r.feed.url}: {r.erro}" for r in resultados if r.erro]

    excluidas: Counter[str] = Counter()
    candidatas: list[Noticia] = []
    for r in resultados:
        for n in r.noticias:
            if not coleta.dentro_da_janela(n, agora, janela_horas):
                excluidas["fora da janela"] += 1
            elif motivo := motivo_exclusao(n, filtros):
                excluidas[motivo] += 1
            else:
                candidatas.append(n)

    noticias = coleta.deduplicar(candidatas)
    agrupar(noticias)
    lidas = sum(len(r.noticias) for r in resultados)
    log.info("lidas %d · mantidas %d · excluídas %s", lidas, len(noticias), dict(excluidas))

    valores, erros_ind = indicadores.coletar()
    erros += erros_ind

    feeds_ok = sum(1 for r in resultados if r.erro is None)
    status = "falha" if feeds_ok == 0 else ("sucesso" if not erros else "parcial")

    novas: int | None = None
    if dry_run:
        log.info("dry-run: nada foi gravado no banco")
    else:
        dsn = os.environ.get("SUPABASE_DB_URL", "").strip()
        if not dsn:
            log.error("variável SUPABASE_DB_URL ausente (configure o secret no GitHub)")
            return 2
        with db.conectar(dsn) as conn:
            aplicadas = db.aplicar_migracoes(conn)
            if aplicadas:
                log.info("migrações aplicadas: %s", aplicadas)
            fonte_ids = db.sincronizar_fontes(conn, fontes)
            coleta_id = db.iniciar_coleta(conn, data_ref)
            try:
                novas = db.gravar_noticias(conn, noticias, fonte_ids, coleta_id, data_ref)
                db.gravar_indicadores(conn, valores)
                removidas = db.remover_antigas(conn, data_ref, retencao_dias)
                log.info("novas %d · removidas por retenção %d", novas, removidas)
            except Exception as exc:
                conn.rollback()
                db.finalizar_coleta(
                    conn,
                    coleta_id,
                    status="falha",
                    feeds_ok=feeds_ok,
                    feeds_falha=len(resultados) - feeds_ok,
                    lidas=lidas,
                    novas=0,
                    erros=[*erros, f"banco: {exc}"[:500]],
                )
                raise
            db.finalizar_coleta(
                conn,
                coleta_id,
                status=status,
                feeds_ok=feeds_ok,
                feeds_falha=len(resultados) - feeds_ok,
                lidas=lidas,
                novas=novas,
                erros=erros,
            )

    if resumo := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(resumo).open("a", encoding="utf-8") as fp:
            fp.write(
                _resumo_markdown(
                    str(data_ref), status, resultados, noticias, excluidas, novas, erros
                )
            )
    if os.environ.get("GITHUB_ACTIONS"):
        for e in erros:
            print(f"::warning title=Coleta::{e}")

    log.info("status final: %s", status)
    return 1 if status == "falha" else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline", description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="coleta e processa, mas não grava no banco"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    )
    return executar(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
