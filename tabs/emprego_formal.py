"""
tabs/emprego_formal.py
======================
Aba Emprego Formal (CAGED).

Núcleo da experiência interativa do dashboard. Tem:
- Faixa de 5 KPIs no topo
- Mapa de PE coroplético (saldo acumulado 12m por município)
- Série temporal por gênero
- Ranking dos top-N municípios

Interatividade:
    Clicando num município no mapa, os gráficos da página são filtrados
    para aquele município. Clicando de novo no mesmo, o filtro é
    removido (volta a mostrar dados estaduais).
"""

import pandas as pd
from dash import Input, Output, State, dcc, html, no_update

from components import data, ui, charts
from components.ui import fmt_num, fmt_pct, fmt_signed
from config import PALETTE, SEMANTIC


def registrar():
    return {
        'eixo': 'Mercado de trabalho',
        'sub': 'Emprego formal',
        'eixo_ordem': 1,
        'sub_ordem': 1,
        'ativa': True,
        'fonte_legenda': 'Novo CAGED · MTE/SE',
    }


# ============================================================================
# KPIs - construção dinâmica
# ============================================================================

def _construir_kpis(municipio_filtrado: int = None):
    """
    Constrói a faixa de KPIs.
    Se municipio_filtrado for passado, mostra dados desse município.
    Caso contrário, dados do estado.
    """
    if municipio_filtrado:
        df_full = data.caged_municipal()
        df_mun = df_full[df_full['cod_ibge_6'] == municipio_filtrado]
        if df_mun.empty:
            return html.Div("Município não encontrado.")

        nome_mun = df_mun['municipio'].iloc[0]
        ultima_data = df_mun['data'].max()
        mes_atual = df_mun[df_mun['data'] == ultima_data].iloc[0]
        saldo = int(mes_atual['saldo'])
        adm = int(mes_atual['admissoes'])
        desl = int(mes_atual['desligamentos'])

        # Saldo do mês anterior
        mes_ant_data = ultima_data - pd.DateOffset(months=1)
        mes_ant_df = df_mun[df_mun['data'] == mes_ant_data]
        saldo_ant = int(mes_ant_df['saldo'].iloc[0]) if not mes_ant_df.empty else None

        # Saldo 12m
        inicio_12m = ultima_data - pd.DateOffset(months=11)
        janela = df_mun[(df_mun['data'] >= inicio_12m) & (df_mun['data'] <= ultima_data)]
        saldo_12m = int(janela['saldo'].sum())

        contexto_label = nome_mun
    else:
        ultimos = data.caged_total_estadual_mes()
        saldo = ultimos['saldo']
        adm = ultimos['admissoes']
        desl = ultimos['desligamentos']
        saldo_ant = ultimos['saldo_mes_anterior']
        ultima_data = ultimos['data']

        # Acumulado 12m estadual
        df_serie = data.caged_serie_estadual_mensal()
        inicio_12m = ultima_data - pd.DateOffset(months=11)
        janela = df_serie[(df_serie['data'] >= inicio_12m) &
                          (df_serie['data'] <= ultima_data)]
        saldo_12m = int(janela['saldo'].sum())

        contexto_label = "Pernambuco"

    # Variação do saldo no mês
    sub_saldo = None
    if saldo_ant is not None and saldo_ant != 0:
        var_pct = (saldo - saldo_ant) / abs(saldo_ant) * 100
        seta = '▲' if var_pct > 0 else '▼' if var_pct < 0 else '—'
        sub_saldo = (f"{seta} {abs(var_pct):.1f}% vs mês anterior",
                     'positivo' if var_pct > 0 else 'negativo')

    mes_str = ultima_data.strftime('%b/%Y').lower()
    ano_str = ultima_data.strftime('%Y')

    # Municípios com saldo positivo (só faz sentido para visão estadual)
    if not municipio_filtrado:
        positivos = data.caged_municipios_com_saldo_positivo()
        kpi_municipios = ui.kpi_simples(
            label="municípios em alta",
            valor=html.Span([
                f"{positivos['positivos']}",
                html.Span(f" /{positivos['total']}",
                         className="kpi-valor-secundario")
            ]),
            sub=f"com saldo positivo em {mes_str}",
        )
    else:
        # Para um município, mostramos a posição no ranking
        ranking = data.caged_saldo_acumulado_12m()
        ranking = ranking.reset_index()
        pos_row = ranking[ranking['cod_ibge_6'] == municipio_filtrado]
        posicao = int(pos_row['index'].iloc[0]) + 1 if not pos_row.empty else None
        kpi_municipios = ui.kpi_simples(
            label="posição no ranking",
            valor=html.Span([
                f"{posicao}º",
                html.Span(" /185", className="kpi-valor-secundario")
            ]) if posicao else "—",
            sub="por saldo acumulado 12m",
        )

    return html.Div(className="kpi-faixa kpi-faixa-cinco", children=[
        html.Div(className="kpi-contexto-tag", children=contexto_label),
        ui.kpi_simples(
            label=f"saldo · {mes_str}",
            valor=fmt_signed(saldo),
            sub=sub_saldo,
            accent=SEMANTIC['destaque'],
        ),
        ui.kpi_simples(
            label="admissões",
            valor=fmt_num(adm),
            sub=f"no mês de referência",
        ),
        ui.kpi_simples(
            label="desligamentos",
            valor=fmt_num(desl),
            sub=f"no mês de referência",
        ),
        ui.kpi_simples(
            label="saldo · 12 meses",
            valor=fmt_signed(saldo_12m),
            sub=("acumulado positivo", 'positivo') if saldo_12m > 0
                else ("acumulado negativo", 'negativo'),
        ),
        kpi_municipios,
    ])


