
import pandas as pd
import plotly.graph_objects as go

from config import (
    PALETTE, SEMANTIC, CHART_LAYOUT_DEFAULTS,
    CHART_FONT, CHART_FONT_SERIF,
    MAPA_ESCALA_POSITIVA, MAPA_ESCALA_DIVERGENTE,
)


def aplicar_layout_default(fig: go.Figure, **overrides) -> go.Figure:
    """Aplica os defaults de layout. Aceita overrides via kwargs."""
    fig.update_layout(**CHART_LAYOUT_DEFAULTS)
    if overrides:
        fig.update_layout(**overrides)
    return fig


# ============================================================================
# Linha temporal
# ============================================================================

def linha_temporal(df: pd.DataFrame, x: str, y: str,
                   cor: str = None,
                   nome: str = "",
                   altura: int = 280,
                   anotacao: tuple = None,
                   y_titulo: str = "",
                   formato_y: str = "") -> go.Figure:
    """
    Gráfico de linha temporal simples com área sombreada sob a linha.

    Parâmetros
    ----------
    df : DataFrame com as colunas x e y
    x, y : nomes das colunas
    cor : cor da linha (default: azul ardósia)
    nome : nome da série (mostrado no hover)
    altura : altura em pixels
    anotacao : tupla (data_x, texto) para marcação vertical (ex: pandemia)
    formato_y : prefixo/sufixo do eixo Y. Ex: ',.0f' para milhares
    """
    cor = cor or SEMANTIC["destaque"]

    fig = go.Figure()

    # Linha principal
    fig.add_trace(go.Scatter(
        x=df[x], y=df[y],
        mode='lines',
        name=nome,
        line=dict(color=cor, width=2),
        fill='tozeroy',
        fillcolor=_hex_alpha(cor, 0.08),
        hovertemplate='%{x|%b/%Y}<br><b>%{y:,.0f}</b><extra></extra>',
    ))

    aplicar_layout_default(fig,
        height=altura,
        showlegend=False,
        yaxis=dict(
            **CHART_LAYOUT_DEFAULTS['yaxis'],
            title=dict(text=y_titulo, font=dict(size=10)),
            tickformat=formato_y,
        ),
    )

    # Anotação vertical (ex: marco da pandemia)
    if anotacao:
        x_anot, texto = anotacao
        fig.add_vline(
            x=x_anot,
            line=dict(color=PALETTE["lilas_acinzentado"], width=1, dash='dot'),
        )
        fig.add_annotation(
            x=x_anot, y=1, yref='paper',
            text=texto,
            showarrow=False,
            font=dict(size=10, color=PALETTE["lilas_acinzentado"], style='italic'),
            xanchor='left', yanchor='top', xshift=4, yshift=-4,
        )

    return fig


# ============================================================================
# Linha múltipla 
# ============================================================================

def linha_multipla(df: pd.DataFrame, x: str, y: str, grupo: str,
                   cores: dict = None,
                   altura: int = 280,
                   anotacao: tuple = None,
                   formato_y: str = "") -> go.Figure:
    """
    Várias séries (uma linha por valor único da coluna `grupo`).

    Parâmetros
    ----------
    cores : dict {valor_do_grupo: cor_hex}. Se não passado, usa default.
    """
    if cores is None:
        # Cores default para até 4 séries
        cores_default = [
            SEMANTIC["destaque"],
            PALETTE["terracota"],
            PALETTE["verde_salvia"],
            PALETTE["lilas_acinzentado"],
        ]
        valores = df[grupo].unique()
        cores = {v: cores_default[i % len(cores_default)]
                 for i, v in enumerate(valores)}

    fig = go.Figure()
    for valor, cor in cores.items():
        sub = df[df[grupo] == valor].sort_values(x)
        # A primeira série é sólida; as demais, tracejadas (leitura clara)
        is_primary = list(cores.keys()).index(valor) == 0
        fig.add_trace(go.Scatter(
            x=sub[x], y=sub[y],
            mode='lines',
            name=str(valor),
            line=dict(
                color=cor,
                width=2,
                dash='solid' if is_primary else 'dash',
            ),
            hovertemplate=f'<b>{valor}</b><br>%{{x|%b/%Y}}<br>%{{y:,.0f}}<extra></extra>',
        ))

    aplicar_layout_default(fig,
        height=altura,
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom', y=1.02,
            xanchor='right', x=1,
            font=dict(size=10, color=PALETTE["cinza_medio"]),
        ),
        margin=dict(l=40, r=20, t=30, b=40),
        yaxis=dict(
            **CHART_LAYOUT_DEFAULTS['yaxis'],
            tickformat=formato_y,
        ),
    )

    if anotacao:
        x_anot, texto = anotacao
        fig.add_vline(x=x_anot,
            line=dict(color=PALETTE["lilas_acinzentado"], width=1, dash='dot'))
        fig.add_annotation(
            x=x_anot, y=1, yref='paper', text=texto,
            showarrow=False,
            font=dict(size=10, color=PALETTE["lilas_acinzentado"]),
            xanchor='left', yanchor='top', xshift=4, yshift=-4,
        )

    return fig


