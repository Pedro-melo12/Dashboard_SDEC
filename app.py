"""
app.py
======
Aplicação principal do Observatório Econômico de Pernambuco.

Este arquivo é deliberadamente curto. A maior parte do trabalho está em:
- config.py (paleta, caminhos, metadados)
- components/ (UI e gráficos reutilizáveis)
- tabs/ (cada arquivo é uma aba auto-registrada)

Para rodar:
    python app.py

Depois abra http://127.0.0.1:8050 no navegador.

Para adicionar novas abas, copie tabs/_template.py e implemente.
A aba aparece sozinha no menu.
"""

from datetime import datetime

from dash import Dash, Input, Output, dcc, html

import tabs
from tabs import home as tab_home
from components import data, ui
from config import META

# ============================================================================
# Inicialização do app
# ============================================================================

app = Dash(
    __name__,
    title=f"{META['titulo']} · Observatório Econômico",
    update_title=None,  # remove o "Updating..." do title bar
    suppress_callback_exceptions=True,
)

# Necessário para deploy em produção (gunicorn, render, etc)
server = app.server


# ============================================================================
# Descobre as abas dinamicamente
# ============================================================================
# Esta lista é construída em tempo de inicialização lendo a pasta tabs/.
# Para adicionar uma aba nova, basta criar o arquivo - este código não muda.

EIXOS = tabs.listar_eixos()
ABAS_TODAS = tabs.descobrir_abas()

# ABAS sem a Home - usado para navegação real do dashboard.
# A Home é uma aba especial: tem layout estático no DOM e nunca aparece
# na lista de abas "reais".
ABAS = [a for a in ABAS_TODAS if a['eixo'] != '__home__']


# ============================================================================
# Componente de navegação (eixos + sub-abas)
# ============================================================================

def construir_nav_eixos(eixo_ativo: str):
    """Constrói a barra superior de eixos."""
    # "Home" é o primeiro item — clicável, leva à capa
    home_ativo = eixo_ativo == '__home__'
    items = [html.A(
        "Home",
        id={'type': 'nav-eixo', 'index': '__home__'},
        n_clicks=0,
        className=f"nav-eixo nav-home {'ativo' if home_ativo else ''}",
    )]

    for eixo in EIXOS:
        # Pular eixo interno __home__ (não aparece no loop)
        if eixo['nome'] == '__home__':
            continue
        ativo = eixo['nome'] == eixo_ativo
        items.append(html.A(
            eixo['nome'],
            id={'type': 'nav-eixo', 'index': eixo['nome']},
            n_clicks=0,
            className=f"nav-eixo {'ativo' if ativo else ''}",
        ))

    return html.Nav(className="nav-eixos", children=items)


def construir_nav_subs(eixo_ativo: str, sub_ativa: str):
    """Constrói os chips de sub-abas para o eixo ativo."""
    subs = [a for a in ABAS if a['eixo'] == eixo_ativo]

    items = []
    for sub in subs:
        ativa = sub['sub'] == sub_ativa
        fonte = sub.get('fonte_legenda', '')
        items.append(html.A(
            children=[
                sub['sub'],
                html.Span(fonte, className="nav-sub-fonte") if fonte else "",
            ],
            id={'type': 'nav-sub', 'index': sub['id']},
            n_clicks=0,
            className=f"nav-sub {'ativo' if ativa else ''}",
        ))

    return html.Div(className="nav-subs", children=items)


# ============================================================================
# Layout principal
# ============================================================================

def construir_layout():
    """Layout estático do app. As mudanças de aba acontecem via callback."""
    # Home é sempre a aba inicial
    aba_inicial_id = '__home__'
    eixo_inicial = '__home__'

    # Data de atualização: pega a última data do CAGED
    try:
        ultima = data.caged_municipal()['data'].max()
        atualizado_em = ultima.strftime("%b · %Y").lower()
    except Exception:
        atualizado_em = "—"

    return html.Div(className="app-shell", children=[
        # Header global
        ui.header(
            titulo=META['titulo'],
            sobretitulo=META['sobretitulo'],
            orgao=META['orgao'],
            atualizado_em=atualizado_em,
        ),

        # Navegação - dois níveis (oculta na Home)
        html.Div(
            id='nav-container',
            style={'display': 'none'},  # oculto inicial (estamos na Home)
            children=[
                construir_nav_eixos(eixo_inicial),
                construir_nav_subs(eixo_inicial, ''),
            ]
        ),

        # Store guarda qual aba está ativa
        dcc.Store(id='aba-ativa', data=aba_inicial_id),

        # Location (URL) para compatibilidade
        dcc.Location(id='url', refresh=False),

        # HOME estática no layout — sempre presente no DOM
        # Visibilidade controlada por display
        html.Div(
            id='home-container',
            children=tab_home.layout(),
        ),

        # Container do conteúdo das outras abas (oculto na Home)
        html.Div(
            id='conteudo-aba',
            style={'display': 'none'},
        ),
    ])