# ============================================================================
# Mapa
# ============================================================================

def _construir_mapa_figura(anos: list, meses: list):
    """
    Constrói a figura Plotly do mapa filtrada por anos/meses.
    Retorna apenas a figure - o componente Graph é separado pra que o
    callback possa atualizar só a figura sem perder o registro do
    clickData (que é usado para filtrar a página por município).
    """
    df = data.caged_municipal_filtrado(anos=anos, meses=meses)
    geo = data.geojson_municipios()

    # Escala: divergente se houver valores negativos no período
    tem_negativos = (df['saldo'] < 0).any()

    # Label legível pro hover/legenda baseada no período selecionado
    if anos and len(anos) == 1 and meses and len(meses) == 1:
        unidade = f"saldo · {_MESES_PT[meses[0]-1].lower()}/{anos[0]}"
    elif anos and len(anos) == 1 and not meses:
        unidade = f"saldo · {anos[0]}"
    elif anos and not meses:
        unidade = f"saldo · {len(anos)} anos"
    elif meses and not anos:
        unidade = f"saldo · {len(meses)} meses"
    elif anos and meses:
        unidade = f"saldo · período filtrado"
    else:
        unidade = "saldo · todo o período"

    fig = charts.mapa_pe(
        df=df,
        geojson=geo,
        valor_col='saldo',
        label_col='municipio',
        cod_col='cod_ibge_6',
        divergente=tem_negativos,
        altura=460,
        unidade=unidade,
    )
    return fig


def _construir_mapa():
    """
    Componente inicial do mapa. Default: último mês disponível.
    O id='mapa-pe' é usado pelo callback de clique (filtro por município)
    e o callback de filtros (que atualiza a 'figure').
    """
    # Fallback gracioso quando o GeoJSON ainda não foi baixado
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

    ano_default, mes_default = _ultimo_ano_mes()
    fig = _construir_mapa_figura(anos=[ano_default], meses=[mes_default])

    return dcc.Graph(
        id='mapa-pe',
        figure=fig,
        config={'displayModeBar': False, 'scrollZoom': False},
        clickData=None,
    )


# ============================================================================
# Gênero - Donut Charts (mês de referência + acumulado no ano)
# ============================================================================

