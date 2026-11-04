"""Carregamento e validação da configuração de fontes (fontes.toml)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pipeline.modelos import CATEGORIAS_VALIDAS, Feed, Filtros, Fonte
from pipeline.texto import normalizar

CAMINHO_PADRAO = Path(__file__).with_name("fontes.toml")


class ConfigInvalida(ValueError):
    """Erro de validação do arquivo de fontes."""


def carregar(caminho: Path = CAMINHO_PADRAO) -> tuple[list[Fonte], Filtros]:
    with caminho.open("rb") as fp:
        bruto = tomllib.load(fp)

    filtros_brutos = bruto.get("filtros", {})
    filtros = Filtros(
        url_excluir=tuple(s.lower() for s in filtros_brutos.get("url_excluir", [])),
        titulo_excluir=tuple(normalizar(s) for s in filtros_brutos.get("titulo_excluir", [])),
    )

    fontes: list[Fonte] = []
    slugs: set[str] = set()
    urls: set[str] = set()
    for item in bruto.get("fontes", []):
        slug = item["slug"]
        if slug in slugs:
            raise ConfigInvalida(f"slug de fonte duplicado: {slug}")
        slugs.add(slug)

        feeds: list[Feed] = []
        for f in item.get("feeds", []):
            if f["categoria"] not in CATEGORIAS_VALIDAS:
                raise ConfigInvalida(f"categoria inválida em {slug}: {f['categoria']}")
            if f["url"] in urls:
                raise ConfigInvalida(f"feed duplicado: {f['url']}")
            urls.add(f["url"])
            feeds.append(Feed(fonte_slug=slug, categoria=f["categoria"], url=f["url"]))

        fontes.append(
            Fonte(slug=slug, nome=item["nome"], site_url=item["site_url"], feeds=tuple(feeds))
        )

    if not fontes:
        raise ConfigInvalida("nenhuma fonte configurada")
    return fontes, filtros
