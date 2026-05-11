"""
tabs/atividade_economica.py
============================
Aba Atividade Econômica - placeholder.

Aguarda dados sobre setores produtivos, indústria, agropecuária e
serviços em Pernambuco. Exibe mensagem indicativa enquanto isso.
"""

from dash import html
from components import ui


def registrar():
    return {
        'eixo': 'Atividade Econômica',
        'sub': 'Visão geral',
        'eixo_ordem': 4,
        'sub_ordem': 1,
        'ativa': True,
        'fonte_legenda': 'Aguardando dados',
    }


def layout():
    return html.Div(className="aba-conteudo", children=[

        html.Div(className="aba-titulo-bloco", children=[
            html.Div([
                html.P("Atividade Econômica",
                       className="aba-titulo"),
                html.P("indicadores de produção · indústria · agropecuária · serviços",
                       className="aba-subtitulo"),
            ]),
        ]),

        ui.secao(
            etiqueta="status",
            titulo="",
            descricao="aba em construção",
            children=html.Div(
                className="aviso-pendente",
                children=[
                    html.P([
                        "Esta aba foi criada e está aguardando os dados a serem ",
                        "carregados. Quando disponíveis, vamos ", html.Strong(
                            "construir gráficos, charts e tabelas"),
                        " com filtros, no mesmo padrão das demais abas.",
                    ]),
                    html.P([
                        "Os dados poderão incluir: produção industrial mensal, ",
                        "valor adicionado bruto por setor, produção agrícola por ",
                        "cultura, balança comercial setorial, indicadores de ",
                        "competitividade e outros.",
                    ]),
                ]
            ),
        ),

        ui.footer(
            fonte_principal="aguardando dados",
            atualizacao="—",
        ),
    ])


def callbacks(app):
    pass
