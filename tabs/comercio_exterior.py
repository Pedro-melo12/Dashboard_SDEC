"""
tabs/comercio_exterior.py
==========================
Aba Comércio Exterior - placeholder.

Aguarda dados sobre exportações, importações e balança comercial de
Pernambuco. Exibe mensagem indicativa enquanto isso.
"""

from dash import html
from components import ui


def registrar():
    return {
        'eixo': 'Comércio Exterior',
        'sub': 'Visão geral',
        'eixo_ordem': 5,
        'sub_ordem': 1,
        'ativa': True,
        'fonte_legenda': 'Aguardando dados',
    }


def layout():
    return html.Div(className="aba-conteudo", children=[

        html.Div(className="aba-titulo-bloco", children=[
            html.Div([
                html.P("Comércio Exterior",
                       className="aba-titulo"),
                html.P("exportações · importações · balança comercial",
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
                        "Esta aba foi criada e está aguardando os dados a ",
                        "serem carregados. Quando disponíveis, teremos gráficos, ",
                        "charts e tabelas com filtros, no mesmo padrão das ",
                        "demais abas.",
                    ]),
                    html.P([
                        "Os dados poderão incluir: pauta de exportação por ",
                        "produto, principais países parceiros, evolução mensal ",
                        "do volume e do valor, balança comercial por setor, ",
                        "comparação com outros estados do Nordeste e outros.",
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
