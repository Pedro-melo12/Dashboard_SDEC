"""
tabs/gestao_publica.py
======================
Aba Gestão Pública - dados das eleições municipais e gestão.

Estrutura:
1. KPIs (4): total prefeitos, total vereadores, partidos com prefeitos,
            % prefeitas mulheres
2. Mapa de PE colorido por nº de vereadores. Hover: prefeito, partido,
   número de vereadores, RD.
3. Lado a lado: ranking partidos com mais prefeitos (top 8) +
                ranking partidos com mais vereadores (top 8)
4. Lado a lado: gênero prefeitos (donut) + gênero vereadores (donut)
5. Tabela completa - 185 municípios

Fonte: TSE (eleições municipais).
"""

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html, no_update, ALL, ctx

from components import data, ui, charts
from config import PALETTE, SEMANTIC, CHART_FONT


def registrar():
    return {
        'eixo': 'Gestão Pública',
        'sub': 'Eleições municipais',
        'eixo_ordem': 3,
        'sub_ordem': 1,
        'ativa': True,
        'fonte_legenda': 'TSE · Eleições municipais',
    }


# ============================================================================
# KPIs
# ============================================================================

def _construir_kpis():
    df_pref = data.prefeitos()
    df_ver = data.vereadores()

    n_pref = len(df_pref)
    n_ver = len(df_ver)
    n_partidos_pref = df_pref['prefeito_partido'].nunique()
    pct_mulheres = 100 * (df_pref['prefeito_genero'] == 'FEMININO').sum() / n_pref

    return html.Div(className="kpi-faixa kpi-faixa-quatro", children=[
        html.Div(className="kpi-contexto-tag", children="Pernambuco"),
        ui.kpi_simples(
            label="prefeitos eleitos",
            valor=str(n_pref),
            sub=("184 municípios com prefeito (Fernando de Noronha não tem)",
                 "neutro"),
            accent=SEMANTIC['destaque'],
        ),
        ui.kpi_simples(
            label="vereadores eleitos",
            valor=f"{n_ver:,}".replace(',', '.'),
            sub=(f"média de {n_ver/n_pref:.1f} por município".replace('.', ','),
                 "neutro"),
        ),
        ui.kpi_simples(
            label="partidos com prefeitos",
            valor=str(n_partidos_pref),
            sub=("disputaram e venceram pelo menos 1 prefeitura", "neutro"),
        ),
        ui.kpi_simples(
            label="prefeitas mulheres",
            valor=f"{pct_mulheres:.1f}%".replace('.', ','),
            sub=(f"{int(round(pct_mulheres * n_pref / 100))} de {n_pref} municípios",
                 "neutro"),
        ),
    ])


# ============================================================================
# Mapa - colorido por número de vereadores
# ============================================================================

def _construir_mapa():
    from config import GEO_MUNICIPIOS
    if not GEO_MUNICIPIOS.exists():
        return html.Div(
            className="aviso-dados",
            style={"padding": "40px", "text-align": "center"},
            children=[
                html.P("ⓘ Mapa indisponível: GeoJSON ainda não foi baixado.",
                       style={"font-size": "13px", "margin-bottom": "8px"}),
                html.Span("Rode no terminal: ", style={"font-size": "12px"}),
                html.Code("python -m etl.geo_etl",
                          style={"background": "#FFF", "padding": "2px 8px",
                                 "border-radius": "3px", "font-size": "12px"}),
            ]
        )

    df = data.gestao_publica_municipal().copy()
    df['prefeito_nome'] = df['prefeito_nome'].fillna('—')
    df['prefeito_partido'] = df['prefeito_partido'].fillna('—')
    df['regiao_desenvolvimento'] = df['regiao_desenvolvimento'].fillna('—')

    geo = data.geojson_municipios()

    hovertemplate = (
        '<b>%{text}</b><br>'
        '<i>%{customdata[3]}</i><br>'
        '────────<br>'
        'prefeito: %{customdata[0]}<br>'
        'partido: %{customdata[1]}<br>'
        'vereadores: %{customdata[2]}'
    )

    fig = charts.mapa_municipios_pe(
        df=df,
        geojson=geo,
        valor_col='n_vereadores',
        hovertemplate=hovertemplate,
        customdata_cols=['prefeito_nome', 'prefeito_partido',
                         'n_vereadores', 'regiao_desenvolvimento'],
        altura=460,
        titulo_legenda='nº vereadores',
    )

    return dcc.Graph(
        id='mapa-gestao',
        figure=fig,
        config={'displayModeBar': False, 'scrollZoom': False},
    )


