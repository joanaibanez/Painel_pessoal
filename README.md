# Painel Pessoal — Brasil

Painel diário com as manchetes importantes do Brasil e indicadores econômicos.

- **Coleta:** GitHub Actions, todo dia às 07h (Brasília).
- **Banco:** PostgreSQL relacional no Supabase.
- **Site:** página estática no GitHub Pages que lê o banco pela API do Supabase. Clicar numa manchete abre a matéria no site original.

```
 ┌───────────────┐  07h BRT   ┌────────────────────┐  upsert  ┌──────────────────┐
 │ GitHub Actions│──────────▶ │ pipeline (Python)  │────────▶ │ Supabase Postgres│
 │  cron diário  │            │ RSS + BCB/SGS      │          │  (RLS: só leitura│
 └───────────────┘            └────────────────────┘          │   para o público)│
                                                              └────────┬─────────┘
                                                                       │ REST (chave publishable)
                                                              ┌────────▼─────────┐
                                                              │ GitHub Pages     │
                                                              │ site/index.html  │
                                                              └──────────────────┘
```

## Neutralidade editorial

| Mecanismo | Como funciona |
|---|---|
| Fontes diversas | Agência Brasil (pública), g1, Folha, Estadão, CNN Brasil e BBC News Brasil. |
| Sem opinião | URLs de colunas, blogs, editoriais e análises são descartadas, assim como entretenimento, loterias e publieditoriais (`pipeline/fontes.toml`). |
| Importância objetiva | Manchetes equivalentes de veículos diferentes são agrupadas. A relevância é o **número de redações independentes** que publicaram o fato. Não há palavra-chave “importante” nem peso por veículo. |
| Manchete principal | Em cada grupo, aparece primeiro a versão de quem publicou antes. As demais ficam em “Também em…”. |

Limitação: nenhum filtro automático garante neutralidade absoluta. O pipeline só não introduz viés próprio. O enquadramento de cada manchete continua sendo do veículo de origem.

## Estrutura

```
.github/workflows/
  coleta-diaria.yml   # cron 07h BRT + execução manual (com opção dry-run)
  ci.yml              # ruff + pytest
  pages.yml           # publica site/ no GitHub Pages
pipeline/             # coleta, filtros, agrupamento, persistência
  fontes.toml         # fontes, feeds e regras de exclusão (edite aqui)
supabase/migrations/  # modelagem de dados (aplicada automaticamente pelo pipeline)
site/index.html       # painel
tests/                # testes unitários
```

## Modelagem de dados

| Tabela | Conteúdo | Leitura pública |
|---|---|---|
| `categorias` | Editorias (Brasil, Economia, Governo e leis, Saúde…) | sim |
| `fontes` | Veículos monitorados | sim |
| `feeds` | URLs RSS de cada fonte → categoria | não |
| `coletas` | Uma linha por execução: status, contagens e erros | sim |
| `noticias` | Manchetes (URL única), `grupo` e `relevancia` | sim |
| `indicadores` / `indicador_valores` | Dólar, euro, Selic e IPCA (Banco Central) | sim |

- Todas as tabelas têm RLS ligado.
- O papel `anon` (chave publishable usada no site) só tem `SELECT`.
- Só o pipeline escreve, conectado como `postgres` via secret.
- As migrações ficam registradas em `pipeline.migracoes`, num schema que a API não expõe.

## Configuração (uma vez)

1. **Secret do banco.** Em *Settings → Secrets and variables → Actions → New repository secret*:
   - Nome: `SUPABASE_DB_URL`
   - Valor: a string de conexão do pooler, `postgresql://postgres.<ref>:<senha>@aws-0-us-east-2.pooler.supabase.com:6543/postgres`
2. **GitHub Pages.** Em *Settings → Pages → Build and deployment → Source*, escolha **GitHub Actions**. Depois rode o workflow *Publicar site* uma vez.
3. **Primeira carga.** Em *Actions → Coleta diária de notícias → Run workflow*. A primeira execução cria as tabelas automaticamente.

Para testar as fontes sem gravar no banco, use *Run workflow* com **dry_run** marcado. O resumo do job mostra quantos itens cada feed devolveu.

## Desenvolvimento local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && ruff format --check . && pytest
python -m pipeline --dry-run          # coleta sem gravar
SUPABASE_DB_URL=... python -m pipeline # coleta e grava
```

## Operação

- **Adicionar ou remover uma fonte:** edite `pipeline/fontes.toml`. Na execução seguinte, fontes e feeds são sincronizados, e os removidos são marcados como inativos.
- **Mudar o esquema:** crie `supabase/migrations/0002_<descricao>.sql`. Ele é aplicado uma única vez, em transação.
- **Retenção:** notícias com mais de 180 dias são apagadas (`RETENCAO_DIAS`).
- **Status das coletas:** `sucesso` quando tudo funcionou, `parcial` quando algum feed ou indicador falhou (o restante é gravado), `falha` quando nenhum feed respondeu (o job fica vermelho).
- **Atenção:** o GitHub desativa workflows agendados em repositórios públicos sem commits há 60 dias. Se isso acontecer, reative em *Actions*.
