# Observatório Econômico de Pernambuco

Dashboard institucional desenvolvido em Python/Dash para a Secretaria de Desenvolvimento Econômico do Estado de Pernambuco.

## O que é

Plataforma de visualização de indicadores econômicos de Pernambuco, projetada como **observatório extensível**: cada nova temática (PIB, comércio exterior, demografia, etc.) entra como um novo arquivo na pasta `tabs/`, sem refatoração.

A primeira versão cobre **Mercado de Trabalho** com duas abas:

- **Emprego formal** (CAGED): saldo, admissões e desligamentos a nível municipal, com mapa interativo dos 185 municípios
- **Desemprego** (PNAD Contínua): taxa de desocupação, rendimento médio, ocupação e desalentados a nível estadual

## Estrutura do projeto

```
observatorio_pe/
├── app.py                  # entrada principal
├── config.py               # paleta, caminhos, metadados
├── requirements.txt
│
├── data/
│   ├── raw/                # arquivos originais (xlsx)
│   ├── processed/          # parquets gerados pelo ETL
│   └── geo/                # geojson de municípios
│
├── etl/
│   ├── caged_etl.py        # ETL CAGED
│   ├── pnad_etl.py         # ETL PNAD
│   ├── geo_etl.py          # baixa GeoJSON do IBGE
│   └── run_all.py          # orquestrador
│
├── components/
│   ├── data.py             # acesso aos dados (com cache)
│   ├── charts.py           # gráficos Plotly padronizados
│   └── ui.py               # componentes de UI (cards, headers)
│
├── tabs/                   # ★ adicione novas abas aqui
│   ├── _template.py        # modelo para criar abas
│   ├── desemprego.py
│   └── emprego_formal.py
│
└── assets/
    ├── style.css           # CSS principal
    └── logo.jpeg           # logos institucionais
```

## Como rodar localmente

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Processar os dados (uma vez só)

```bash
python -m etl.run_all
```

Isso vai:
- Baixar o GeoJSON dos municípios de PE direto do IBGE
- Ler `data/raw/CAGED_PE.xlsx` e `data/raw/PNAD_PE.xlsx`
- Gerar os parquets em `data/processed/`
- Criar o catálogo de metadados

### 3. Iniciar o app

```bash
python app.py
```

Abrir <http://127.0.0.1:8050> no navegador.

## Como atualizar os dados

Quando chegar uma nova versão do CAGED ou da PNAD:

1. Substitua o arquivo correspondente em `data/raw/`
2. Rode `python -m etl.run_all`
3. Reinicie o app

O ETL é idempotente: pode rodar quantas vezes quiser sem efeito colateral.

## Como adicionar uma nova aba

1. Copie o template:

   ```bash
   cp tabs/_template.py tabs/comercio_exterior.py
   ```

2. Edite o arquivo, implementando as três funções:
   - `registrar()` → metadados (eixo, sub, ordem)
   - `layout()` → componente Dash do conteúdo
   - `callbacks(app)` → callbacks de interatividade (pode ficar vazio)

3. Reinicie o app. A aba aparece sozinha no menu.

Não é preciso modificar `app.py`.

## Sobre o formato Parquet

Os arquivos em `data/processed/` estão em formato Parquet, não CSV. Vantagens:
- 5-10× menor que CSV
- Carregamento muito mais rápido
- Tipos de dados preservados (datas, números)
- Sem problemas de encoding

Para inspecionar um Parquet, use Python:

```python
import pandas as pd
df = pd.read_parquet('data/processed/caged_municipal.parquet')
print(df.head())
df.to_csv('inspecao.csv', index=False)  # converter se quiser ver no Excel
```

## Identidade visual

Paleta sóbria e pastel definida em `config.py`. Para mudar todas as cores do dashboard, edite o dicionário `PALETTE` lá - todos os componentes referenciam essas variáveis.

## Deploy

Para colocar em produção (Render, Railway, servidor próprio), use gunicorn:

```bash
gunicorn app:server --bind 0.0.0.0:8000
```

A variável `server` em `app.py` é o WSGI app exposto justamente para isso.

## Licença e autoria

Projeto da Secretaria de Desenvolvimento Econômico do Governo do Estado de Pernambuco.