# ============================================================================
# Ranking (barras horizontais)
# ============================================================================

def barras_ranking(df: pd.DataFrame, label_col: str, valor_col: str,
                   altura: int = 320, top_n: int = 8,
                   pre_sorted: bool = False) -> go.Figure:
    """
    Barras horizontais ordenadas (maior em cima por padrão).
    Usado para ranking de municípios, setores, etc.

    Lida bem com valores negativos: o eixo X é estendido em ambos os
    lados pra dar espaço pro texto, e o sinal é mostrado de forma
    consistente.

    pre_sorted : se True, NÃO faz sort interno - usa a ordem do DataFrame
        recebido tal como está. Útil para "bottom rankings" onde queremos
        o pior valor no topo (ordem específica que o caller já aplicou).
    """
    df = df.head(top_n).copy()
    if not pre_sorted:
        # Default: sort ascendente para que Plotly (que desenha bottom-up)
        # mostre maior valor no topo.
        df = df.sort_values(valor_col)

    # Cor: positivo em azul (mais escuro pros maiores), negativo em terracota
    cores = []
    n = len(df)
    valores_pos = df[df[valor_col] >= 0][valor_col].tolist()
    valores_pos_sorted = sorted(valores_pos, reverse=True)
    for v in df[valor_col]:
        if v < 0:
            cores.append(PALETTE["terracota"])
        else:
            # Posição entre os positivos (top 2 = destaque, demais = suave)
            pos_idx = valores_pos_sorted.index(v) if v in valores_pos_sorted else 99
            if pos_idx < 2:
                cores.append(SEMANTIC["destaque"])
            elif pos_idx < 5:
                cores.append(SEMANTIC["destaque_suave"])
            else:
                cores.append(PALETTE["bege_quente"])

    # Formato do texto com sinal negativo bonito (− em vez de -)
    def _fmt(v):
        s = f"{abs(int(v)):,}".replace(',', '.')
        return ('−' + s) if v < 0 else s

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df[valor_col],
        y=df[label_col],
        orientation='h',
        marker=dict(color=cores),
        text=df[valor_col].apply(_fmt),
        textposition='outside',
        textfont=dict(size=11, color=PALETTE["grafite"]),
        cliponaxis=False,
        hovertemplate='<b>%{y}</b><br>%{x:,.0f}<extra></extra>',
    ))

    # Range do X: estende em ambos os lados pra dar espaço pro texto
    max_val = df[valor_col].max()
    min_val = df[valor_col].min()
    if min_val < 0:
        # Folga proporcional ao maior valor absoluto
        max_abs = max(abs(min_val), abs(max_val))
        x_range = [min_val - max_abs * 0.20, max(max_val, 0) + max_abs * 0.20]
    else:
        x_range = [0, max_val * 1.20]

    aplicar_layout_default(fig,
        height=altura,
        showlegend=False,
        margin=dict(l=10, r=20, t=10, b=20),
        xaxis=dict(visible=False, range=x_range),
        yaxis=dict(
            showgrid=False,
            tickfont=dict(size=11, color=PALETTE["grafite"]),
            ticks='',
            showline=False,
        ),
    )

    return fig


# ============================================================================
# Mapa coroplético de PE
# ============================================================================

