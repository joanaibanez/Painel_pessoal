from pipeline.config import carregar
from pipeline.modelos import CATEGORIAS_VALIDAS


def test_config_padrao_valida():
    fontes, filtros = carregar()
    assert len(fontes) >= 5
    feeds = [f for fonte in fontes for f in fonte.feeds]
    assert all(f.categoria in CATEGORIAS_VALIDAS for f in feeds)
    assert all(f.url.startswith("https://") for f in feeds)
    assert filtros.url_excluir and filtros.titulo_excluir