app.layout = construir_layout


# ============================================================================
# Callbacks de navegação
# ============================================================================
# Um único callback gerencia toda a navegação. Responde a:
# - Clique em qualquer eixo (barra superior)
# - Clique em qualquer sub-aba (chips)
# - Carga inicial (renderiza a primeira aba)

from dash import ALL, ctx


@app.callback(
    Output('aba-ativa', 'data'),
    Output('nav-container', 'children'),
    Output('nav-container', 'style'),
    Output('home-container', 'style'),
    Output('conteudo-aba', 'children'),
    Output('conteudo-aba', 'style'),
    Input({'type': 'nav-sub', 'index': ALL}, 'n_clicks'),
    Input({'type': 'nav-eixo', 'index': ALL}, 'n_clicks'),
    Input('btn-entrar', 'n_clicks'),
    prevent_initial_call=True,
)
def navegar(_clicks_subs, _clicks_eixos, _click_entrar):
    """
    Gerencia transições entre Home e abas.

    Estado inicial (definido no layout):
    - home-container: display=block (visível)
    - nav-container: display=none (oculto)
    - conteudo-aba: display=none (oculto, vazio)

    Transições:
    - btn-entrar → mostra primeira aba (Mercado de Trabalho)
    - nav-eixo __home__ → volta pra Home
    - outros nav-eixo → mostra primeira sub-aba desse eixo
    - nav-sub X → mostra sub-aba X
    """
    from dash import no_update
    triggered = ctx.triggered_id

    STYLE_VISIVEL = {'display': 'block'}
    STYLE_OCULTO = {'display': 'none'}

    # Botão "Acessar o Observatório" da Home
    if triggered == 'btn-entrar':
        aba = ABAS[0]
        nav = [construir_nav_eixos(aba['eixo']),
               construir_nav_subs(aba['eixo'], aba['sub'])]
        return (aba['id'], nav,
                STYLE_VISIVEL,  # nav visível
                STYLE_OCULTO,   # home oculta
                aba['module'].layout(),
                STYLE_VISIVEL)  # conteudo visível

    if isinstance(triggered, dict):
        if triggered.get('type') == 'nav-eixo':
            eixo_clicado = triggered['index']
            if eixo_clicado == '__home__':
                # Voltar para Home — sem re-renderizar nada
                return (no_update, no_update,
                        STYLE_OCULTO,  # nav oculto
                        STYLE_VISIVEL, # home visível
                        no_update,
                        STYLE_OCULTO)  # conteudo oculto
            primeiras = [a for a in ABAS if a['eixo'] == eixo_clicado]
            if not primeiras:
                return [no_update] * 6
            aba_id = primeiras[0]['id']
        elif triggered.get('type') == 'nav-sub':
            aba_id = triggered['index']
        else:
            return [no_update] * 6
    else:
        return [no_update] * 6

    aba = tabs.aba_por_id(aba_id)
    if aba is None:
        return [no_update] * 6

    nav = [construir_nav_eixos(aba['eixo']),
           construir_nav_subs(aba['eixo'], aba['sub'])]

    return (aba['id'], nav,
            STYLE_VISIVEL,
            STYLE_OCULTO,
            aba['module'].layout(),
            STYLE_VISIVEL)


# ============================================================================
# Registrar callbacks de cada aba
# ============================================================================

for aba in ABAS:
    if hasattr(aba['module'], 'callbacks'):
        aba['module'].callbacks(app)


# ============================================================================
# Run
# ============================================================================

if __name__ == '__main__':
    import os

    # DEBUG controlável via variável de ambiente.
    # Em desenvolvimento: `DASH_DEBUG=1 python app.py` ativa o devtools.
    # Em produção (default): roda sem o painel de debug.
    debug = os.environ.get('DASH_DEBUG', '0') == '1'

    print()
    print("=" * 60)
    print(f"  {META['titulo']} · Observatório Econômico")
    print(f"  {META['orgao']}")
    print("=" * 60)
    print(f"  Abas registradas: {len(ABAS)}")
    for aba in ABAS:
        print(f"    · {aba['eixo']} > {aba['sub']}")
    print()
    print("  Servidor: http://127.0.0.1:8050")
    print(f"  Debug: {'ON' if debug else 'OFF'}"
          f"{' (DASH_DEBUG=1 para ativar)' if not debug else ''}")
    print("  (Ctrl+C para parar)")
    print("=" * 60)
    print()

    #app.run(debug=debug, host='127.0.0.1', port=8050)
    app.run(debug=debug, host='0.0.0.0', port=int(os.environ.get("PORT", 8050)))