def mapa_municipios_pe(df: pd.DataFrame, geojson: dict,
                       valor_col: str,
                       hovertemplate: str,
                       customdata_cols: list = None,
                       label_col: str = 'municipio',
                       cod_col: str = 'cod_ibge_6',
                       cor_escala=None,
                       divergente: bool = False,
                       altura: int = 480,
                       titulo_legenda: str = '',
                       zmin: float = None,
                       zmax: float = None,
                       discreto: bool = False,
                       legenda_visivel: bool = True) -> go.Figure:
    
    df = df.copy()
    df[cod_col] = df[cod_col].astype(str)

    for f in geojson.get('features', []):
        props = f.get('properties', {})
        if 'cod_ibge_6' in props:
            props['cod_ibge_6'] = str(props['cod_ibge_6'])

    if discreto:
        # Modo categórico: cada valor único recebe uma cor diferente
        categorias = sorted(df[valor_col].dropna().unique().tolist())
        # Paleta de 12 cores qualitativas (suficiente para 12 RDs)
        paleta_cat = [
            "#5B7B9A",  # azul ardósia
            "#9B7E5C",  # bege quente
            "#C99383",  # terracota
            "#7E9E84",  # verde sálvia
            "#B0A584",  # bege oliva
            "#A29CC4",  # lilás acinzentado
            "#D4B86A",  # mostarda
            "#8C9DAB",  # azul empoeirado
            "#C4937A",  # rosé
            "#7A8E7E",  # verde mais escuro
            "#A87B7B",  # marrom rosado
            "#6B8AA0",  # azul médio
        ]
        cat_to_idx = {c: i for i, c in enumerate(categorias)}
        df['_z'] = df[valor_col].map(cat_to_idx).astype(float)

        # Construir colorscale discreto: lista de [pos, cor] em "degraus"
        n = len(categorias)
        colorscale = []
        for i, c in enumerate(categorias):
            pos_a = i / max(n - 1, 1) if n > 1 else 0
            cor = paleta_cat[i % len(paleta_cat)]
            colorscale.append([pos_a, cor])
        # Plotly precisa repetir o último ponto pra fechar
        if n == 1:
            colorscale.append([1, paleta_cat[0]])

        z_values = df['_z']
        zmin_eff = -0.5
        zmax_eff = n - 0.5
    else:
        if cor_escala is None:
            colorscale = MAPA_ESCALA_DIVERGENTE if divergente else MAPA_ESCALA_POSITIVA
        else:
            colorscale = cor_escala
        z_values = df[valor_col]

        if divergente:
            max_abs = max(abs(df[valor_col].min()), abs(df[valor_col].max()))
            zmin_eff = -max_abs
            zmax_eff = max_abs
        else:
            zmin_eff = zmin
            zmax_eff = zmax

    # Customdata
    cd = None
    if customdata_cols:
        cd = df[customdata_cols].values

    extras = {}
    if zmin_eff is not None:
        extras['zmin'] = zmin_eff
    if zmax_eff is not None:
        extras['zmax'] = zmax_eff

    trace_kwargs = dict(
        geojson=geojson,
        featureidkey="properties.cod_ibge_6",
        locations=df[cod_col],
        z=z_values,
        text=df[label_col],
        colorscale=colorscale,
        marker=dict(line=dict(color=PALETTE["branco"], width=0.5),
                    opacity=0.85),
        showscale=legenda_visivel and not discreto,
        hovertemplate=hovertemplate + '<extra></extra>',
        **extras,
    )

    if cd is not None:
        trace_kwargs['customdata'] = cd

    if legenda_visivel and not discreto:
        trace_kwargs['colorbar'] = dict(
            thickness=10, len=0.55, x=0.02,
            xanchor='left', y=0.5, outlinewidth=0,
            tickfont=dict(size=10, color=PALETTE["cinza_medio"]),
            title=dict(text=titulo_legenda,
                       font=dict(size=10, color=PALETTE["cinza_medio"]),
                       side='top'),
        )

    fig = go.Figure(go.Choroplethmapbox(**trace_kwargs))

    fig.update_layout(
        mapbox=dict(
            style="white-bg",
            zoom=6.3,
            center=dict(lat=-8.45, lon=-37.8),
        ),
    )

    aplicar_layout_default(fig,
        height=altura,
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )

    return fig


