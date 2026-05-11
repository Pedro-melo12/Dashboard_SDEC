"""
tabs/indices_socioeconomicos.py
================================
Aba Índices Socioeconômicos - PIB municipal (SEPLAG-PE / IBGE).

Estrutura:
1. KPIs reativos: 5 cards com indicadores estaduais OU municipais
   (alterna ao clicar num município no mapa)
2. Mapa coroplético colorido por PIB. Hover rico mostra município, RD,
   PIB, PIB da RD, % na RD, % no estado.
   - Filtro de ano
   - Click no município = filtra os KPIs
3. Linha dupla: Top 10 municípios + Ranking 12 RDs
4. Linha dupla: Evolução PIB estadual + Crescimento nominal × real (IPCA)
5. Linha dupla: VAB Setorial por RD (4 setores) + Dependência de impostos
   (% impostos / PIB)

Fonte: SEPLAG-PE / IBGE. PIB nominal 2010-2023, impostos e VAB setorial
2010-2021 (Sistema de Contas Nacionais ano-base 2010).
"""

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html, no_update, ALL, ctx

from components import data, ui, charts
from config import PALETTE, SEMANTIC, CHART_FONT


def registrar():
    return {
        'eixo': 'Índices Socioeconômicos',
        'sub': 'PIB municipal',
        'eixo_ordem': 2,
        'sub_ordem': 1,
        'ativa': True,
        'fonte_legenda': 'SEPLAG-PE · IBGE',
    }


# ============================================================================
# Helpers de formatação
# ============================================================================

def _fmt_brl_curto(v):
    """R$ 66 bi / R$ 250 mi / R$ 1,8 mi (compacto)"""
    if v is None or pd.isna(v):
        return "—"
    abs_v = abs(v)
    if abs_v >= 1e9:
        s = f"R$ {v/1e9:.2f} bi"
    elif abs_v >= 1e6:
        s = f"R$ {v/1e6:.1f} mi"
    elif abs_v >= 1e3:
        s = f"R$ {v/1e3:.0f} mil"
    else:
        s = f"R$ {v:.2f}"
    return s.replace('.', ',')


def _fmt_pct(v, casas=1):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:.{casas}f}%".replace('.', ',')


def _ordinal(n):
    """1º, 2º, 3º, 11º..."""
    return f"{n}º"


# ============================================================================
# KPIs - duas variantes (estadual e municipal)
# ============================================================================

def _kpis_estaduais(ano: int):
    """5 KPIs com indicadores do estado todo. Default."""
    k = data.pib_kpis_estaduais(ano)

    cresc_str = None
    if k['crescimento_pct'] is not None:
        seta = '▲' if k['crescimento_pct'] > 0 else '▼' if k['crescimento_pct'] < 0 else '—'
        cor = 'positivo' if k['crescimento_pct'] > 0 else 'negativo'
        cresc_str = (f"{seta} {abs(k['crescimento_pct']):.1f}% nominal vs ano anterior".replace('.', ','), cor)

    return html.Div(className="kpi-faixa kpi-faixa-cinco", children=[
        html.Div(className="kpi-contexto-tag", children="Pernambuco"),
        ui.kpi_simples(
            label=f"PIB · {ano}",
            valor=_fmt_brl_curto(k['pib_total']),
            sub=cresc_str,
            accent=SEMANTIC['destaque'],
        ),
        ui.kpi_simples(
            label="PIB per capita médio",
            valor=_fmt_brl_curto(k['pib_per_capita_medio']),
            sub=("média entre 185 municípios", "neutro"),
        ),
        ui.kpi_simples(
            label="maior PIB municipal",
            valor=k['top_municipio'],
            sub=(f"{_fmt_brl_curto(k['top_municipio_pib'])} "
                 f"({_fmt_pct(k['top_municipio_part'])} do estado)",
                 "neutro"),
        ),
        ui.kpi_simples(
            label="concentração",
            valor=_fmt_pct(k['part_top5_pct']),
            sub=("dos top 5 municípios no PIB", "neutro"),
        ),
        ui.kpi_simples(
            label="municípios cobertos",
            valor="185",
            sub=("Pernambuco + Fernando de Noronha", "neutro"),
        ),
    ])