# ============================================================================
# Rankings de partidos
# ============================================================================

def _ranking_partidos_prefeitos():
    df = data.n_prefeitos_por_partido().head(8)
    fig = charts.barras_ranking(
        df=df, label_col='partido', valor_col='n_prefeitos',
        altura=320, top_n=8,
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


def _ranking_partidos_vereadores():
    df = data.n_vereadores_por_partido().head(8)
    fig = charts.barras_ranking(
        df=df, label_col='partido', valor_col='n_vereadores',
        altura=320, top_n=8,
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ============================================================================
# Donuts de gênero
# ============================================================================

def _donut_genero_prefeitos():
    dist = data.distribuicao_genero_prefeitos()
    masc = dist.get('MASCULINO', 0)
    fem = dist.get('FEMININO', 0)
    total = masc + fem

    fig = charts.donut_dois(
        label_a='Masculino', valor_a=masc,
        label_b='Feminino', valor_b=fem,
        cor_a=SEMANTIC['destaque'],
        cor_b=PALETTE['terracota'],
        total_centro=f"<b>{total}</b><br>"
                     f"<span style='font-size:10px;color:#7A7A7A'>"
                     f"prefeitos eleitos</span>",
        altura=260,
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


def _donut_genero_vereadores():
    df = data.vereadores()
    masc = int((df['genero'] == 'MASCULINO').sum())
    fem = int((df['genero'] == 'FEMININO').sum())
    total = masc + fem

    fig = charts.donut_dois(
        label_a='Masculino', valor_a=masc,
        label_b='Feminino', valor_b=fem,
        cor_a=SEMANTIC['destaque'],
        cor_b=PALETTE['terracota'],
        total_centro=f"<b>{total:,}</b><br>".replace(',', '.') +
                     f"<span style='font-size:10px;color:#7A7A7A'>"
                     f"vereadores eleitos</span>",
        altura=260,
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ============================================================================
# Tabela completa - 185 municípios (manual, com sort)
# ============================================================================

COLUNAS_TABELA_GP = [
    {'id': 'municipio', 'nome': 'Município', 'fmt': str, 'tipo': 'texto'},
    {'id': 'regiao_desenvolvimento', 'nome': 'RD',
     'fmt': lambda v: '—' if pd.isna(v) else str(v), 'tipo': 'texto'},
    {'id': 'prefeito_nome', 'nome': 'Prefeito',
     'fmt': lambda v: '—' if pd.isna(v) else str(v), 'tipo': 'texto'},
    {'id': 'prefeito_partido', 'nome': 'Partido',
     'fmt': lambda v: '—' if pd.isna(v) else str(v), 'tipo': 'texto'},
    {'id': 'n_vereadores', 'nome': 'Vereadores',
     'fmt': lambda v: str(int(v)) if pd.notna(v) else '0', 'tipo': 'numero'},
]


def _tabela_gestao(sort_col: str = 'municipio', sort_dir: str = 'asc'):
    df = data.gestao_publica_municipal().copy()

    if sort_col in df.columns:
        df = df.sort_values(sort_col,
                             ascending=(sort_dir == 'asc'),
                             na_position='last').reset_index(drop=True)

    header_cells = []
    for col in COLUNAS_TABELA_GP:
        seta = ''
        if col['id'] == sort_col:
            seta = ' ▾' if sort_dir == 'desc' else ' ▴'
        classes = f"th-{col['tipo']}"
        if col['id'] == sort_col:
            classes += ' th-active'
        header_cells.append(html.Th(
            col['nome'] + seta,
            id={'type': 'th-sort-gp', 'index': col['id']},
            className=classes,
            n_clicks=0,
        ))

    body_rows = []
    for _, row in df.iterrows():
        cells = []
        for col in COLUNAS_TABELA_GP:
            valor_bruto = row.get(col['id'])
            valor_fmt = col['fmt'](valor_bruto)
            cells.append(html.Td(valor_fmt, className=f"td-{col['tipo']}"))
        body_rows.append(html.Tr(cells))

    return html.Table(
        className='tabela-gestao',
        children=[
            html.Thead(html.Tr(header_cells)),
            html.Tbody(body_rows),
        ],
    )


# ============================================================================
# Layout
# ============================================================================

def layout():
    return html.Div(className="aba-conteudo", children=[

        html.Div(className="aba-titulo-bloco", children=[
            html.Div([
                html.P("Gestão Pública · eleições municipais",
                       className="aba-titulo"),
                html.P("prefeitos, vereadores e partidos · 185 municípios",
                       className="aba-subtitulo"),
            ]),
        ]),

        _construir_kpis(),

        # Mapa
        ui.secao(
            etiqueta="geografia política",
            titulo="",
            descricao="cor por número de vereadores · "
                      "passe o cursor para ver prefeito e partido",
            children=_construir_mapa(),
        ),

        # Rankings
        html.Div(className="grid-duplo grid-1-1", children=[
            ui.secao(
                etiqueta="prefeituras por partido",
                titulo="",
                descricao="top 8 partidos com mais prefeitos eleitos",
                children=_ranking_partidos_prefeitos(),
            ),
            ui.secao(
                etiqueta="vereadores por partido",
                titulo="",
                descricao="top 8 partidos com mais vereadores eleitos",
                children=_ranking_partidos_vereadores(),
            ),
        ]),

        # Donuts gênero
        html.Div(className="grid-duplo grid-1-1", children=[
            ui.secao(
                etiqueta="composição por gênero",
                titulo="",
                descricao="prefeitos eleitos · masculino × feminino",
                children=_donut_genero_prefeitos(),
            ),
            ui.secao(
                etiqueta="composição por gênero",
                titulo="",
                descricao="vereadores eleitos · masculino × feminino",
                children=_donut_genero_vereadores(),
            ),
        ]),

        # Tabela
        ui.secao(
            etiqueta="todos os municípios",
            titulo="",
            descricao="prefeito, partido e número de vereadores · "
                      "clique nos cabeçalhos para ordenar",
            children=html.Div([
                dcc.Store(id='tabela-gp-sort-state',
                          data={'col': 'municipio', 'dir': 'asc'}),
                html.Div(id='tabela-gp-container',
                         children=_tabela_gestao()),
            ]),
        ),

        ui.footer(
            fonte_principal="TSE · Eleições municipais",
            atualizacao="2024",
        ),
    ])


# ============================================================================
# Callbacks
# ============================================================================

def callbacks(app):

    @app.callback(
        Output('tabela-gp-sort-state', 'data'),
        Input({'type': 'th-sort-gp', 'index': ALL}, 'n_clicks'),
        State('tabela-gp-sort-state', 'data'),
        prevent_initial_call=True,
    )
    def atualizar_sort_gp(_clicks, atual):
        trigger = ctx.triggered_id
        if not isinstance(trigger, dict):
            return no_update
        col = trigger.get('index')
        if col is None:
            return no_update
        if atual and atual.get('col') == col:
            nova_dir = 'desc' if atual.get('dir') == 'asc' else 'asc'
        else:
            nova_dir = 'asc'
        return {'col': col, 'dir': nova_dir}

    @app.callback(
        Output('tabela-gp-container', 'children'),
        Input('tabela-gp-sort-state', 'data'),
    )
    def renderizar_tabela_gp(state):
        if not state:
            return no_update
        return _tabela_gestao(
            sort_col=state.get('col', 'municipio'),
            sort_dir=state.get('dir', 'asc'),
        )