def mapa_pe(df: pd.DataFrame, geojson: dict,
            valor_col: str,
            label_col: str = 'municipio',
            cod_col: str = 'cod_ibge_6',
            divergente: bool = False,
            altura: int = 480,
            unidade: str = '') -> go.Figure:

    escala = MAPA_ESCALA_DIVERGENTE if divergente else MAPA_ESCALA_POSITIVA

    # Garantir match string × string em ambos os lados
    df = df.copy()
    df[cod_col] = df[cod_col].astype(str)

    # Padronizar cod_ibge_6 do GeoJSON também como string
    for f in geojson.get('features', []):
        props = f.get('properties', {})
        if 'cod_ibge_6' in props:
            props['cod_ibge_6'] = str(props['cod_ibge_6'])

    extras = {}
    if divergente:
        max_abs = max(abs(df[valor_col].min()), abs(df[valor_col].max()))
        extras = dict(zmin=-max_abs, zmax=max_abs)

    fig = go.Figure(go.Choroplethmapbox(
        geojson=geojson,
        featureidkey="properties.cod_ibge_6",
        locations=df[cod_col],
        z=df[valor_col],
        text=df[label_col],
        colorscale=escala,
        marker=dict(line=dict(color=PALETTE["branco"], width=0.5),
                    opacity=0.85),
        colorbar=dict(
            thickness=10,
            len=0.55,
            x=0.02,
            xanchor='left',
            y=0.5,
            outlinewidth=0,
            tickfont=dict(size=10, color=PALETTE["cinza_medio"]),
            title=dict(
                text=unidade,
                font=dict(size=10, color=PALETTE["cinza_medio"]),
                side='top',
            ),
        ),
        hovertemplate=(
            '<b>%{text}</b><br>'
            'saldo: %{z:,.0f}'
            '<extra></extra>'
        ),
        **extras,
    ))

    # Centro aproximado de PE: lat -8.4, lon -38.0
    fig.update_layout(
        mapbox=dict(
            style="white-bg",  # SEM tiles externos, tudo offline
            zoom=6.3,
            center=dict(lat=-8.45, lon=-37.8),
        ),
    )

    aplicar_layout_default(fig,
        height=altura,
        margin=dict(l=0, r=0, t=10, b=10),
        dragmode=False,
    )

    return fig



# ============================================================================
# Donut com N fatias
# ============================================================================

def donut_n(labels: list, valores: list, cores: list = None,
            total_centro: str = "", altura: int = 280,
            hovertemplate: str = None) -> go.Figure:
    """
    Donut com N fatias. Mostra percentuais nas fatias e total no centro.
    """
    if cores is None:
        cores = [
            SEMANTIC['destaque'],
            PALETTE['terracota'],
            PALETTE['lilas_acinzentado'],
            PALETTE['cinza_claro'],
        ][:len(labels)]

    if hovertemplate is None:
        hovertemplate = '<b>%{label}</b><br>%{value:,.0f} (%{percent})<extra></extra>'

    fig = go.Figure(go.Pie(
        labels=labels,
        values=valores,
        hole=0.62,
        marker=dict(colors=cores,
                    line=dict(color=PALETTE['branco'], width=2)),
        sort=False,
        rotation=90,
        textinfo='percent',
        textfont=dict(size=11, family=CHART_FONT, color=PALETTE['branco']),
        hovertemplate=hovertemplate,
        showlegend=True,
    ))

    if total_centro:
        fig.add_annotation(
            text=total_centro,
            x=0.5, y=0.5,
            xref='paper', yref='paper',
            showarrow=False,
            font=dict(size=12, family=CHART_FONT_SERIF,
                      color=PALETTE['preto_titulo']),
            align='center',
        )

    aplicar_layout_default(fig,
        height=altura,
        showlegend=True,
        legend=dict(
            orientation='v',
            yanchor='middle', y=0.5,
            xanchor='left', x=1.02,
            font=dict(size=11, color=PALETTE['grafite']),
            itemclick=False,
            itemdoubleclick=False,
        ),
        margin=dict(l=10, r=140, t=10, b=10),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )

    return fig


# ============================================================================
# Barras horizontais com destaque - ranking regional
# ============================================================================

