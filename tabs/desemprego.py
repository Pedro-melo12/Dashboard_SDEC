"""
tabs/desemprego.py
==================
Aba Desemprego - PNAD Contínua.

Estrutura:
1. Faixa de KPIs (5 cards): taxa, ocupados, desocupados, desalentados, rendimento
2. Série histórica - taxa de desemprego ao longo do tempo (PE vs NE)
3. Estrutura da PEA (donut com filtro de trimestre) + Ranking 9 estados (com filtros)
4. Rendimento PE vs NE + Pobreza/Extrema pobreza em PE
5. Tabela completa - 9 estados × indicadores

Fontes:
- PNAD Contínua trimestral (IBGE), regiões: 9 estados do NE + Nordeste agregado
- Período: 2012-T1 a 2025-T3
"""

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html, no_update

from components import data, ui, charts
from components.ui import fmt_num, fmt_pct, fmt_brl, fmt_signed
from config import PALETTE, SEMANTIC, CHART_FONT


def registrar():
    return {
        'eixo': 'Mercado de trabalho',
        'sub': 'Desemprego',
        'eixo_ordem': 1,
        'sub_ordem': 2,
        'ativa': True,
        'fonte_legenda': 'PNAD Contínua · IBGE',
    }


# ============================================================================
# Helpers de formatação
# ============================================================================

def _fmt_milhares(n):
    """Ex: 416828 -> '416,8 mil'"""
    if n is None or pd.isna(n):
        return "—"
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.2f} mi".replace('.', ',')
    if abs(n) >= 1_000:
        return f"{n/1_000:.1f} mil".replace('.', ',')
    return fmt_num(int(n))


# ============================================================================
# KPIs - 5 indicadores principais
# ============================================================================

def _construir_kpis():
    """5 KPIs principais para PE no último trimestre disponível."""
    taxa = data.pnad_reg_ultimo_valor('taxa_desemprego', 'Pernambuco')
    ocupados = data.pnad_reg_ultimo_valor('ocupados', 'Pernambuco')
    desocupados = data.pnad_reg_ultimo_valor('desocupados', 'Pernambuco')
    desalentados = data.pnad_reg_ultimo_valor('desalentados', 'Pernambuco')
    rendimento = data.pnad_reg_ultimo_valor('rendimento_medio', 'Pernambuco')

    def _sub_pp(info, inverter_cor=False):
        """
        Subtítulo com variação. inverter_cor=True para indicadores onde
        'subir é ruim' (taxa de desemprego, desocupados, desalentados).
        """
        if info['variacao_pp'] is None:
            return None
        var = info['variacao_pp']
        seta = '▲' if var > 0 else '▼' if var < 0 else '—'
        cor_neutra = 'positivo' if var > 0 else 'negativo'
        cor_invertida = 'negativo' if var > 0 else 'positivo'
        cor = cor_invertida if inverter_cor else cor_neutra
        if info['unidade'] == '%':
            return (f"{seta} {abs(var):.1f}pp vs trim. anterior", cor)
        else:
            return (f"{seta} {fmt_signed(int(var))} vs trim. anterior", cor)

    return html.Div(className="kpi-faixa kpi-faixa-cinco", children=[
        html.Div(className="kpi-contexto-tag", children="Pernambuco"),
        ui.kpi_simples(
            label=f"taxa desemprego · {taxa['trimestre']}",
            valor=fmt_pct(taxa['valor']),
            sub=_sub_pp(taxa, inverter_cor=True),
            accent=SEMANTIC['destaque'],
        ),
        ui.kpi_simples(
            label="população ocupada",
            valor=_fmt_milhares(ocupados['valor']),
            sub=_sub_pp(ocupados),
        ),
        ui.kpi_simples(
            label="população desocupada",
            valor=_fmt_milhares(desocupados['valor']),
            sub=_sub_pp(desocupados, inverter_cor=True),
        ),
        ui.kpi_simples(
            label="desalentados",
            valor=_fmt_milhares(desalentados['valor']),
            sub=_sub_pp(desalentados, inverter_cor=True),
        ),
        ui.kpi_simples(
            label="rendimento médio",
            valor=fmt_brl(rendimento['valor']),
            sub=_sub_pp(rendimento),
        ),
    ])


