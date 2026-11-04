from datetime import date
from decimal import Decimal

from pipeline.indicadores import interpretar


def test_interpretar_resposta_sgs():
    dados = [{"data": "03/11/2026", "valor": "5.4321"}, {"data": "xx", "valor": "1"}]
    valores = interpretar("dolar_ptax", dados)
    assert len(valores) == 1
    assert valores[0].data == date(2026, 11, 3)
    assert valores[0].valor == Decimal("5.4321")