def _donut_genero_mes(periodo_str: str = None):
    """
    Donut: composição masc/fem do saldo no MÊS escolhido.

    Parâmetros
    ----------
    periodo_str : "YYYY-MM" (ex: "2025-07"). Se None, usa o último
                  período disponível na base.
    """
    df_gen = data.caged_genero()
    if not periodo_str:
        # Default: último mês disponível
        ultima = df_gen['data'].max()
        ano, mes = int(ultima.year), int(ultima.month)
    else:
        ano_str, mes_str = periodo_str.split('-')
        ano, mes = int(ano_str), int(mes_str)

    target = pd.Timestamp(year=ano, month=mes, day=1)
    mes_df = df_gen[df_gen['data'] == target]
    masc = int(mes_df[mes_df['sexo'] == 'Masculino']['saldo'].sum())
    fem = int(mes_df[mes_df['sexo'] == 'Feminino']['saldo'].sum())
    total = masc + fem

    total_fmt = ('+' if total >= 0 else '−') + \
                f"{abs(total):,}".replace(',', '.')
    mes_label = f"{_MESES_PT[mes-1].lower()}/{ano}"

    fig = charts.donut_dois(
        label_a='Masculino', valor_a=masc,
        label_b='Feminino', valor_b=fem,
        total_centro=f"<b>{total_fmt}</b><br><span style='font-size:10px;color:#7A7A7A'>"
                     f"saldo · {mes_label}</span>",
        altura=220,
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


def _donut_genero_ano():
    """
    Donut: saldo ACUMULADO no último ano disponível na base.

    Quando o usuário atualizar a base com 2026, esta função
    automaticamente passará a mostrar 2026 sem nenhuma alteração de
    código (lê o ano dinamicamente de caged_genero_acumulado_ano()).
    """
    info = data.caged_genero_acumulado_ano()  # sem arg = último ano
    total_str = ('+' if info['total'] >= 0 else '−') + \
                f"{abs(info['total']):,}".replace(',', '.')

    fig = charts.donut_dois(
        label_a='Masculino', valor_a=info['masculino'],
        label_b='Feminino', valor_b=info['feminino'],
        total_centro=f"<b>{total_str}</b><br><span style='font-size:10px;color:#7A7A7A'>"
                     f"acumulado · {info['ano']}</span>",
        altura=220,
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


def _opcoes_mes_ano():
    """
    Lista de períodos mensais disponíveis (mais recente primeiro),
    formato {'label': 'Jul/2025', 'value': '2025-07'}.
    """
    df_gen = data.caged_genero()
    datas = sorted(df_gen['data'].unique(), reverse=True)
    opcoes = []
    for d in datas:
        d = pd.Timestamp(d)
        opcoes.append({
            'label': f"{_MESES_PT[d.month-1]}/{d.year}",
            'value': f"{d.year}-{d.month:02d}",
        })
    return opcoes


def _ultimo_periodo_mensal_str() -> str:
    """Retorna 'YYYY-MM' do último mês disponível em caged_genero."""
    d = pd.Timestamp(data.caged_genero()['data'].max())
    return f"{d.year}-{d.month:02d}"


# ============================================================================
# Ranking municipal (Top 5 e Bottom 5, com filtros de ano e mês)
# ============================================================================

def _ranking_municipios_topbottom(anos: list, meses: list):
    """
    Constrói os DOIS gráficos (top 5 e bottom 5) lado a lado, baseado
    nos anos e meses selecionados nos filtros.
    """
    df = data.caged_municipal_filtrado(anos=anos, meses=meses)

    if df.empty:
        return html.Div("Sem dados para o período selecionado.",
                        className="aviso-dados")

    top5 = df.head(5)
    # Para o bottom: queremos o MAIS NEGATIVO no TOPO (pior em primeiro,
    # ranking de "piores"). df está ordenado descendente; tail(5) traz os
    # 5 menores na ordem [-40, -44, -88, -89, -106]. Como o Plotly desenha
    # barras horizontais de baixo pra cima, passar essa ordem com
    # pre_sorted=True faz -106 (mais negativo, pior) ficar no topo.
    bottom5 = df.tail(5)

    fig_top = charts.barras_ranking(
        df=top5, label_col='municipio', valor_col='saldo',
        altura=180, top_n=5,
    )
    fig_bot = charts.barras_ranking(
        df=bottom5, label_col='municipio', valor_col='saldo',
        altura=180, top_n=5,
        pre_sorted=True,  # mais negativo no topo, menos negativo embaixo
    )
    return html.Div(className="ranking-duplo", children=[
        html.Div(className="ranking-bloco", children=[
            html.P("TOP 5 · maiores saldos", className="ranking-label"),
            dcc.Graph(figure=fig_top, config={'displayModeBar': False}),
        ]),
        html.Div(className="ranking-bloco", children=[
            html.P("BOTTOM 5 · menores saldos", className="ranking-label"),
            dcc.Graph(figure=fig_bot, config={'displayModeBar': False}),
        ]),
    ])


# ============================================================================
# Setores - 5 grandes setores (com filtros de ano e mês)
# ============================================================================

def _setor_ranking_filtrado(anos: list, meses: list):
    """Ranking de setores baseado nos filtros."""
    df = data.caged_setor_filtrado(anos=anos, meses=meses)
    if df.empty:
        return html.Div("Sem dados para o período selecionado.",
                        className="aviso-dados")
    fig = charts.barras_ranking(
        df=df, label_col='setor', valor_col='saldo',
        altura=240, top_n=5,
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


def _setor_serie():
    """Série temporal por setor (média móvel 3m para suavizar)."""
    df = data.caged_setor_serie_temporal(janela_meses=3)

    cores = {
        'Serviços': SEMANTIC['destaque'],
        'Comércio': PALETTE['azul_empoeirado'],
        'Indústria': PALETTE['verde_salvia'],
        'Construção': PALETTE['mostarda_suave'],
        'Agropecuária': PALETTE['terracota'],
    }

    fig = charts.linha_multipla(
        df=df, x='data', y='saldo_mm', grupo='setor',
        cores=cores,
        altura=240,
        formato_y=',.0f',
    )
    fig.add_vline(x=pd.Timestamp('2020-03-01'),
                  line=dict(color=PALETTE["lilas_acinzentado"], width=1, dash='dot'))
    fig.add_annotation(
        x=pd.Timestamp('2020-03-01'), y=1, yref='paper', text='pandemia',
        showarrow=False,
        font=dict(size=10, color=PALETTE["lilas_acinzentado"]),
        xanchor='left', yanchor='top', xshift=4, yshift=-4,
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ============================================================================
# Helpers de filtro - opções dos dropdowns
# ============================================================================

# Anos disponíveis na base (computado uma vez)
def _opcoes_anos():
    df = data.caged_municipal()
    anos = sorted(df['ano'].unique().tolist(), reverse=True)
    return [{'label': str(a), 'value': int(a)} for a in anos]


_MESES_PT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
             'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


def _opcoes_meses():
    return [{'label': _MESES_PT[m-1], 'value': m} for m in range(1, 13)]


def _ultimo_ano_mes():
    """Retorna (ano, mes) da última data disponível no CAGED municipal."""
    df = data.caged_municipal()
    ultima = df['data'].max()
    return int(ultima.year), int(ultima.month)


def _filtros_periodo(prefixo: str, default_anos: list, default_meses: list):
    """
    Constrói os 2 dropdowns de filtro (ano + mês) com prefixo no ID.
    Usado tanto no setor quanto no ranking municipal.
    """
    return html.Div(className="filtros-row", children=[
        html.Div(className="filtro-item", children=[
            html.Label("ano(s):", className="filtro-label"),
            dcc.Dropdown(
                id=f'{prefixo}-ano',
                options=_opcoes_anos(),
                value=default_anos,
                multi=True,
                placeholder="todos",
                className="filtro-dropdown",
            ),
        ]),
        html.Div(className="filtro-item", children=[
            html.Label("mês(es):", className="filtro-label"),
            dcc.Dropdown(
                id=f'{prefixo}-mes',
                options=_opcoes_meses(),
                value=default_meses,
                multi=True,
                placeholder="todos",
                className="filtro-dropdown",
            ),
        ]),
    ])


# ============================================================================
# Layout completo da aba
# ============================================================================

def layout():
    ano_default, mes_default = _ultimo_ano_mes()

    return html.Div(className="aba-conteudo", children=[

        html.Div(className="aba-titulo-bloco", children=[
            html.Div([
                html.P("Emprego formal · CAGED",
                       className="aba-titulo"),
                html.P("saldo, admissões e desligamentos · 185 municípios · 2020-2025",
                       className="aba-subtitulo"),
            ]),
            html.Div(className="aba-acoes", children=[
                html.Span("clique em um município no mapa para filtrar",
                         className="aba-dica"),
                html.Button("limpar filtro", id="btn-limpar-filtro",
                           className="btn-link hidden"),
            ]),
        ]),

        # Store guarda o município filtrado entre callbacks
        dcc.Store(id='municipio-filtrado', data=None),

        # Container dos KPIs - será atualizado por callback
        html.Div(id='kpis-emprego', children=_construir_kpis()),

        # Mapa em linha cheia - com filtros de período
        ui.secao(
            etiqueta="geografia do emprego formal",
            titulo="",  # apagado a pedido - só etiqueta + descrição
            descricao=f"default: {_MESES_PT[mes_default-1].lower()}/{ano_default}"
                      f" · clique em um município para filtrar a página",
            children=html.Div([
                _filtros_periodo(
                    prefixo='filtro-mapa',
                    default_anos=[ano_default],
                    default_meses=[mes_default],
                ),
                _construir_mapa(),
            ]),
        ),

        # Linha 1: Donuts de gênero + Ranking Top/Bottom municipal
        html.Div(className="grid-duplo grid-1-1", children=[
            ui.secao(
                etiqueta="composição por gênero",
                titulo="",  # apagado a pedido
                descricao="saldo de empregos formais por sexo",
                children=html.Div([
                    # Cabeçalho com filtro do donut esquerdo + label do direito
                    html.Div(className="duplo-donut-header", children=[
                        html.Div(className="donut-cabecalho", children=[
                            html.Label("MÊS DE REFERÊNCIA",
                                       className="donut-titulo-mini"),
                            dcc.Dropdown(
                                id='filtro-donut-mes',
                                options=_opcoes_mes_ano(),
                                value=_ultimo_periodo_mensal_str(),
                                clearable=False,
                                searchable=False,
                                className="filtro-dropdown filtro-donut",
                            ),
                        ]),
                        html.Div(className="donut-cabecalho", children=[
                            html.Label("ACUMULADO NO ANO",
                                       className="donut-titulo-mini"),
                            html.P(
                                f"{data.caged_genero()['data'].max().year}",
                                className="donut-info-ano",
                            ),
                        ]),
                    ]),
                    # Donuts em si
                    html.Div(className="duplo-donut", children=[
                        html.Div(id='donut-mes-container',
                                 children=_donut_genero_mes()),
                        _donut_genero_ano(),
                    ]),
                ]),
            ),
            ui.secao(
                etiqueta="ranking municipal",
                titulo="Maiores e menores saldos",
                descricao=f"default: {_MESES_PT[mes_default-1].lower()}/{ano_default}"
                          f" · ajuste o período abaixo",
                children=html.Div([
                    _filtros_periodo(
                        prefixo='filtro-mun',
                        default_anos=[ano_default],
                        default_meses=[mes_default],
                    ),
                    html.Div(id='ranking-municipal-container',
                             children=_ranking_municipios_topbottom(
                                 anos=[ano_default],
                                 meses=[mes_default])),
                ]),
            ),
        ]),

        # Linha 2: Setores - ranking com filtros + série temporal
        html.Div(className="grid-duplo grid-1-1", children=[
            ui.secao(
                etiqueta="setores · CNAE",
                titulo="Saldo por grande setor",
                descricao=f"default: ano {ano_default} acumulado"
                          f" · ajuste o período abaixo",
                children=html.Div([
                    _filtros_periodo(
                        prefixo='filtro-setor',
                        default_anos=[ano_default],
                        default_meses=[],  # ano todo
                    ),
                    html.Div(id='setor-ranking-container',
                             children=_setor_ranking_filtrado(
                                 anos=[ano_default], meses=[])),
                ]),
            ),
            ui.secao(
                etiqueta="evolução por setor",
                titulo="Saldo mensal por setor",
                descricao="média móvel de 3 meses · 2020—2025",
                children=_setor_serie(),
            ),
        ]),

        ui.footer(
            fonte_principal="Novo CAGED · MTE/SE",
            atualizacao=data.caged_municipal()['data'].max().strftime("%b/%Y").lower(),
        ),
    ])


# ============================================================================
# Callbacks - reatividade do mapa
# ============================================================================

def callbacks(app):
    """
    Registra a interatividade do mapa e dos filtros de período.

    Fluxos:
    1. Mapa: clique no município -> store -> KPIs
    2. Filtros do ranking municipal: ano/mês -> recalcula top/bottom
    3. Filtros do setor: ano/mês -> recalcula ranking de setores
    """

    @app.callback(
        Output('municipio-filtrado', 'data'),
        Input('mapa-pe', 'clickData'),
        Input('btn-limpar-filtro', 'n_clicks'),
        State('municipio-filtrado', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_filtro(click_data, n_clicks_limpar, atual):
        from dash import ctx
        trigger = ctx.triggered_id

        if trigger == 'btn-limpar-filtro':
            return None

        if trigger == 'mapa-pe' and click_data:
            cod = click_data['points'][0].get('location')
            if cod is None:
                return no_update
            # cod_ibge_6 vem como string ("260005"); normalizamos pra int
            # pra casar com a coluna do DataFrame que é int64.
            try:
                cod = int(str(cod).strip())
            except (TypeError, ValueError):
                return no_update
            # Toggle: clique no mesmo município = limpa filtro
            if atual == cod:
                return None
            return cod

        return no_update

    @app.callback(
        Output('kpis-emprego', 'children'),
        Input('municipio-filtrado', 'data'),
    )
    def atualizar_kpis(municipio):
        return _construir_kpis(municipio)

    @app.callback(
        Output('btn-limpar-filtro', 'className'),
        Input('municipio-filtrado', 'data'),
    )
    def toggle_btn_limpar(municipio):
        if municipio:
            return 'btn-link'
        return 'btn-link hidden'

    # ----- Filtro do donut do mês de gênero -----
    @app.callback(
        Output('donut-mes-container', 'children'),
        Input('filtro-donut-mes', 'value'),
    )
    def atualizar_donut_mes(periodo):
        return _donut_genero_mes(periodo_str=periodo)

    # ----- Filtros do mapa (atualiza a figure, mantém o clickData) -----
    @app.callback(
        Output('mapa-pe', 'figure'),
        Input('filtro-mapa-ano', 'value'),
        Input('filtro-mapa-mes', 'value'),
    )
    def atualizar_mapa(anos, meses):
        anos = anos or []
        meses = meses or []
        return _construir_mapa_figura(anos=anos, meses=meses)

    # ----- Filtros do ranking municipal (Top 5 / Bottom 5) -----
    @app.callback(
        Output('ranking-municipal-container', 'children'),
        Input('filtro-mun-ano', 'value'),
        Input('filtro-mun-mes', 'value'),
    )
    def atualizar_ranking_municipal(anos, meses):
        # Normalizar None para lista vazia
        anos = anos or []
        meses = meses or []
        return _ranking_municipios_topbottom(anos=anos, meses=meses)

    # ----- Filtros do ranking de setores -----
    @app.callback(
        Output('setor-ranking-container', 'children'),
        Input('filtro-setor-ano', 'value'),
        Input('filtro-setor-mes', 'value'),
    )
    def atualizar_ranking_setor(anos, meses):
        anos = anos or []
        meses = meses or []
        return _setor_ranking_filtrado(anos=anos, meses=meses)