def _kpis_municipal(cod_ibge_6: int, ano: int):
    """5 KPIs do município selecionado."""
    d = data.pib_municipio_detalhe(cod_ibge_6, ano)
    if d is None:
        return _kpis_estaduais(ano)

    rank_estadual = _ordinal(d['rank_estadual'])
    rank_rd = _ordinal(d['rank_na_rd'])

    return html.Div(className="kpi-faixa kpi-faixa-cinco", children=[
        html.Div(className="kpi-contexto-tag", children=d['municipio']),
        ui.kpi_simples(
            label=f"PIB · {ano}",
            valor=_fmt_brl_curto(d['pib']),
            sub=(f"{rank_estadual} de {d['n_municipios_estado']} no estado", "neutro"),
            accent=SEMANTIC['destaque'],
        ),
        ui.kpi_simples(
            label="PIB per capita",
            valor=_fmt_brl_curto(d['pib_per_capita']),
            sub=(f"RD {d['regiao_desenvolvimento']}", "neutro"),
        ),
        ui.kpi_simples(
            label="participação na RD",
            valor=_fmt_pct(d['part_na_rd']),
            sub=(f"{rank_rd} de {d['n_municipios_rd']} na RD", "neutro"),
        ),
        ui.kpi_simples(
            label="participação no estado",
            valor=_fmt_pct(d['part_no_estado'], 3),
            sub=("do PIB de Pernambuco", "neutro"),
        ),
        ui.kpi_simples(
            label="carga tributária",
            valor=_fmt_pct(d['dependencia_impostos_pct']) if d['dependencia_impostos_pct'] is not None else "—",
            sub=("impostos / PIB municipal"
                 + (" · 2022/23 sem dado" if d['dependencia_impostos_pct'] is None else ""),
                 "neutro"),
        ),
    ])


def _construir_kpis(ano: int, cod_ibge_6: int = None):
    if cod_ibge_6:
        return _kpis_municipal(cod_ibge_6, ano)
    return _kpis_estaduais(ano)


# ============================================================================
# Mapa
# ============================================================================

def _construir_mapa_figura(ano: int):
    df = data.pib_municipal_ano(ano).copy()
    df['regiao_desenvolvimento'] = df['regiao_desenvolvimento'].fillna('—')
    geo = data.geojson_municipios()

    df['_pib_str'] = df['pib'].apply(_fmt_brl_curto)
    df['_pib_rd_str'] = df['pib_rd'].apply(_fmt_brl_curto)
    df['_part_rd'] = df['part_na_rd'].apply(lambda v: _fmt_pct(v, 2))
    df['_part_est'] = df['part_no_estado'].apply(lambda v: _fmt_pct(v, 3))

    hovertemplate = (
        '<b>%{text}</b><br>'
        '<i>RD %{customdata[0]}</i><br>'
        '────────<br>'
        'PIB: %{customdata[1]}<br>'
        'PIB da RD: %{customdata[2]}<br>'
        '%{customdata[3]} do PIB da RD<br>'
        '%{customdata[4]} do PIB do estado'
    )

    fig = charts.mapa_municipios_pe(
        df=df,
        geojson=geo,
        valor_col='pib',
        hovertemplate=hovertemplate,
        customdata_cols=['regiao_desenvolvimento', '_pib_str', '_pib_rd_str',
                         '_part_rd', '_part_est'],
        altura=480,
        titulo_legenda='PIB (R$)',
    )
    return fig


