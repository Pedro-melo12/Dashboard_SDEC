"""
tabs/home.py
============
Capa do Observatório Econômico de Pernambuco.

Esta aba é a primeira a ser exibida ao abrir o dashboard.
Layout estático e elegante com identidade visual do projeto.
"""

from dash import html, dcc
from config import PALETTE


def registrar():
    return {
        'eixo': '__home__',
        'sub': '',
        'eixo_ordem': 0,
        'sub_ordem': 0,
        'ativa': True,
        'fonte_legenda': '',
    }


def layout():
    return html.Div(
        className="home-capa",
        children=[

            # Faixa decorativa superior
            html.Div(className="home-faixa-top"),

            # Conteúdo central
            html.Div(className="home-centro", children=[

                # Textos principais
                html.Div(className="home-textos", children=[
                    html.H1("Observatório Econômico",
                            className="home-titulo"),
                    html.H2("de Pernambuco",
                            className="home-subtitulo"),
                    html.P(
                        "Dados e indicadores econômicos dos 185 municípios "
                        "pernambucanos. Emprego formal, desemprego, PIB, "
                        "gestão pública e muito mais.",
                        className="home-descricao",
                    ),
                ]),

                # Botão para entrar — html.Button no layout estático
                # garante que o callback funcione sem instabilidade
                html.Div(className="home-acoes", children=[
                    html.Button(
                        "Acessar o Observatório →",
                        id="btn-entrar",
                        n_clicks=0,
                        className="home-btn-entrar",
                    ),
                ]),

                # Chips dos eixos disponíveis
                html.Div(className="home-eixos-chips", children=[
                    html.Span("Mercado de trabalho", className="home-chip"),
                    html.Span("Índices Socioeconômicos", className="home-chip"),
                    html.Span("Gestão Pública", className="home-chip"),
                    html.Span("Atividade Econômica", className="home-chip"),
                    html.Span("Comércio Exterior", className="home-chip"),
                ]),
            ]),

            # Rodapé da capa
            html.Div(className="home-rodape", children=[
                html.Span(
                    "Pernambuco em dados · SDEC · Governo do Estado",
                    className="home-rodape-texto",
                ),
                html.Span("2025", className="home-rodape-ano"),
            ]),

            # Faixa decorativa inferior (listras das cores de PE)
            html.Div(className="home-faixas-pe", children=[
                html.Div(className="home-faixa-verde"),
                html.Div(className="home-faixa-amarela"),
                html.Div(className="home-faixa-vermelha"),
            ]),
        ],
    )


def callbacks(app):
    """O botão 'Entrar' está conectado no app.py principal."""
    pass
