"""Agrupamento de manchetes equivalentes entre fontes e cálculo de relevância.

Critério neutro de importância: um fato é mais relevante quanto mais redações
independentes o noticiam. Não há nenhum julgamento de conteúdo/ideologia.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from pipeline.modelos import Noticia
from pipeline.texto import tokens

MIN_TERMOS_EM_COMUM = 3
LIMIAR_SOBREPOSICAO = 0.6


def _semelhantes(a: frozenset[str], b: frozenset[str]) -> bool:
    if not a or not b:
        return False
    comuns = len(a & b)
    return comuns >= MIN_TERMOS_EM_COMUM and comuns / min(len(a), len(b)) >= LIMIAR_SOBREPOSICAO


def agrupar(noticias: Sequence[Noticia]) -> None:
    """Preenche `grupo` e `relevancia` de cada notícia (in-place).

    Usa union-find sobre pares de fontes diferentes cujos títulos compartilham
    a maior parte dos termos significativos (coeficiente de sobreposição).
    """
    n = len(noticias)
    pai = list(range(n))

    def raiz(i: int) -> int:
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    termos = [tokens(x.titulo) for x in noticias]
    for i in range(n):
        for j in range(i + 1, n):
            if noticias[i].fonte_slug != noticias[j].fonte_slug and _semelhantes(
                termos[i], termos[j]
            ):
                pai[raiz(i)] = raiz(j)

    grupos: dict[int, list[int]] = {}
    for i in range(n):
        grupos.setdefault(raiz(i), []).append(i)

    for membros in grupos.values():
        chave = min(noticias[i].url for i in membros)
        grupo_id = hashlib.sha1(chave.encode(), usedforsecurity=False).hexdigest()[:16]
        relevancia = len({noticias[i].fonte_slug for i in membros})
        for i in membros:
            noticias[i].grupo = grupo_id
            noticias[i].relevancia = relevancia
