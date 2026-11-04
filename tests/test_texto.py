from pipeline.texto import contem_expressao, limpar_html, normalizar, normalizar_url, tokens


def test_normalizar_remove_acentos_e_pontuacao():
    assert normalizar("Ação: São Paulo, já!") == "acao sao paulo ja"


def test_tokens_ignora_stopwords_e_palavras_curtas():
    esperado = {"banco", "central", "mantem", "selic"}
    assert tokens("O Banco Central mantém a Selic em 10%") == esperado


def test_limpar_html_e_truncar():
    assert limpar_html("<p>Olá &amp; <b>mundo</b></p>") == "Olá & mundo"
    assert limpar_html("palavra " * 50, limite=20).endswith("…")
    assert limpar_html("<br/>") is None


def test_normalizar_url_remove_rastreio_e_fragmento():
    url = "HTTPS://Site.COM.br/a?utm_source=x&id=1&fbclid=y#sec"
    assert normalizar_url(url) == "https://site.com.br/a?id=1"


def test_normalizar_url_rejeita_esquemas_inseguros():
    assert normalizar_url("javascript:alert(1)") is None
    assert normalizar_url("ftp://x.com/a") is None
    assert normalizar_url("") is None


def test_contem_expressao_palavra_inteira():
    assert contem_expressao("resultado da mega sena hoje", "mega sena")
    assert not contem_expressao("bbbanco", "bbb")
