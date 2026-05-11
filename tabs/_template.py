"""
tabs/_template.py
=================
Template para criar uma nova aba no observatório.

Como usar:
1. Copie este arquivo: cp tabs/_template.py tabs/minha_aba.py
2. Renomeie a função registrar para refletir sua aba
3. Preencha as 3 funções: registrar, layout, callbacks
4. Ao iniciar o app, sua aba aparece no menu automaticamente

Não modifique este arquivo - ele serve como referência.
"""

from dash import html


def registrar():
    """
    Configuração da aba.
    Tem que devolver dict com pelo menos: eixo, sub, eixo_ordem, sub_ordem.
    """
    return {
        'eixo': 'Mercado de trabalho',     # eixo principal (navegação top)
        'sub': 'Nome da sub-aba',           # sub-aba (chips abaixo do eixo)
        'eixo_ordem': 1,                    # ordem do eixo (menor = primeiro)
        'sub_ordem': 99,                    # ordem dentro do eixo
        'ativa': True,                      # se False, aparece desabilitada
    }


def layout():
    """
    Retorna o componente Dash que será o conteúdo da aba.
    Chamado uma vez na inicialização. Para conteúdo que depende do
    estado, use callbacks.
    """
    return html.Div([
        html.P("Conteúdo da aba aqui."),
    ])


def callbacks(app):
    """
    Registra os callbacks da aba.
    Recebe a instância do app para poder usar @app.callback.
    Pode ser uma função vazia se a aba é estática.
    """
    pass
