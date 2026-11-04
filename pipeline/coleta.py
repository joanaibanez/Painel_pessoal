"""Download e parsing dos feeds RSS/Atom."""

from __future__ import annotations

import calendar
import logging
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import feedparser
import httpx

from pipeline import __version__
from pipeline.modelos import Feed, Noticia, ResultadoFeed
from pipeline.texto import limpar_html, normalizar_url

log = logging.getLogger(__name__)

USER_AGENT = (
    f"PainelPessoalBot/{__version__} "
    "(+https://github.com/joanaibanez/Painel_pessoal; leitor de RSS, 1 acesso/dia)"
)
MAX_ITENS_POR_FEED = 25
TENTATIVAS = 3
STATUS_REPETIVEIS = {429, 500, 502, 503, 504}


class ErroFeed(RuntimeError):
    """Falha ao obter ou interpretar um feed."""


def criar_cliente() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(20.0, connect=10.0),
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.5",
        },
    )


def baixar(cliente: httpx.Client, url: str) -> bytes:
    """GET com retry e backoff exponencial para erros transitórios."""
    ultimo_erro: Exception | None = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = cliente.get(url)
            if resposta.status_code in STATUS_REPETIVEIS:
                raise httpx.HTTPStatusError(
                    f"HTTP {resposta.status_code}", request=resposta.request, response=resposta
                )
            resposta.raise_for_status()
            return resposta.content
        except httpx.HTTPStatusError as exc:
            ultimo_erro = exc
            if exc.response.status_code not in STATUS_REPETIVEIS:
                break
        except httpx.TransportError as exc:
            ultimo_erro = exc
        if tentativa < TENTATIVAS:
            time.sleep(2**tentativa)
    raise ErroFeed(f"{type(ultimo_erro).__name__}: {ultimo_erro}")


def _data(entry: feedparser.FeedParserDict) -> datetime | None:
    for campo in ("published_parsed", "updated_parsed"):
        valor = entry.get(campo)
        if valor:
            return datetime.fromtimestamp(calendar.timegm(valor), tz=UTC)
    return None


def _imagem(entry: feedparser.FeedParserDict) -> str | None:
    candidatos: list[str] = []
    for chave in ("media_content", "media_thumbnail"):
        candidatos += [m.get("url", "") for m in entry.get(chave, []) or []]
    candidatos += [
        e.get("href", "")
        for e in entry.get("enclosures", []) or []
        if str(e.get("type", "")).startswith("image/")
    ]
    for c in candidatos:
        url = normalizar_url(c)
        if url:
            return url
    return None


def interpretar(conteudo: bytes, feed: Feed) -> list[Noticia]:
    """Converte o XML do feed em objetos Noticia (sem filtragem editorial)."""
    analisado = feedparser.parse(conteudo)
    if analisado.bozo and not analisado.entries:
        raise ErroFeed(f"XML inválido: {analisado.get('bozo_exception')}")

    noticias: list[Noticia] = []
    for entry in analisado.entries[:MAX_ITENS_POR_FEED]:
        titulo = limpar_html(entry.get("title"), limite=500)
        url = normalizar_url(entry.get("link", ""))
        if not titulo or not url:
            continue
        noticias.append(
            Noticia(
                fonte_slug=feed.fonte_slug,
                categoria=feed.categoria,
                titulo=titulo,
                url=url,
                resumo=limpar_html(entry.get("summary"), limite=300),
                imagem_url=_imagem(entry),
                publicado_em=_data(entry),
            )
        )
    return noticias


def coletar_feed(cliente: httpx.Client, feed: Feed) -> ResultadoFeed:
    try:
        noticias = interpretar(baixar(cliente, feed.url), feed)
        log.info(
            "ok   %-16s %-19s %3d itens  %s",
            feed.fonte_slug,
            feed.categoria,
            len(noticias),
            feed.url,
        )
        return ResultadoFeed(feed=feed, noticias=noticias)
    except Exception as exc:  # um feed com problema não derruba a coleta
        log.warning("erro %-16s %-19s %s  %s", feed.fonte_slug, feed.categoria, exc, feed.url)
        return ResultadoFeed(feed=feed, erro=str(exc)[:500])


def coletar_todos(feeds: Iterable[Feed], max_workers: int = 8) -> list[ResultadoFeed]:
    feeds = list(feeds)
    with criar_cliente() as cliente, ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(lambda f: coletar_feed(cliente, f), feeds))


def dentro_da_janela(noticia: Noticia, agora: datetime, horas: int) -> bool:
    """Mantém notícias recentes. Itens sem data são aceitos (o feed já é 'últimas')."""
    if noticia.publicado_em is None:
        return True
    return agora - timedelta(hours=horas) <= noticia.publicado_em <= agora + timedelta(hours=2)


def deduplicar(noticias: Iterable[Noticia]) -> list[Noticia]:
    """Uma notícia por URL; prefere a categoria mais específica que 'geral'."""
    por_url: dict[str, Noticia] = {}
    for n in noticias:
        atual = por_url.get(n.url)
        if atual is None:
            por_url[n.url] = n
        elif atual.categoria == "geral" and n.categoria != "geral":
            atual.categoria = n.categoria
    return list(por_url.values())
