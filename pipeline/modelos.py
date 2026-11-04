"""Estruturas de dados do pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

CATEGORIAS_VALIDAS = frozenset(
    {"geral", "economia", "politica", "saude", "educacao", "ciencia_tecnologia", "mundo"}
)


@dataclass(frozen=True, slots=True)
class Feed:
    fonte_slug: str
    categoria: str
    url: str


@dataclass(frozen=True, slots=True)
class Fonte:
    slug: str
    nome: str
    site_url: str
    feeds: tuple[Feed, ...]


@dataclass(frozen=True, slots=True)
class Filtros:
    url_excluir: tuple[str, ...] = ()
    titulo_excluir: tuple[str, ...] = ()


@dataclass(slots=True)
class Noticia:
    fonte_slug: str
    categoria: str
    titulo: str
    url: str
    resumo: str | None = None
    imagem_url: str | None = None
    publicado_em: datetime | None = None
    grupo: str = ""
    relevancia: int = 1


@dataclass(frozen=True, slots=True)
class ValorIndicador:
    codigo: str
    data: date
    valor: Decimal


@dataclass(slots=True)
class ResultadoFeed:
    feed: Feed
    noticias: list[Noticia] = field(default_factory=list)
    erro: str | None = None
