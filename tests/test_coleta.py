from datetime import UTC, datetime, timedelta
from pathlib import Path

from pipeline.coleta import deduplicar, dentro_da_janela, interpretar
from pipeline.modelos import Feed, Noticia

FIXTURE = Path(__file__).parent / "fixtures" / "feed_exemplo.xml"
FEED = Feed(fonte_slug="exemplo", categoria="economia", url="https://exemplo.com.br/rss")


def test_interpretar_feed_rss():
    noticias = interpretar(FIXTURE.read_bytes(), FEED)

    assert [n.titulo for n in noticias] == [
        "Banco Central mantém taxa Selic em 10,5% ao ano",
        "Opinião: o que esperar da economia",
    ]  # item com link javascript: descartado
    selic = noticias[0]
    assert selic.url == "https://exemplo.com.br/economia/2026/11/04/selic.ghtml?id=7"
    assert selic.resumo == "O Copom decidiu manter a taxa."
    assert selic.imagem_url == "https://img.exemplo.com.br/selic.jpg"
    assert selic.publicado_em == datetime(2026, 11, 4, 12, tzinfo=UTC)
    assert selic.categoria == "economia"


def test_janela_temporal():
    agora = datetime(2026, 11, 4, 10, tzinfo=UTC)
    n = Noticia("f", "geral", "t", "https://x")
    assert dentro_da_janela(n, agora, 30)  # sem data → aceita
    n.publicado_em = agora - timedelta(hours=29)
    assert dentro_da_janela(n, agora, 30)
    n.publicado_em = agora - timedelta(hours=31)
    assert not dentro_da_janela(n, agora, 30)
    n.publicado_em = agora + timedelta(days=1)
    assert not dentro_da_janela(n, agora, 30)


def test_deduplicar_prefere_categoria_especifica():
    a = Noticia("f", "geral", "t", "https://x/1")
    b = Noticia("f", "saude", "t", "https://x/1")
    c = Noticia("f", "mundo", "t", "https://x/2")
    resultado = deduplicar([a, b, c])
    assert [(n.url, n.categoria) for n in resultado] == [
        ("https://x/1", "saude"),
        ("https://x/2", "mundo"),
    ]
