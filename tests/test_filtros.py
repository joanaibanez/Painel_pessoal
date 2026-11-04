from pipeline.config import carregar
from pipeline.filtros import motivo_exclusao
from pipeline.modelos import Noticia

_, FILTROS = carregar()


def _n(titulo: str, url: str = "https://site.com.br/economia/materia") -> Noticia:
    return Noticia("f", "economia", titulo, url)


def test_exclui_opiniao_pela_url():
    assert motivo_exclusao(_n("Qualquer", "https://site.com.br/opiniao/x"), FILTROS)
    assert motivo_exclusao(_n("Qualquer", "https://site.com.br/colunas/fulano/x"), FILTROS)


def test_exclui_entretenimento_pelo_titulo():
    assert motivo_exclusao(_n("Resultado da Mega-Sena de hoje"), FILTROS)
    assert motivo_exclusao(_n("BBB: participante é eliminado"), FILTROS)
    assert motivo_exclusao(_n("Assista ao vivo à sessão"), FILTROS)


def test_mantem_noticia_factual():
    assert motivo_exclusao(_n("Senado conclui análise do artigo 5º da reforma"), FILTROS) is None
    assert motivo_exclusao(_n("IBGE divulga inflação de outubro"), FILTROS) is None