# ============================================================================
# Série histórica - taxa de desemprego (PE vs NE)
# ============================================================================

def _serie_taxa_desemprego():
    df = data.pnad_reg_indicador('taxa_desemprego')
    df = df[df['regiao'].isin(['Pernambuco', 'Nordeste'])]
    df = df[df['valor'].notna()]

    cores = {
        'Pernambuco': SEMANTIC['destaque'],
        'Nordeste': PALETTE['lilas_acinzentado'],
    }
    fig = charts.linha_multipla(
        df=df, x='data', y='valor', grupo='regiao',
        cores=cores,
        altura=320,
        anotacao=(pd.Timestamp('2020-03-01'), 'pandemia'),
        formato_y=',.1f',
    )
    fig.update_layout(yaxis=dict(
        ticksuffix='%',
        showgrid=True,
        gridcolor=PALETTE["cinza_neblina"],
        gridwidth=0.5,
        zeroline=True,
        zerolinecolor=PALETTE["cinza_claro"],
        tickfont=dict(size=10, color=PALETTE["cinza_medio"]),
    ))
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ============================================================================
# Estrutura da PEA - Donut com filtro de trimestre
# ============================================================================

def _donut_pea(trimestre: str = None, regiao: str = 'Pernambuco'):
    """Donut com 4 fatias da população em idade de trabalhar."""
    info = data.pnad_reg_estrutura_pea(regiao=regiao,
                                        trimestre_label=trimestre)

    labels = ['Ocupados', 'Desocupados', 'Desalentados', 'Fora da força']
    valores = [info['ocupados'], info['desocupados'],
               info['desalentados'], info['fora_outros']]
    cores = [
        SEMANTIC['destaque'],
        PALETTE['terracota'],
        PALETTE['mostarda_suave'],
        PALETTE['cinza_neblina'],
    ]

    total_str = _fmt_milhares(info['total'])
    fig = charts.donut_n(
        labels=labels,
        valores=valores,
        cores=cores,
        total_centro=f"<b>{total_str}</b><br>"
                     f"<span style='font-size:9px;color:#7A7A7A'>"
                     f"em idade de trabalhar</span>",
        altura=280,
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


def _opcoes_trimestres_pea():
    trimestres = data.pnad_reg_trimestres_disponiveis('Pernambuco')
    return [{'label': t, 'value': t} for t in trimestres]


# ============================================================================
# Ranking dos 9 estados do NE
# ============================================================================

INDICADORES_RANKING = [
    {'value': 'taxa_desemprego', 'label': 'Taxa de desemprego (%)',
     'sufixo': '%', 'menor_melhor': True},
    {'value': 'desocupados', 'label': 'Desocupados (pessoas)',
     'sufixo': '', 'menor_melhor': True},
    {'value': 'ocupados', 'label': 'Ocupados (pessoas)',
     'sufixo': '', 'menor_melhor': False},
    {'value': 'desalentados', 'label': 'Desalentados (pessoas)',
     'sufixo': '', 'menor_melhor': True},
    {'value': 'rendimento_medio', 'label': 'Rendimento médio (R$)',
     'sufixo': '', 'menor_melhor': False},
]


def _ranking_estados(indicador: str = 'taxa_desemprego',
                     trimestre: str = None):
    df = data.pnad_reg_ranking_estados(chave=indicador,
                                        trimestre_label=trimestre)
    if df.empty:
        return html.Div("Sem dados.", className="aviso-dados")

    meta = next((i for i in INDICADORES_RANKING if i['value'] == indicador),
                INDICADORES_RANKING[0])

    fig = charts.barras_com_destaque(
        df=df, label_col='regiao', valor_col='valor',
        destaque='Pernambuco',
        altura=300,
        ordem_ascendente=False,  # sempre decrescente: maiores em cima
        sufixo_valor=meta['sufixo'],
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ============================================================================
# Rendimento médio PE vs NE
# ============================================================================

def _serie_rendimento():
    df = data.pnad_reg_indicador('rendimento_medio')
    df = df[df['regiao'].isin(['Pernambuco', 'Nordeste'])]
    df = df[df['valor'].notna()]
    df = df[df['data'] >= pd.Timestamp('2018-01-01')]  # filtro a partir de 2018

    cores = {
        'Pernambuco': SEMANTIC['destaque'],
        'Nordeste': PALETTE['lilas_acinzentado'],
    }
    fig = charts.linha_multipla(
        df=df, x='data', y='valor', grupo='regiao',
        cores=cores,
        altura=260,
        formato_y=',.0f',
    )
    fig.update_layout(yaxis=dict(
        tickprefix='R$ ',
        showgrid=True,
        gridcolor=PALETTE["cinza_neblina"],
        gridwidth=0.5,
        tickfont=dict(size=10, color=PALETTE["cinza_medio"]),
    ))
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ============================================================================
# Pobreza - área empilhada
# ============================================================================

def _grafico_pobreza():
    df = data.pobreza_serie('Pernambuco')
    df = df[df['data'] >= pd.Timestamp('2018-01-01')]  # filtro a partir de 2018
    if df.empty:
        return html.Div("Sem dados de pobreza.", className="aviso-dados")

    pivot = df.pivot_table(index='data', columns='indicador',
                            values='valor', aggfunc='first').reset_index()
    pivot = pivot.sort_values('data')

    fig = go.Figure()
    if 'pobreza' in pivot.columns:
        fig.add_trace(go.Scatter(
            x=pivot['data'], y=pivot['pobreza'],
            mode='lines', name='Em pobreza',
            line=dict(color=PALETTE['terracota'], width=2),
            fill='tozeroy',
            fillcolor='rgba(201, 147, 131, 0.25)',
            hovertemplate='%{x|%Y-Q%q}<br>%{y:,.0f} pessoas<extra>Em pobreza</extra>',
        ))
    if 'extrema_pobreza' in pivot.columns:
        fig.add_trace(go.Scatter(
            x=pivot['data'], y=pivot['extrema_pobreza'],
            mode='lines', name='Extrema pobreza',
            line=dict(color=PALETTE['preto_titulo'], width=1.5),
            fill='tozeroy',
            fillcolor='rgba(44, 44, 42, 0.45)',
            hovertemplate='%{x|%Y-Q%q}<br>%{y:,.0f} pessoas<extra>Extrema pobreza</extra>',
        ))

    charts.aplicar_layout_default(fig,
        height=260,
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom', y=1.02,
            xanchor='right', x=1,
            font=dict(size=10, color=PALETTE["cinza_medio"]),
        ),
        margin=dict(l=50, r=20, t=30, b=40),
        yaxis=dict(
            showgrid=True,
            gridcolor=PALETTE["cinza_neblina"],
            gridwidth=0.5,
            tickformat=',.0f',
            tickfont=dict(size=10, color=PALETTE["cinza_medio"]),
        ),
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ============================================================================
# Informalidade - taxa (linha temporal a partir de 2018)
# ============================================================================

def _grafico_informalidade_taxa():
    """
    Linha temporal da TAXA de informalidade em PE a partir de 2018.
    Calculada como informais/ocupados × 100.
    """
    df = data.informalidade_serie('Pernambuco')
    df = df[df['data'] >= pd.Timestamp('2018-01-01')]
    if df.empty:
        return html.Div("Sem dados.", className="aviso-dados")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['data'], y=df['taxa'],
        mode='lines',
        name='Taxa de informalidade',
        line=dict(color=PALETTE['terracota'], width=2),
        fill='tozeroy',
        fillcolor='rgba(201, 147, 131, 0.10)',
        hovertemplate='%{x|%Y-Q%q}<br><b>%{y:.1f}%</b> · '
                      'informais sobre ocupados<extra></extra>',
    ))

    # Anotação da pandemia
    fig.add_vline(x=pd.Timestamp('2020-03-01'),
                  line=dict(color=PALETTE["lilas_acinzentado"],
                            width=1, dash='dot'))
    fig.add_annotation(
        x=pd.Timestamp('2020-03-01'), y=1, yref='paper', text='pandemia',
        showarrow=False,
        font=dict(size=10, color=PALETTE["lilas_acinzentado"]),
        xanchor='left', yanchor='top', xshift=4, yshift=-4,
    )

    charts.aplicar_layout_default(fig,
        height=260,
        showlegend=False,
        margin=dict(l=50, r=20, t=20, b=40),
        yaxis=dict(
            ticksuffix='%',
            showgrid=True,
            gridcolor=PALETTE["cinza_neblina"],
            gridwidth=0.5,
            tickfont=dict(size=10, color=PALETTE["cinza_medio"]),
            range=[40, 55],
        ),
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ============================================================================
# Tabela completa - 9 estados (implementação manual com html.Table)
# ============================================================================
#
# Por que html.Table em vez de dash_table?
# O dash_table renderiza header e body em <table>s separadas internamente,
# o que causa desalinhamento entre os widths em browsers diferentes.
# Uma <html.Table> é uma única tag, com <thead> e <tbody> compartilhando
# o mesmo <colgroup> implícito - alinhamento garantido em qualquer browser.
# Sorting é feito manualmente via callback.

def _fmt_taxa(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:.1f}%".replace('.', ',')


def _fmt_pessoas(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{int(v):,}".replace(',', '.')


def _fmt_rendimento(v):
    if v is None or pd.isna(v):
        return "—"
    return f"R$ {v:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')


# Configuração das colunas: id, nome exibido, formatador, tipo de alinhamento
COLUNAS_TABELA = [
    {'id': 'regiao', 'nome': 'Estado', 'fmt': str, 'tipo': 'texto'},
    {'id': 'taxa_desemprego', 'nome': 'Taxa desemp.', 'fmt': _fmt_taxa, 'tipo': 'numero'},
    {'id': 'ocupados', 'nome': 'Ocupados', 'fmt': _fmt_pessoas, 'tipo': 'numero'},
    {'id': 'desocupados', 'nome': 'Desocupados', 'fmt': _fmt_pessoas, 'tipo': 'numero'},
    {'id': 'desalentados', 'nome': 'Desalentados', 'fmt': _fmt_pessoas, 'tipo': 'numero'},
    {'id': 'rendimento_medio', 'nome': 'Rendimento', 'fmt': _fmt_rendimento, 'tipo': 'numero'},
]


def _tabela_estados(trimestre: str = None,
                    sort_col: str = 'taxa_desemprego',
                    sort_dir: str = 'desc'):
    """
    Tabela manual com html.Table - alinhamento garantido em qualquer browser.

    sort_col : qual coluna usar pra ordenar (ex: 'taxa_desemprego')
    sort_dir : 'asc' ou 'desc'
    """
    df = data.pnad_reg_tabela_estados(trimestre_label=trimestre)
    if df.empty:
        return html.Div("Sem dados.", className="aviso-dados")

    # Ordenar
    if sort_col in df.columns:
        if sort_col == 'regiao':
            df = df.sort_values(sort_col, ascending=(sort_dir == 'asc'))
        else:
            df = df.sort_values(sort_col, ascending=(sort_dir == 'asc'),
                                na_position='last')
        df = df.reset_index(drop=True)

    # Cabeçalho - cada th é clicável (callback de sort)
    header_cells = []
    for col in COLUNAS_TABELA:
        # Indicador visual de coluna ordenada
        seta = ''
        if col['id'] == sort_col:
            seta = ' ▾' if sort_dir == 'desc' else ' ▴'
        classes = f"th-{col['tipo']}"
        if col['id'] == sort_col:
            classes += ' th-active'
        header_cells.append(html.Th(
            col['nome'] + seta,
            id={'type': 'th-sort', 'index': col['id']},
            className=classes,
            n_clicks=0,
        ))

    # Linhas
    body_rows = []
    for _, row in df.iterrows():
        is_pe = row['regiao'] == 'Pernambuco'
        cells = []
        for col in COLUNAS_TABELA:
            valor_bruto = row.get(col['id'])
            valor_fmt = col['fmt'](valor_bruto)
            cells.append(html.Td(
                valor_fmt,
                className=f"td-{col['tipo']}",
            ))
        body_rows.append(html.Tr(
            cells,
            className='tr-pe' if is_pe else '',
        ))

    return html.Table(
        className='tabela-estados',
        children=[
            html.Thead(html.Tr(header_cells)),
            html.Tbody(body_rows),
        ],
    )


# ============================================================================
# Layout
# ============================================================================

def layout():
    trimestres = data.pnad_reg_trimestres_disponiveis('Pernambuco')
    trim_default = trimestres[0]

    return html.Div(className="aba-conteudo", children=[

        html.Div(className="aba-titulo-bloco", children=[
            html.Div([
                html.P("Desemprego · PNAD Contínua",
                       className="aba-titulo"),
                html.P("indicadores trimestrais · Pernambuco e estados do Nordeste · 2012-T1 a "
                       + trim_default,
                       className="aba-subtitulo"),
            ]),
        ]),

        # KPIs
        _construir_kpis(),

        # Série histórica
        ui.secao(
            etiqueta="evolução temporal",
            titulo="Taxa de desemprego · 2012—2025",
            descricao="Pernambuco vs Nordeste · trimestres móveis",
            children=_serie_taxa_desemprego(),
        ),

        # Estrutura PEA + Ranking estados
        html.Div(className="grid-duplo grid-1-1", children=[
            ui.secao(
                etiqueta="estrutura da população",
                titulo="",
                descricao="composição da PIA em Pernambuco · escolha o trimestre",
                children=html.Div([
                    html.Div(className="filtros-row", children=[
                        html.Div(className="filtro-item", children=[
                            html.Label("TRIMESTRE", className="filtro-label"),
                            dcc.Dropdown(
                                id='filtro-pea-trimestre',
                                options=_opcoes_trimestres_pea(),
                                value=trim_default,
                                clearable=False,
                                searchable=True,
                                className="filtro-dropdown",
                            ),
                        ]),
                    ]),
                    html.Div(id='donut-pea-container',
                             children=_donut_pea(trim_default)),
                ]),
            ),
            ui.secao(
                etiqueta="comparação regional",
                titulo="",
                descricao="9 estados do Nordeste · escolha indicador e trimestre",
                children=html.Div([
                    html.Div(className="filtros-row", children=[
                        html.Div(className="filtro-item", children=[
                            html.Label("INDICADOR", className="filtro-label"),
                            dcc.Dropdown(
                                id='filtro-rank-ind',
                                options=[
                                    {'label': i['label'], 'value': i['value']}
                                    for i in INDICADORES_RANKING
                                ],
                                value='taxa_desemprego',
                                clearable=False,
                                searchable=False,
                                className="filtro-dropdown",
                            ),
                        ]),
                        html.Div(className="filtro-item", children=[
                            html.Label("TRIMESTRE", className="filtro-label"),
                            dcc.Dropdown(
                                id='filtro-rank-trim',
                                options=_opcoes_trimestres_pea(),
                                value=trim_default,
                                clearable=False,
                                className="filtro-dropdown",
                            ),
                        ]),
                    ]),
                    html.Div(id='ranking-estados-container',
                             children=_ranking_estados('taxa_desemprego',
                                                       trim_default)),
                ]),
            ),
        ]),

        # Linha tripla: Rendimento + Pobreza + Informalidade (todos a partir de 2018)
        html.Div(className="grid-triplo", children=[
            ui.secao(
                etiqueta="rendimento",
                titulo="",
                descricao="rendimento médio mensal · PE vs Nordeste",
                children=_serie_rendimento(),
            ),
            ui.secao(
                etiqueta="pobreza",
                titulo="",
                descricao="população em pobreza e extrema pobreza · PE",
                children=_grafico_pobreza(),
            ),
            ui.secao(
                etiqueta="informalidade",
                titulo="",
                descricao="taxa de informalidade · % sobre ocupados · PE",
                children=_grafico_informalidade_taxa(),
            ),
        ]),

        # Tabela
        ui.secao(
            etiqueta="tabela comparativa",
            titulo="",
            descricao=f"9 estados do Nordeste · todos os indicadores · {trim_default}"
                      f" · clique nos cabeçalhos para ordenar",
            children=html.Div([
                # Store guarda qual coluna e direção de ordenação
                dcc.Store(id='tabela-sort-state',
                          data={'col': 'taxa_desemprego', 'dir': 'desc'}),
                html.Div(id='tabela-estados-container',
                         children=_tabela_estados(trim_default)),
            ]),
        ),

        ui.footer(
            fonte_principal="PNAD Contínua · IBGE",
            atualizacao=trim_default,
        ),
    ])


# ============================================================================
# Callbacks
# ============================================================================

def callbacks(app):

    @app.callback(
        Output('donut-pea-container', 'children'),
        Input('filtro-pea-trimestre', 'value'),
    )
    def atualizar_pea(trimestre):
        if not trimestre:
            return no_update
        return _donut_pea(trimestre=trimestre)

    @app.callback(
        Output('ranking-estados-container', 'children'),
        Input('filtro-rank-ind', 'value'),
        Input('filtro-rank-trim', 'value'),
    )
    def atualizar_ranking(indicador, trimestre):
        if not indicador or not trimestre:
            return no_update
        return _ranking_estados(indicador=indicador, trimestre=trimestre)

    # ----- Sort manual da tabela -----
    # Pattern-matching: cada th tem id {'type': 'th-sort', 'index': col_id}
    # Click → atualiza store → renderiza tabela com nova ordenação.

    from dash import ALL, ctx

    @app.callback(
        Output('tabela-sort-state', 'data'),
        Input({'type': 'th-sort', 'index': ALL}, 'n_clicks'),
        State('tabela-sort-state', 'data'),
        prevent_initial_call=True,
    )
    def atualizar_sort_state(_clicks, atual):
        trigger = ctx.triggered_id
        if not isinstance(trigger, dict):
            return no_update
        col_clicada = trigger.get('index')
        if col_clicada is None:
            return no_update

        # Toggle de direção se clicar na mesma coluna; senão asc por default.
        if atual and atual.get('col') == col_clicada:
            nova_dir = 'asc' if atual.get('dir') == 'desc' else 'desc'
        else:
            nova_dir = 'desc'  # primeiro clique sempre descending
        return {'col': col_clicada, 'dir': nova_dir}

    @app.callback(
        Output('tabela-estados-container', 'children'),
        Input('tabela-sort-state', 'data'),
    )
    def renderizar_tabela_ordenada(state):
        if not state:
            return no_update
        return _tabela_estados(
            trimestre=None,  # último disponível
            sort_col=state.get('col', 'taxa_desemprego'),
            sort_dir=state.get('dir', 'desc'),
        )
