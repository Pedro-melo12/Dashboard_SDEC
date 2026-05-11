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
ABAS = tabs.descobrir_abas()


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

        # Navegação - dois níveis
        html.Div(id='nav-container', children=[
            construir_nav_eixos(eixo_inicial),
            construir_nav_subs(eixo_inicial, ''),
        ]),

        # Store guarda qual aba está ativa
        dcc.Store(id='aba-ativa', data=aba_inicial_id),

        # Location (URL) para compatibilidade
        dcc.Location(id='url', refresh=False),

        # Container do conteúdo da aba
        html.Div(id='conteudo-aba'),
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
from tabs import home as tab_home


@app.callback(
    Output('aba-ativa', 'data'),
    Output('nav-container', 'children'),
    Output('conteudo-aba', 'children'),
    Input({'type': 'nav-sub', 'index': ALL}, 'n_clicks'),
    Input({'type': 'nav-eixo', 'index': ALL}, 'n_clicks'),
    Input('url', 'pathname'),
    Input('aba-ativa', 'data'),
)
def navegar(_clicks_subs, _clicks_eixos, pathname, aba_id_atual):
    triggered = ctx.triggered_id

    # URL /entrar — botão "Acessar" da capa Home (via href)
    if triggered == 'url' and pathname == '/entrar':
        aba_id = ABAS[0]['id']
    elif isinstance(triggered, dict):
        if triggered.get('type') == 'nav-sub':
            aba_id = triggered['index']
        elif triggered.get('type') == 'nav-eixo':
            eixo_clicado = triggered['index']
            if eixo_clicado == '__home__':
                aba_id = '__home__'
            else:
                primeiras = [a for a in ABAS if a['eixo'] == eixo_clicado]
                aba_id = primeiras[0]['id'] if primeiras else aba_id_atual
        else:
            aba_id = aba_id_atual
    else:
        aba_id = aba_id_atual

    # Renderizar Home
    if aba_id == '__home__':
        nav = [
            construir_nav_eixos('__home__'),
            construir_nav_subs('__home__', ''),
        ]
        return '__home__', nav, tab_home.layout()

    # Renderizar aba normal
    aba = tabs.aba_por_id(aba_id)
    if aba is None:
        aba = ABAS[0]
        aba_id = aba['id']

    nav = [
        construir_nav_eixos(aba['eixo']),
        construir_nav_subs(aba['eixo'], aba['sub']),
    ]
    conteudo = aba['module'].layout()

    return aba_id, nav, conteudo


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
    print("  Servidor: http://0.0.0.0:8050")
    print(f"  Debug: {'ON' if debug else 'OFF'}"
          f"{' (DASH_DEBUG=1 para ativar)' if not debug else ''}")
    print("  (Ctrl+C para parar)")
    print("=" * 60)
    print()

    app.run(debug=debug, host='0.0.0.0', port=int(os.environ.get("PORT", 8050)))