def _construir_mapa(ano: int):
    from config import GEO_MUNICIPIOS
    if not GEO_MUNICIPIOS.exists():
        return html.Div(
            className="aviso-dados",
            style={"padding": "40px", "text-align": "center"},
            children=[
                html.P("ⓘ Mapa indisponível: GeoJSON ainda não foi baixado.",
                       style={"font-size": "13px", "margin-bottom": "8px"}),
                html.Span("Rode no terminal: ", style={"font-size": "12px"}),
                html.Code("python -m etl.geo_etl"),
            ]
        )

    fig = _construir_mapa_figura(ano)
    return dcc.Graph(
        id='mapa-pib',
        figure=fig,
        config={'displayModeBar': False, 'scrollZoom': False},
        clickData=None,
    )


# ============================================================================
# Rankings
# ============================================================================

def _ranking_municipios_pib(ano: int):
    df = data.pib_ranking_municipios(ano, top_n=10)
    fig = charts.barras_ranking(
        df=df, label_col='municipio', valor_col='pib',
        altura=320, top_n=10,
    )
    fig.update_traces(text=df['pib'].apply(_fmt_brl_curto)[::-1])
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


def _ranking_rds_pib(ano: int):
    df = data.pib_ranking_rds(ano)
    fig = charts.barras_ranking(
        df=df, label_col='regiao_desenvolvimento', valor_col='pib',
        altura=320, top_n=12,
    )
    fig.update_traces(text=df.head(12)['pib'].apply(_fmt_brl_curto)[::-1])
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ============================================================================
# Evolução temporal e crescimento nominal × real
# ============================================================================

def _serie_pib_estadual_nominal_e_real():
    """
    Linhas do PIB estadual ao longo do tempo: nominal vs real.

    DEFLACIONADO AO ANO BASE 2010 (não 2023):
    - PIB nominal: cresce rápido (acumula inflação + crescimento real)
    - PIB real (a preços de 2010): cresce devagar (só crescimento real)
    - Em 2010 ambos coincidem (ponto de ancoragem)
    - A área entre as duas linhas = inflação acumulada
    """
    df = data.pib_estadual_nominal_e_real_base2010()
    df['nom_bi'] = df['pib_nominal'] / 1e9
    df['real_bi'] = df['pib_real_base2010'] / 1e9

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['ano'], y=df['nom_bi'],
        mode='lines+markers',
        name='Nominal',
        line=dict(color=SEMANTIC['destaque'], width=2.5),
        marker=dict(size=6, color=SEMANTIC['destaque']),
        fill='tozeroy',
        fillcolor='rgba(91, 123, 154, 0.10)',
        hovertemplate='%{x}<br>nominal: <b>R$ %{y:.1f} bi</b><extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=df['ano'], y=df['real_bi'],
        mode='lines+markers',
        name='Real (a preços de 2010)',
        line=dict(color=PALETTE['terracota'], width=2, dash='dash'),
        marker=dict(size=5, color=PALETTE['terracota']),
        hovertemplate='%{x}<br>real: <b>R$ %{y:.1f} bi</b> (a preços de 2010)<extra></extra>',
    ))

    fig.add_vline(x=2020,
                  line=dict(color=PALETTE["lilas_acinzentado"],
                            width=1, dash='dot'))
    fig.add_annotation(
        x=2020, y=1, yref='paper', text='pandemia',
        showarrow=False,
        font=dict(size=10, color=PALETTE["lilas_acinzentado"]),
        xanchor='left', yanchor='top', xshift=4, yshift=-4,
    )

    charts.aplicar_layout_default(fig,
        height=320,
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom', y=1.02,
            xanchor='right', x=1,
            font=dict(size=10, color=PALETTE['cinza_medio']),
        ),
        margin=dict(l=50, r=20, t=30, b=40),
        xaxis=dict(
            tickmode='linear', dtick=2,
            showgrid=False,
            tickfont=dict(size=10, color=PALETTE['cinza_medio']),
        ),
        yaxis=dict(
            ticksuffix=' bi',
            tickprefix='R$ ',
            showgrid=True,
            gridcolor=PALETTE['cinza_neblina'],
            gridwidth=0.5,
            tickfont=dict(size=10, color=PALETTE['cinza_medio']),
        ),
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


