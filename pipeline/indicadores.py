"""Indicadores econômicos do Banco Central (API SGS, dados abertos)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

import httpx

from pipeline.coleta import baixar, criar_cliente
from pipeline.modelos import ValorIndicador

log = logging.getLogger(__name__)

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/{n}?formato=json"

# codigo -> série SGS (mantenha em sincronia com a tabela public.indicadores)
SERIES: dict[str, int] = {
    "dolar_ptax": 1,
    "euro_ptax": 21619,
    "selic_meta": 432,
    "ipca_12m": 13522,
}


def interpretar(codigo: str, dados: list[dict[str, str]]) -> list[ValorIndicador]:
    valores: list[ValorIndicador] = []
    for item in dados:
        try:
            valores.append(
                ValorIndicador(
                    codigo=codigo,
                    data=datetime.strptime(item["data"], "%d/%m/%Y").date(),
                    valor=Decimal(item["valor"]),
                )
            )
        except (KeyError, ValueError, InvalidOperation):
            log.warning("valor inválido em %s: %r", codigo, item)
    return valores


def coletar(ultimos: int = 2) -> tuple[list[ValorIndicador], list[str]]:
    """Retorna (valores, erros). Falhas não interrompem o pipeline."""
    valores: list[ValorIndicador] = []
    erros: list[str] = []
    with criar_cliente() as cliente:
        cliente.headers["Accept"] = "application/json"
        for codigo, serie in SERIES.items():
            try:
                bruto = baixar(cliente, URL_SGS.format(serie=serie, n=ultimos))
                novos = interpretar(codigo, json.loads(bruto))
                valores += novos
                log.info("ok   indicador %-12s %d valores", codigo, len(novos))
            except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                log.warning("erro indicador %s: %s", codigo, exc)
                erros.append(f"indicador {codigo}: {exc}"[:500])
    return valores, erros
