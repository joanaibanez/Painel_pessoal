from pipeline.modelos import Noticia
from pipeline.relevancia import agrupar


def test_agrupa_mesmo_fato_em_fontes_diferentes():
    noticias = [
        Noticia("g1", "economia", "Copom mantém taxa Selic em 10,5% ao ano", "https://a/1"),
        Noticia("folha", "economia", "Copom decide manter a Selic em 10,5% ao ano", "https://b/1"),
        Noticia("cnn", "economia", "Banco Central: Copom mantém Selic em 10,5%", "https://c/1"),
        Noticia("g1", "saude", "Ministério amplia vacinação contra dengue", "https://a/2"),
    ]
    agrupar(noticias)

    selic = noticias[:3]
    assert len({n.grupo for n in selic}) == 1
    assert all(n.relevancia == 3 for n in selic)
    assert noticias[3].grupo != selic[0].grupo
    assert noticias[3].relevancia == 1


def test_mesma_fonte_nao_infla_relevancia():
    noticias = [
        Noticia("g1", "geral", "Chuvas fortes atingem o litoral de São Paulo", "https://a/1"),
        Noticia("g1", "geral", "Chuvas fortes atingem litoral de São Paulo hoje", "https://a/2"),
    ]
    agrupar(noticias)
    assert all(n.relevancia == 1 for n in noticias)


def test_grupo_e_deterministico():
    def montar():
        return [
            Noticia("x", "geral", "Enem 2026 tem gabarito divulgado pelo Inep", "https://x/1"),
            Noticia("y", "geral", "Inep divulga gabarito do Enem 2026", "https://y/1"),
        ]

    a, b = montar(), montar()
    agrupar(a)
    agrupar(b)
    assert [n.grupo for n in a] == [n.grupo for n in b]
