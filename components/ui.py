"""
components/ui.py
================
Componentes de UI reutilizáveis em Dash. Cada função retorna um
componente Dash pronto para ser usado em qualquer aba.

Filosofia: estilo aplicado via classes CSS (assets/style.css), não
inline. Isso mantém o código Python limpo e permite ajustes visuais
globais editando um único arquivo CSS.
"""

from dash import html
from config import PALETTE, SEMANTIC


# ============================================================================
# Helpers de formatação
# ============================================================================

def fmt_num(n, casas=0):
    """Formata número com separadores brasileiros (1.234,56)."""
    if n is None:
        return "—"
    if isinstance(n, float) and casas > 0:
        s = f"{n:,.{casas}f}"
    else:
        s = f"{int(round(n)):,}"
    # Trocar separadores: en (1,234.56) -> pt (1.234,56)
    return s.replace(',', '_').replace('.', ',').replace('_', '.')


def fmt_signed(n):
    """Formata com sinal explícito (+1.234 ou -1.234)."""
    if n is None:
        return "—"
    sinal = '+' if n > 0 else ('−' if n < 0 else '')
    return sinal + fmt_num(abs(n))


def fmt_pct(n, casas=1):
    """Formata percentual (12,3%)."""
    if n is None:
        return "—"
    return f"{n:,.{casas}f}".replace('.', ',') + '%'


def fmt_brl(n):
    """Formata como R$."""
    if n is None:
        return "—"
    return "R$ " + fmt_num(n)


# ============================================================================
# KPI - cartão simples com label, valor e subtítulo opcional
# ============================================================================

def kpi_simples(label, valor, sub=None, accent=None, classe_extra=""):
    """
    KPI básico para uma faixa de KPIs.

    Parâmetros
    ----------
    label : str
        Texto pequeno em uppercase no topo
    valor : str
        Número grande (já formatado)
    sub : str ou (str, str)
        Subtítulo. Se for tupla, o segundo elemento é uma cor (hex ou
        chave semântica como 'positivo', 'negativo').
    accent : str
        Se passado, adiciona uma barrinha lateral colorida (cor da paleta)
    classe_extra : str
        Classes CSS adicionais
    """
    sub_color = PALETTE["cinza_medio"]
    sub_text = ""
    if sub is not None:
        if isinstance(sub, tuple):
            sub_text, cor = sub
            sub_color = SEMANTIC.get(cor, cor)
        else:
            sub_text = sub

    style = {}
    if accent:
        style['borderLeft'] = f"2px solid {accent}"
        style['paddingLeft'] = '14px'

    return html.Div(
        className=f"kpi-simples {classe_extra}",
        style=style,
        children=[
            html.P(label, className="kpi-label"),
            html.P(valor, className="kpi-valor"),
            html.P(sub_text, className="kpi-sub", style={"color": sub_color}),
        ]
    )


# ============================================================================
# Bloco de seção - container com etiqueta + título + corpo
# ============================================================================

def secao(etiqueta, titulo, descricao, children, classe_extra=""):
    """
    Bloco de conteúdo com cabeçalho editorial.

    Estrutura visual:
        ETIQUETA EM UPPERCASE
        Título grande em serifa  (omitido se titulo vazio/None)
        descrição menor em cinza
        --- divisor ---
        [conteúdo]
    """
    header_children = [html.P(etiqueta, className="secao-etiqueta")]
    if titulo:  # só renderiza o título se não estiver vazio
        header_children.append(html.P(titulo, className="secao-titulo"))
    header_children.append(html.P(descricao, className="secao-descricao"))

    return html.Div(
        className=f"secao {classe_extra}",
        children=[
            html.Div(className="secao-header", children=header_children),
            html.Div(className="secao-divisor"),
            html.Div(className="secao-corpo", children=children),
        ]
    )


# ============================================================================
# Header institucional do app
# ============================================================================

def header(titulo, sobretitulo, orgao, atualizado_em):
    """
    Header global do dashboard. Aparece no topo de todas as abas.

    Logo da Secretaria à esquerda, título central editorial,
    bandeira de PE + status à direita.
    """
    return html.Div(
        className="app-header",
        children=[
            # Lado esquerdo: logo + nome do órgão
            html.Div(
                className="header-esq",
                children=[
                    html.Img(src="/assets/logo.jpeg", className="header-logo"),
                ]
            ),
            # Centro: títulos
            html.Div(
                className="header-centro",
                children=[
                    html.P(sobretitulo.upper(), className="header-sobretitulo"),
                    html.H1(titulo, className="header-titulo"),
                ]
            ),
            # Lado direito: status + bandeira de PE
            html.Div(
                className="header-dir",
                children=[
                    html.Div(
                        className="header-status",
                        children=[
                            html.Span(className="status-dot"),
                            html.Span(f"atualizado · {atualizado_em}",
                                     className="status-text"),
                        ]
                    ),
                    html.Div(
                        className="header-marca-pe",
                        children=[
                            html.Img(src="/assets/bandeira_pe.jpg",
                                     className="bandeira-pe",
                                     alt="Bandeira de Pernambuco"),
                        ]
                    ),
                ]
            ),
        ]
    )


# ============================================================================
# Footer
# ============================================================================

def footer(fonte_principal, atualizacao):
    """Rodapé com fonte e ações."""
    return html.Div(
        className="app-footer",
        children=[
            html.Div([
                html.Strong("fonte: ", className="footer-strong"),
                html.Span(fonte_principal),
                html.Span(" · ", className="footer-sep"),
                html.Span(f"extraído em {atualizacao}"),
            ]),
            html.Div(
                className="footer-acoes",
                children=[
                    html.Span("↓ baixar dados", className="footer-acao"),
                    html.Span("ⓘ metodologia", className="footer-acao"),
                ]
            ),
        ]
    )
