"""Regras de exclusão: opinião, publicidade e entretenimento."""

from __future__ import annotations

from pipeline.modelos import Filtros, Noticia
from pipeline.texto import contem_expressao, normalizar


def motivo_exclusao(noticia: Noticia, filtros: Filtros) -> str | None:
    """Retorna o motivo da exclusão, ou None se a notícia deve ser mantida."""
    url = noticia.url.lower()
    for trecho in filtros.url_excluir:
        if trecho in url:
            return f"url contém '{trecho}'"

    titulo = normalizar(noticia.titulo)
    for termo in filtros.titulo_excluir:
        if contem_expressao(titulo, termo):
            return f"título contém '{termo}'"
    return None