def barras_com_destaque(df: pd.DataFrame, label_col: str, valor_col: str,
                        destaque: str,
                        altura: int = 320,
                        ordem_ascendente: bool = False,
                        sufixo_valor: str = "") -> go.Figure:
    """
    Barras horizontais onde uma categoria específica é destacada em cor
    primária e o resto em cinza neutro.

    Parâmetros
    ----------
    destaque : valor da label_col que deve ganhar destaque (ex: 'Pernambuco')
    ordem_ascendente : se True, menores valores em cima (útil pra "menor é melhor")
    sufixo_valor : string adicionada após o número (ex: '%', ' mil')
    """
    df = df.copy()
    df = df.sort_values(valor_col, ascending=not ordem_ascendente)

    cores = [
        SEMANTIC['destaque'] if str(v) == destaque
        else PALETTE['cinza_claro']
        for v in df[label_col]
    ]

    def _fmt(v):
        if pd.isna(v):
            return ''
        s = f"{v:,.1f}".replace(',', '_').replace('.', ',').replace('_', '.')
        return s + sufixo_valor

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df[valor_col],
        y=df[label_col],
        orientation='h',
        marker=dict(color=cores),
        text=df[valor_col].apply(_fmt),
        textposition='outside',
        textfont=dict(size=11, color=PALETTE['grafite']),
        cliponaxis=False,
        hovertemplate='<b>%{y}</b><br>%{x:,.2f}<extra></extra>',
    ))

    max_val = df[valor_col].max()
    min_val = df[valor_col].min()
    if min_val < 0:
        max_abs = max(abs(min_val), abs(max_val))
        x_range = [min_val - max_abs * 0.20, max(max_val, 0) + max_abs * 0.20]
    else:
        x_range = [0, max_val * 1.20]

    aplicar_layout_default(fig,
        height=altura,
        showlegend=False,
        margin=dict(l=10, r=20, t=10, b=20),
        xaxis=dict(visible=False, range=x_range),
        yaxis=dict(
            showgrid=False,
            tickfont=dict(size=11, color=PALETTE["grafite"]),
            ticks='',
            showline=False,
        ),
    )
    return fig




def _hex_alpha(hex_color: str, alpha: float) -> str:
    """Converte #RRGGBB para rgba(r,g,b,a)."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ============================================================================
# Donut chart (gênero)
# ============================================================================

def donut_dois(label_a: str, valor_a: float,
               label_b: str, valor_b: float,
               cor_a: str = None,
               cor_b: str = None,
               total_centro: str = "",
               altura: int = 220) -> go.Figure:
    """
    Donut com 2 fatias (ex: Masculino vs Feminino).

    Mostra o valor numérico de cada fatia em "outside" e o percentual
    no hover. No centro, opcionalmente, exibe um total ou rótulo.

    Para evitar problema com saldos negativos (que quebram a rosca),
    usamos os valores absolutos no plot e indicamos o sinal pelo texto.
    """
    cor_a = cor_a or SEMANTIC['destaque']        # azul ardósia (masculino)
    cor_b = cor_b or PALETTE['terracota']        # terracota (feminino)

    # Valores absolutos pra rosca - se algum for negativo, sinalizamos
    val_a_abs = abs(valor_a)
    val_b_abs = abs(valor_b)

    # Texto formatado (com sinal correto) para mostrar na fatia
    fmt = lambda v: ("+" if v > 0 else ("−" if v < 0 else "")) + \
                    f"{abs(int(v)):,}".replace(',', '.')

    fig = go.Figure(go.Pie(
        labels=[label_a, label_b],
        values=[val_a_abs, val_b_abs],
        text=[fmt(valor_a), fmt(valor_b)],
        textinfo='text',
        textposition='outside',
        textfont=dict(size=11, family=CHART_FONT,
                      color=PALETTE['grafite']),
        hole=0.62,
        marker=dict(colors=[cor_a, cor_b],
                    line=dict(color=PALETTE['branco'], width=2)),
        sort=False,
        rotation=90,
        hovertemplate='<b>%{label}</b><br>%{value:,.0f} (%{percent})<extra></extra>',
        showlegend=False,
    ))

    # Anotação central com o total (ou label customizado)
    if total_centro:
        fig.add_annotation(
            text=total_centro,
            x=0.5, y=0.5,
            xref='paper', yref='paper',
            showarrow=False,
            font=dict(size=13, family=CHART_FONT_SERIF,
                      color=PALETTE['preto_titulo']),
            align='center',
        )

    aplicar_layout_default(fig,
        height=altura,
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )

    return fig
