"""Utilitários de normalização de texto e URL."""

from __future__ import annotations

import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TAGS = re.compile(r"<[^>]+>")
_ESPACOS = re.compile(r"\s+")
_NAO_ALFANUM = re.compile(r"[^a-z0-9]+")

# Parâmetros de rastreamento removidos para que a mesma matéria tenha uma única URL.
_PARAMS_RASTREIO = re.compile(r"^(utm_|fbclid$|gclid$|mc_|ref$|origin$|cmpid$|xtor$|at_)")

STOPWORDS = frozenset(
    """
    a o as os um uma uns umas de do da dos das em no na nos nas por pelo pela pelos pelas
    para pra com sem sob sobre entre ate apos ante e ou mas que se ser sao foi era sera
    tem ter ha nao sim mais menos muito muita ja ainda tambem como quando onde qual quais
    quem seu sua seus suas ele ela eles elas isso isto esse essa este esta aquele aquela
    diz dizem afirma apos contra ao aos vai vao pode podem deve devem apos novo nova
    brasil brasileiro brasileira veja entenda saiba
    """.split()
)


def limpar_html(texto: str | None, limite: int | None = None) -> str | None:
    """Remove tags HTML, decodifica entidades e compacta espaços."""
    if not texto:
        return None
    limpo = _ESPACOS.sub(" ", html.unescape(_TAGS.sub(" ", texto))).strip()
    if not limpo:
        return None
    if limite and len(limpo) > limite:
        corte = limpo[: limite - 1].rsplit(" ", 1)[0]
        limpo = f"{corte}…"
    return limpo


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos, apenas [a-z0-9] separados por espaço simples."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return _NAO_ALFANUM.sub(" ", sem_acento.lower()).strip()


def tokens(texto: str) -> frozenset[str]:
    """Palavras significativas (>= 3 caracteres, fora da lista de stopwords)."""
    return frozenset(t for t in normalizar(texto).split() if len(t) >= 3 and t not in STOPWORDS)


def contem_expressao(texto_normalizado: str, expressao_normalizada: str) -> bool:
    """Verifica se a expressão aparece como palavra(s) inteira(s)."""
    return f" {expressao_normalizada} " in f" {texto_normalizado} "


def normalizar_url(url: str) -> str | None:
    """Canoniza a URL: só http(s), sem fragmento e sem parâmetros de rastreamento."""
    url = (url or "").strip()
    try:
        partes = urlsplit(url)
    except ValueError:
        return None
    if partes.scheme not in ("http", "https") or not partes.netloc:
        return None
    query = urlencode(
        [
            (k, v)
            for k, v in parse_qsl(partes.query, keep_blank_values=True)
            if not _PARAMS_RASTREIO.match(k.lower())
        ]
    )
    return urlunsplit(
        (
            "https" if partes.scheme == "https" else "http",
            partes.netloc.lower(),
            partes.path or "/",
            query,
            "",
        )
    )