def _crescimento_nominal_e_real():
    """
    Barras agrupadas: crescimento nominal × crescimento real (descontado
    IPCA) ano a ano.
    """
    df = data.pib_crescimento_estadual_real()
    df = df.dropna(subset=['cresc_nominal_pct'])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df['ano'], y=df['cresc_nominal_pct'],
        name='Nominal',
        marker=dict(color=PALETTE['cinza_claro']),
        text=df['cresc_nominal_pct'].apply(
            lambda v: ('+' if v > 0 else '') + f"{v:.0f}%".replace('.', ',')),
        textposition='outside',
        textfont=dict(size=9, color=PALETTE['cinza_medio']),
        cliponaxis=False,
        hovertemplate='%{x}<br>nominal: <b>%{y:.2f}%</b><extra></extra>',
    ))
    cores_real = [
        SEMANTIC['destaque'] if v >= 0 else PALETTE['terracota']
        for v in df['cresc_real_pct']
    ]
    fig.add_trace(go.Bar(
        x=df['ano'], y=df['cresc_real_pct'],
        name='Real (descontado IPCA)',
        marker=dict(color=cores_real),
        text=df['cresc_real_pct'].apply(
            lambda v: ('+' if v > 0 else '') + f"{v:.1f}%".replace('.', ',')),
        textposition='outside',
        textfont=dict(size=9, color=PALETTE['grafite']),
        cliponaxis=False,
        hovertemplate='%{x}<br>real: <b>%{y:.2f}%</b><extra></extra>',
    ))

    fig.add_hline(y=0, line=dict(color=PALETTE['cinza_claro'], width=0.5))

    charts.aplicar_layout_default(fig,
        height=320,
        showlegend=True,
        barmode='group',
        bargap=0.25,
        bargroupgap=0.05,
        legend=dict(
            orientation='h',
            yanchor='bottom', y=1.02,
            xanchor='right', x=1,
            font=dict(size=10, color=PALETTE['cinza_medio']),
        ),
        margin=dict(l=40, r=20, t=30, b=40),
        xaxis=dict(
            tickmode='linear', dtick=1,
            showgrid=False,
            tickfont=dict(size=10, color=PALETTE['cinza_medio']),
        ),
        yaxis=dict(
            ticksuffix='%',
            showgrid=True,
            gridcolor=PALETTE['cinza_neblina'],
            gridwidth=0.5,
            tickfont=dict(size=10, color=PALETTE['cinza_medio']),
            range=[
                min(df['cresc_real_pct'].min() * 1.3, -8),
                max(df['cresc_nominal_pct'].max() * 1.25, 18),
            ],
        ),
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# ============================================================================
# VAB Setorial - composição por RD
# ============================================================================

# Mapeamento de chaves técnicas para nomes legíveis
SETOR_NOMES = {
    'agropecuaria': 'Agropecuária',
    'industria': 'Indústria',
    'servicos': 'Serviços',
    'apu': 'Adm. pública',
}
SETOR_CORES = {
    'agropecuaria': PALETTE['verde_salvia'],
    'industria': SEMANTIC['destaque'],
    'servicos': PALETTE['mostarda_suave'],
    'apu': PALETTE['lilas_acinzentado'],
}


def _construir_vab_setorial(rd_nome: str, ano: int):
    """
    Para uma RD escolhida, mostra:
    1. Composição setorial da RD inteira em donut (4 setores, R$ absoluto)
    2. Ranking de TODOS os municípios da RD por VAB total

    SOLUÇÃO DEFINITIVA: dois dcc.Graph separados em flex container CSS.
    Cada gráfico tem sua própria área dedicada — sem possibilidade de
    sobreposição entre labels do donut e do ranking.
    """
    composicao = data.vab_absoluto_por_rd(rd_nome, ano)
    if composicao.empty:
        return html.Div("Sem dados para esta RD/ano.", className="aviso-dados")

    vab_rd = float(composicao['vab'].sum())

    # =========== Donut (gráfico 1, isolado) ===========
    ordem = ['agropecuaria', 'industria', 'servicos', 'apu']
    composicao_ord = composicao.set_index('setor').reindex(ordem).reset_index()
    cores_ord = [SETOR_CORES[s] for s in ordem]
    labels = [SETOR_NOMES[s] for s in ordem]

    fig_donut = go.Figure(go.Pie(
        labels=labels,
        values=composicao_ord['vab'],
        hole=0.55,
        marker=dict(colors=cores_ord, line=dict(color=PALETTE['branco'], width=2)),
        textposition='outside',
        textinfo='label+percent',
        textfont=dict(size=11, color=PALETTE['grafite']),
        hovertemplate='<b>%{label}</b><br>R$ %{value:,.0f}<br>%{percent}<extra></extra>',
        sort=False,
        showlegend=False,
    ))
    # Texto no centro do donut
    fig_donut.add_annotation(
        x=0.5, y=0.5, xref='paper', yref='paper',
        text=f"<b>{_fmt_brl_curto(vab_rd)}</b><br>"
             f"<span style='font-size:10px;color:#7A7A7A'>"
             f"VAB total · {ano}</span>",
        showarrow=False,
        xanchor='center', yanchor='middle',
        font=dict(size=14, color=PALETTE['preto_titulo']),
    )
    charts.aplicar_layout_default(fig_donut,
        height=360,
        showlegend=False,
        margin=dict(l=30, r=30, t=20, b=20),
    )

    # =========== Barras (gráfico 2, isolado) ===========
    df_vab = data.vab_setorial_absoluto()
    sub = df_vab[(df_vab['regiao_desenvolvimento'] == rd_nome)
                  & (df_vab['ano'] == ano)]
    rank = sub.groupby(['cod_ibge_6', 'municipio'], as_index=False)['vab'].sum()
    rank = rank.sort_values('vab', ascending=True)
    n_munis = len(rank)
    altura_barras = max(360, 30 * n_munis + 60)

    # Como o gráfico está em container isolado, o eixo Y tem total liberdade
    # para reservar espaço aos nomes — sem invasão de outro subplot.
    fig_barras = go.Figure(go.Bar(
        x=rank['vab'],
        y=rank['municipio'],
        orientation='h',
        marker=dict(color=SEMANTIC['destaque']),
        text=rank['vab'].apply(_fmt_brl_curto),
        textposition='outside',
        textfont=dict(size=10, color=PALETTE['grafite']),
        cliponaxis=False,
        hovertemplate='<b>%{y}</b><br>VAB: %{x:,.0f}<extra></extra>',
        showlegend=False,
    ))
    fig_barras.update_xaxes(visible=False, range=[0, rank['vab'].max() * 1.30])
    fig_barras.update_yaxes(
        showgrid=False,
        tickfont=dict(size=11, color=PALETTE['grafite']),
        ticks='', showline=False,
        automargin=True,  # Plotly aloca espaço suficiente automaticamente
    )
    charts.aplicar_layout_default(fig_barras,
        height=altura_barras,
        showlegend=False,
        margin=dict(l=10, r=40, t=20, b=20),
    )

    # =========== Container flex com 2 gráficos lado a lado ===========
    return html.Div(
        className="vab-setorial-grid",
        children=[
            html.Div(
                className="vab-donut-wrap",
                children=dcc.Graph(
                    figure=fig_donut,
                    config={'displayModeBar': False},
                ),
            ),
            html.Div(
                className="vab-barras-wrap",
                children=dcc.Graph(
                    figure=fig_barras,
                    config={'displayModeBar': False},
                ),
            ),
        ],
    )


# ============================================================================
# Carga tributária - % impostos no PIB
# ============================================================================
# Antes "dependência de impostos", renomeado pois o termo causava confusão.
# Este indicador mostra a parcela do PIB municipal que é gerada por
# arrecadação de IMPOSTOS SOBRE PRODUTOS (ICMS principalmente, mais IPI e
# ISS de transações). Não é dependência de transferências (FPM/FPE) - isso
# virá em outra aba quando os dados forem fornecidos.
#
# Por isso polos industriais (Goiana, Cabo, Ipojuca) lideram: têm muita
# arrecadação local de ICMS. Municípios pequenos rurais ficam em baixo
# porque produzem pouco e consomem pouco em transações tributáveis.

def _construir_carga_tributaria(ano: int, rd_nome: str = None):
    """
    Ranking de municípios pela carga tributária sobre produtos.
    Se rd_nome estiver definido, mostra apenas municípios dessa RD
    (todos, não top 10).

    Se ano não tem dados (2022/23), mostra aviso explicativo.
    """
    df = data.carga_tributaria_municipios(ano=ano, rd_nome=rd_nome)

    if df.empty:
        return html.Div([
            html.P(f"Sem dados de impostos para {ano}.",
                   style={'margin-bottom': '8px',
                          'font-weight': '500',
                          'color': PALETTE['grafite']}),
            html.P("O IBGE atrasou a divulgação dos dados de VAB e Impostos "
                   "por causa da mudança de ano-base do Sistema de Contas "
                   "Nacionais (Nota Técnica 02/2024). Até 2021 está coberto.",
                   style={'font-size': '11px',
                          'color': PALETTE['cinza_medio'],
                          'margin': '0'}),
        ], className="aviso-dados",
           style={'padding': '40px 30px', 'text-align': 'left'})

    # Se filtrou por RD: mostra todos os municípios da RD ordenados.
    # Se não, mostra top 10 do estado.
    if rd_nome:
        df_plot = df.copy()  # todos da RD
        altura = max(280, 30 * len(df_plot) + 40)
    else:
        df_plot = df.head(10)
        altura = 320

    fig = charts.barras_ranking(
        df=df_plot,
        label_col='municipio',
        valor_col='dependencia_impostos_pct',
        altura=altura,
        top_n=len(df_plot),
    )
    fig.update_traces(
        text=df_plot['dependencia_impostos_pct'].apply(
            lambda v: _fmt_pct(v, 1))[::-1],
    )
    return dcc.Graph(figure=fig, config={'displayModeBar': False})


# Mantém alias para compatibilidade com callbacks antigos (se houver)
_construir_dependencia_impostos = _construir_carga_tributaria


# ============================================================================
# Layout
# ============================================================================

def layout():
    ano_default = data.pib_ultimo_ano()
    anos_disponiveis = data.pib_anos_disponiveis()
    primeiro_ano = anos_disponiveis[-1]

    # Anos com VAB setorial e impostos (até 2021)
    anos_vab = data.vab_setorial_anos_disponiveis()
    ano_vab_default = anos_vab[0] if anos_vab else 2021
    rds = data.lista_rds()

    return html.Div(className="aba-conteudo", children=[

        html.Div(className="aba-titulo-bloco", children=[
            html.Div([
                html.P("Índices Socioeconômicos",
                       className="aba-titulo"),
                html.P(f"PIB municipal · 185 municípios em 12 RDs · "
                       f"{primeiro_ano}—{ano_default}",
                       className="aba-subtitulo"),
            ]),
            html.Div(className="aba-acoes", children=[
                html.Span("clique em um município no mapa para filtrar os KPIs",
                         className="aba-dica"),
                html.Button("limpar seleção", id="btn-limpar-pib",
                           className="btn-link hidden"),
            ]),
        ]),

        # Store que guarda o município selecionado
        dcc.Store(id='pib-municipio-selecionado', data=None),

        # KPIs reativos
        html.Div(id='pib-kpis', children=_kpis_estaduais(ano_default)),

        # Mapa com filtro de ano
        ui.secao(
            etiqueta="geografia do PIB",
            titulo="",
            descricao=f"default: {ano_default} · "
                      f"clique em um município para filtrar os KPIs · "
                      f"hover mostra participação no PIB da RD e do estado",
            children=html.Div([
                html.Div(className="filtros-row", children=[
                    html.Div(className="filtro-item", children=[
                        html.Label("ANO:", className="filtro-label"),
                        dcc.Dropdown(
                            id='filtro-pib-ano',
                            options=[{'label': str(a), 'value': a}
                                     for a in anos_disponiveis],
                            value=ano_default,
                            clearable=False,
                            searchable=False,
                            className="filtro-dropdown",
                        ),
                    ]),
                ]),
                _construir_mapa(ano_default),
            ]),
        ),

        # Linha dupla: rankings
        html.Div(className="grid-duplo grid-1-1", children=[
            ui.secao(
                etiqueta="ranking municipal",
                titulo="",
                descricao=f"top 10 municípios por PIB · {ano_default}",
                children=html.Div(id='ranking-pib-mun-container',
                                  children=_ranking_municipios_pib(ano_default)),
            ),
            ui.secao(
                etiqueta="ranking regional",
                titulo="",
                descricao=f"PIB total por RD · {ano_default}",
                children=html.Div(id='ranking-pib-rd-container',
                                  children=_ranking_rds_pib(ano_default)),
            ),
        ]),

        # Linha dupla: evolução temporal nominal × real + crescimento ano a ano
        html.Div(className="grid-duplo grid-1-1", children=[
            ui.secao(
                etiqueta="evolução temporal",
                titulo="",
                descricao=f"PIB estadual nominal (linha azul) e real "
                          f"a preços de 2010 (linha vermelha tracejada) · {primeiro_ano}—{ano_default}",
                children=_serie_pib_estadual_nominal_e_real(),
            ),
            ui.secao(
                etiqueta="crescimento anual",
                titulo="",
                descricao="taxa nominal × real · descontada inflação (IPCA-IBGE)",
                children=_crescimento_nominal_e_real(),
            ),
        ]),

        # Linha dupla: VAB setorial por RD + dependência impostos
        html.Div(className="grid-duplo grid-1-1", children=[
            ui.secao(
                etiqueta="composição setorial",
                titulo="",
                descricao=f"composição do VAB da RD em 4 setores + "
                          f"ranking dos municípios por VAB total · valores absolutos",
                children=html.Div([
                    html.Div(className="filtros-row", children=[
                        html.Div(className="filtro-item", children=[
                            html.Label("RD:", className="filtro-label"),
                            dcc.Dropdown(
                                id='filtro-vab-rd',
                                options=[{'label': r, 'value': r} for r in rds],
                                value='Metropolitana',
                                clearable=False,
                                searchable=True,
                                className="filtro-dropdown",
                            ),
                        ]),
                        html.Div(className="filtro-item", children=[
                            html.Label("ANO:", className="filtro-label"),
                            dcc.Dropdown(
                                id='filtro-vab-ano',
                                options=[{'label': str(a), 'value': a}
                                         for a in anos_vab],
                                value=ano_vab_default,
                                clearable=False,
                                searchable=False,
                                className="filtro-dropdown",
                            ),
                        ]),
                    ]),
                    html.Div(id='vab-setorial-container',
                             children=_construir_vab_setorial(
                                 'Metropolitana', ano_vab_default)),
                ]),
            ),
            ui.secao(
                etiqueta="carga tributária sobre produtos",
                titulo="",
                descricao=f"% de impostos no PIB municipal · "
                          f"indica concentração de arrecadação local "
                          f"(ICMS, IPI, ISS sobre transações)",
                children=html.Div([
                    html.Div(className="filtros-row", children=[
                        html.Div(className="filtro-item", children=[
                            html.Label("ANO:", className="filtro-label"),
                            dcc.Dropdown(
                                id='filtro-imp-ano',
                                options=[{'label': str(a), 'value': a}
                                         for a in anos_vab],
                                value=ano_vab_default,
                                clearable=False,
                                searchable=False,
                                className="filtro-dropdown",
                            ),
                        ]),
                        html.Div(className="filtro-item", children=[
                            html.Label("RD:", className="filtro-label"),
                            dcc.Dropdown(
                                id='filtro-imp-rd',
                                options=([{'label': 'Todas (top 10 do estado)',
                                           'value': '__todas__'}]
                                         + [{'label': r, 'value': r} for r in rds]),
                                value='__todas__',
                                clearable=False,
                                searchable=True,
                                className="filtro-dropdown",
                            ),
                        ]),
                    ]),
                    html.Div(id='dep-impostos-container',
                             children=_construir_carga_tributaria(
                                 ano_vab_default)),
                ]),
            ),
        ]),

        ui.footer(
            fonte_principal="SEPLAG-PE / IBGE · Sistema de Contas Regionais · "
                          "IPCA: IBGE",
            atualizacao=str(ano_default),
        ),
    ])


# ============================================================================
# Callbacks
# ============================================================================

def callbacks(app):

    # Quando muda ano, atualiza os 4 elementos não-municipais (mas KPIs
    # podem estar mostrando município, então tratamos separadamente)
    @app.callback(
        Output('mapa-pib', 'figure'),
        Output('ranking-pib-mun-container', 'children'),
        Output('ranking-pib-rd-container', 'children'),
        Input('filtro-pib-ano', 'value'),
    )
    def atualizar_pib_ano(ano):
        if not ano:
            return [no_update] * 3
        return (
            _construir_mapa_figura(ano),
            _ranking_municipios_pib(ano),
            _ranking_rds_pib(ano),
        )

    # Click no mapa: salva o cod_ibge_6 selecionado (toggle se for o mesmo)
    @app.callback(
        Output('pib-municipio-selecionado', 'data'),
        Input('mapa-pib', 'clickData'),
        Input('btn-limpar-pib', 'n_clicks'),
        State('pib-municipio-selecionado', 'data'),
        prevent_initial_call=True,
    )
    def gerenciar_selecao(click_data, n_limpar, atual):
        trigger = ctx.triggered_id
        if trigger == 'btn-limpar-pib':
            return None
        if trigger == 'mapa-pib' and click_data:
            cod = click_data['points'][0].get('location')
            if cod is None:
                return no_update
            try:
                cod = int(str(cod).strip())
            except (TypeError, ValueError):
                return no_update
            if atual == cod:
                return None
            return cod
        return no_update

    # Atualiza KPIs com base em (ano, município selecionado)
    @app.callback(
        Output('pib-kpis', 'children'),
        Input('filtro-pib-ano', 'value'),
        Input('pib-municipio-selecionado', 'data'),
    )
    def atualizar_kpis(ano, cod):
        if not ano:
            return no_update
        return _construir_kpis(ano, cod_ibge_6=cod)

    # Mostra/esconde botão de limpar
    @app.callback(
        Output('btn-limpar-pib', 'className'),
        Input('pib-municipio-selecionado', 'data'),
    )
    def toggle_btn(cod):
        return 'btn-link' if cod else 'btn-link hidden'

    # VAB setorial - reage à mudança de RD ou ano
    @app.callback(
        Output('vab-setorial-container', 'children'),
        Input('filtro-vab-rd', 'value'),
        Input('filtro-vab-ano', 'value'),
    )
    def atualizar_vab(rd, ano):
        if not rd or not ano:
            return no_update
        return _construir_vab_setorial(rd, ano)

    # Carga tributária - reage à mudança de ano OU de RD
    @app.callback(
        Output('dep-impostos-container', 'children'),
        Input('filtro-imp-ano', 'value'),
        Input('filtro-imp-rd', 'value'),
    )
    def atualizar_dep(ano, rd):
        if not ano:
            return no_update
        rd_filtro = None if rd == '__todas__' else rd
        return _construir_carga_tributaria(ano, rd_nome=rd_filtro)
