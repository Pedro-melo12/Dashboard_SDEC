"""
components/data.py
==================
Camada de acesso aos dados. Carrega os parquets uma única vez (cache em
memória via @lru_cache) e oferece funções de consulta.

Por que cache? Porque o dashboard pode chamar essas funções dezenas de
vezes por interação do usuário (cada gráfico re-renderiza após um
clique, por exemplo). Ler parquet do disco toda vez é desperdício.

Convenção: funções que retornam DataFrames já filtrados/processados
ficam aqui. Os arquivos das abas (tabs/) NÃO devem chamar pd.read_*
diretamente, sempre passar por aqui.
"""

import json
from functools import lru_cache

import pandas as pd

from config import (
    CAGED_MUNICIPAL, CAGED_GENERO, CAGED_SETOR, PNAD_PE,
    PNAD_REGIONAL, POBREZA_REGIONAL,
    MUNICIPIOS_RD, PREFEITOS, VEREADORES,
    GEO_MUNICIPIOS, CATALOGO,
)

# PIB é opcional (pode não existir ainda em algumas instalações)
try:
    from config import PIB_MUNICIPAL
except ImportError:
    PIB_MUNICIPAL = None


# ============================================================================
# Carregamento bruto (com cache)
# ============================================================================
# @lru_cache(maxsize=None) faz o Python "lembrar" o resultado da função.
# Da segunda chamada em diante, ele devolve direto da memória sem reler
# o arquivo. Ideal para datasets que não mudam durante a execução do app.

@lru_cache(maxsize=None)
def caged_municipal() -> pd.DataFrame:
    """Retorna o CAGED municipal completo."""
    return pd.read_parquet(CAGED_MUNICIPAL)


@lru_cache(maxsize=None)
def caged_genero() -> pd.DataFrame:
    """Retorna o CAGED por gênero (estadual)."""
    return pd.read_parquet(CAGED_GENERO)


@lru_cache(maxsize=None)
def caged_setor() -> pd.DataFrame:
    """Retorna o CAGED por setor (5 grandes setores, estadual, mensal)."""
    return pd.read_parquet(CAGED_SETOR)


@lru_cache(maxsize=None)
def pnad() -> pd.DataFrame:
    """Retorna o PNAD em formato long."""
    return pd.read_parquet(PNAD_PE)


@lru_cache(maxsize=None)
def pnad_regional() -> pd.DataFrame:
    """
    Retorna a PNAD trimestral regional consolidada (9 estados do NE +
    Nordeste consolidado, 7 indicadores, 2012-T1 a 2025-T3).
    """
    return pd.read_parquet(PNAD_REGIONAL)


@lru_cache(maxsize=None)
def pobreza_regional() -> pd.DataFrame:
    """
    Retorna a base de pobreza/extrema pobreza por região, trimestral.
    """
    return pd.read_parquet(POBREZA_REGIONAL)


@lru_cache(maxsize=None)
def geojson_municipios() -> dict:
    """Retorna o GeoJSON dos municípios de PE."""
    with open(GEO_MUNICIPIOS, 'r', encoding='utf-8') as f:
        return json.load(f)


@lru_cache(maxsize=None)
def catalogo() -> dict:
    """Retorna o catálogo de datasets."""
    if CATALOGO.exists():
        with open(CATALOGO, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'datasets': []}


# ============================================================================
# Consultas derivadas - PNAD
# ============================================================================

def pnad_indicador(chave: str) -> pd.DataFrame:
    """
    Filtra a PNAD por um indicador específico.

    Parâmetros
    ----------
    chave : str
        Chave técnica (ex: 'taxa_desocupacao', 'rendimento_medio')

    Retorna
    -------
    DataFrame com colunas data, trimestre, ano, valor.
    """
    df = pnad()
    return df[df['indicador'] == chave].sort_values('data').reset_index(drop=True)


def pnad_ultimo_valor(chave: str) -> dict:
    """
    Pega o último valor disponível de um indicador, mais o anterior
    (para calcular variação).

    Retorna
    -------
    dict com keys: valor, valor_anterior, variacao_pp, trimestre, unidade
    (variacao_pp = variação em pontos percentuais quando aplicável)
    """
    df = pnad_indicador(chave)
    if df.empty:
        return {'valor': None, 'valor_anterior': None, 'variacao_pp': None,
                'trimestre': '—', 'unidade': '—'}

    ultimo = df.iloc[-1]
    anterior = df.iloc[-2] if len(df) >= 2 else None

    return {
        'valor': float(ultimo['valor']),
        'valor_anterior': float(anterior['valor']) if anterior is not None else None,
        'variacao_pp': (float(ultimo['valor']) - float(anterior['valor']))
                       if anterior is not None else None,
        'trimestre': ultimo['trimestre'],
        'unidade': ultimo['unidade'],
        'nome': ultimo['indicador_nome'],
    }


# ============================================================================
# Consultas derivadas - CAGED municipal
# ============================================================================

def caged_saldo_acumulado_12m(data_referencia: pd.Timestamp = None) -> pd.DataFrame:
    """
    Calcula o saldo acumulado de 12 meses por município, terminando em
    `data_referencia` (default: última disponível).

    Retorna DataFrame com cod_ibge_6, municipio, saldo_12m, admissoes_12m,
    desligamentos_12m.
    """
    df = caged_municipal()
    if data_referencia is None:
        data_referencia = df['data'].max()

    inicio = data_referencia - pd.DateOffset(months=11)
    janela = df[(df['data'] >= inicio) & (df['data'] <= data_referencia)]

    agg = janela.groupby(['cod_ibge_6', 'municipio'], as_index=False).agg(
        saldo_12m=('saldo', 'sum'),
        admissoes_12m=('admissoes', 'sum'),
        desligamentos_12m=('desligamentos', 'sum'),
    )
    return agg.sort_values('saldo_12m', ascending=False).reset_index(drop=True)


def caged_total_estadual_mes(data_referencia: pd.Timestamp = None) -> dict:
    """
    Totais do estado no mês de referência (default: último mês disponível).
    Retorna dict com saldo, admissoes, desligamentos, data, mes_anterior_saldo.
    """
    df = caged_municipal()
    if data_referencia is None:
        data_referencia = df['data'].max()

    mes_atual = df[df['data'] == data_referencia]
    saldo_atual = int(mes_atual['saldo'].sum())
    adm = int(mes_atual['admissoes'].sum())
    desl = int(mes_atual['desligamentos'].sum())

    # Mês anterior para cálculo de variação
    mes_anterior_data = data_referencia - pd.DateOffset(months=1)
    mes_anterior = df[df['data'] == mes_anterior_data]
    saldo_anterior = int(mes_anterior['saldo'].sum()) if not mes_anterior.empty else None

    return {
        'data': data_referencia,
        'saldo': saldo_atual,
        'admissoes': adm,
        'desligamentos': desl,
        'saldo_mes_anterior': saldo_anterior,
    }


def caged_serie_estadual_mensal() -> pd.DataFrame:
    """Série temporal mensal do saldo total estadual."""
    df = caged_municipal()
    serie = df.groupby('data', as_index=False).agg(
        saldo=('saldo', 'sum'),
        admissoes=('admissoes', 'sum'),
        desligamentos=('desligamentos', 'sum'),
    )
    return serie.sort_values('data').reset_index(drop=True)


def caged_municipios_com_saldo_positivo(data_referencia: pd.Timestamp = None) -> dict:
    """Conta quantos dos 185 municípios estão com saldo positivo no mês."""
    df = caged_municipal()
    if data_referencia is None:
        data_referencia = df['data'].max()

    mes = df[df['data'] == data_referencia]
    positivos = (mes['saldo'] > 0).sum()
    total = len(mes)
    return {'positivos': int(positivos), 'total': int(total)}


def caged_serie_municipio(cod_ibge_6: int) -> pd.DataFrame:
    """Série temporal de um município específico."""
    df = caged_municipal()
    return df[df['cod_ibge_6'] == cod_ibge_6].sort_values('data').reset_index(drop=True)


# ============================================================================
# Consultas derivadas - CAGED por gênero
# ============================================================================

def caged_genero_mes_referencia() -> dict:
    """
    Retorna saldo masculino e feminino do último mês disponível.

    Saída: {'data': Timestamp, 'masculino': int, 'feminino': int, 'total': int}
    """
    df = caged_genero()
    ultima = df['data'].max()
    mes = df[df['data'] == ultima]
    masc = int(mes[mes['sexo'] == 'Masculino']['saldo'].sum())
    fem = int(mes[mes['sexo'] == 'Feminino']['saldo'].sum())
    return {
        'data': ultima,
        'masculino': masc,
        'feminino': fem,
        'total': masc + fem,
    }


def caged_genero_acumulado_ano(ano: int = None) -> dict:
    """
    Retorna saldo acumulado masculino e feminino para um ano completo
    (ou parcial, se for o ano corrente).

    Parâmetros
    ----------
    ano : se None, usa o ano da última data disponível.
    """
    df = caged_genero()
    if ano is None:
        ano = df['data'].max().year

    janela = df[df['data'].dt.year == ano]
    masc = int(janela[janela['sexo'] == 'Masculino']['saldo'].sum())
    fem = int(janela[janela['sexo'] == 'Feminino']['saldo'].sum())
    return {
        'ano': ano,
        'masculino': masc,
        'feminino': fem,
        'total': masc + fem,
    }


# ============================================================================
# Consultas derivadas - CAGED municipal (com filtros de período)
# ============================================================================

def caged_municipal_filtrado(anos: list = None, meses: list = None) -> pd.DataFrame:
    """
    Retorna saldo agregado por município, filtrando por listas de anos
    e/ou meses. Listas vazias ou None significam "sem filtro".

    Parâmetros
    ----------
    anos : list[int] como [2024, 2025], ou None / []
    meses : list[int] como [1, 2, 3], ou None / []
    """
    df = caged_municipal()
    if anos:
        df = df[df['ano'].isin(anos)]
    if meses:
        df = df[df['mes'].isin(meses)]

    agg = df.groupby(['cod_ibge_6', 'municipio'], as_index=False).agg(
        saldo=('saldo', 'sum'),
        admissoes=('admissoes', 'sum'),
        desligamentos=('desligamentos', 'sum'),
    )
    return agg.sort_values('saldo', ascending=False).reset_index(drop=True)


# ============================================================================
# Consultas derivadas - CAGED por setor
# ============================================================================

def caged_setor_acumulado_12m(data_referencia: pd.Timestamp = None) -> pd.DataFrame:
    """
    Saldo acumulado de 12 meses por setor, terminando em data_referencia.
    Retorna DataFrame com setor, saldo_12m, admissoes_12m, desligamentos_12m.
    """
    df = caged_setor()
    if data_referencia is None:
        data_referencia = df['data'].max()

    inicio = data_referencia - pd.DateOffset(months=11)
    janela = df[(df['data'] >= inicio) & (df['data'] <= data_referencia)]

    agg = janela.groupby('setor', as_index=False).agg(
        saldo_12m=('saldo', 'sum'),
        admissoes_12m=('admissoes', 'sum'),
        desligamentos_12m=('desligamentos', 'sum'),
    )
    return agg.sort_values('saldo_12m', ascending=False).reset_index(drop=True)


def caged_setor_filtrado(anos: list = None, meses: list = None) -> pd.DataFrame:
    """
    Retorna saldo agregado por setor, filtrando por anos e/ou meses.
    Listas vazias ou None = sem filtro nessa dimensão.
    """
    df = caged_setor()
    if anos:
        df = df[df['ano'].isin(anos)]
    if meses:
        df = df[df['mes'].isin(meses)]

    agg = df.groupby('setor', as_index=False).agg(
        saldo=('saldo', 'sum'),
        admissoes=('admissoes', 'sum'),
        desligamentos=('desligamentos', 'sum'),
    )
    return agg.sort_values('saldo', ascending=False).reset_index(drop=True)


def caged_setor_serie_temporal(janela_meses: int = 3) -> pd.DataFrame:
    """
    Série temporal por setor com média móvel para suavizar ruído mensal.

    Parâmetros
    ----------
    janela_meses : tamanho da janela da média móvel. 3 é um bom default
    para mostrar a tendência sem perder muito detalhe temporal.
    """
    df = caged_setor().sort_values(['setor', 'data']).copy()
    df['saldo_mm'] = (df.groupby('setor')['saldo']
                       .transform(lambda s: s.rolling(janela_meses, min_periods=1).mean()))
    return df


# ============================================================================
# Consultas derivadas - PNAD regional (9 estados do NE + Nordeste)
# ============================================================================

# Lista das regiões disponíveis no parquet, em ordem alfabética
# (Nordeste sempre por último por ser agregado)
REGIOES_NE_ESTADOS = [
    'Maranhão', 'Piauí', 'Ceará', 'Rio Grande do Norte', 'Paraíba',
    'Pernambuco', 'Alagoas', 'Sergipe', 'Bahia',
]


def pnad_reg_indicador(chave: str, regiao: str = None) -> pd.DataFrame:
    """
    Filtra a PNAD regional por indicador (e opcionalmente por região).

    Parâmetros
    ----------
    chave : ex 'taxa_desemprego', 'desocupados', 'desalentados'
    regiao : ex 'Pernambuco', 'Nordeste'. Se None, retorna todas.
    """
    df = pnad_regional()
    df = df[df['indicador'] == chave]
    if regiao:
        df = df[df['regiao'] == regiao]
    return df.sort_values(['regiao', 'data']).reset_index(drop=True)


def pnad_reg_ultimo_valor(chave: str, regiao: str = 'Pernambuco') -> dict:
    """
    Pega o último valor de um indicador para uma região + variação vs
    trimestre anterior.

    Saída: dict com valor, valor_anterior, variacao_pp, variacao_abs,
    trimestre, unidade, nome.
    """
    df = pnad_reg_indicador(chave, regiao)
    if df.empty:
        return {'valor': None, 'valor_anterior': None, 'variacao_pp': None,
                'variacao_abs': None, 'trimestre': '—', 'unidade': '—',
                'nome': '—'}

    ultimo = df.iloc[-1]
    anterior = df.iloc[-2] if len(df) >= 2 else None

    valor = float(ultimo['valor']) if pd.notna(ultimo['valor']) else None
    valor_ant = float(anterior['valor']) if anterior is not None and \
                pd.notna(anterior['valor']) else None

    variacao_abs = (valor - valor_ant) if (valor is not None and valor_ant is not None) else None

    return {
        'valor': valor,
        'valor_anterior': valor_ant,
        'variacao_pp': variacao_abs,  # alias para indicadores em %
        'variacao_abs': variacao_abs,
        'trimestre': ultimo['trimestre_label'],
        'unidade': ultimo['unidade'],
        'nome': ultimo['indicador_nome'],
    }


def pnad_reg_estrutura_pea(regiao: str = 'Pernambuco',
                            trimestre_label: str = None) -> dict:
    """
    Retorna a estrutura da população em idade de trabalhar (PIA) para
    uma região e trimestre. Composição:
        ocupados + desocupados = força de trabalho
        + desalentados + (fora_forca - desalentados) = fora da força

    A coluna 'fora_forca' já INCLUI os desalentados na PNAD, então
    para evitar dupla contagem no donut, calculamos
    fora_nao_desalentados = fora_forca - desalentados.

    Parâmetros
    ----------
    regiao : ex 'Pernambuco', 'Nordeste'
    trimestre_label : 'YYYY-Tn'. Se None, último disponível.
    """
    df = pnad_regional()
    df_reg = df[df['regiao'] == regiao]

    if trimestre_label is None:
        # Último disponível para esta região
        trimestre_label = df_reg['trimestre_label'].max()

    sub = df_reg[df_reg['trimestre_label'] == trimestre_label]

    def _get(chave):
        v = sub[sub['indicador'] == chave]['valor']
        return float(v.iloc[0]) if not v.empty and pd.notna(v.iloc[0]) else 0.0

    ocupados = _get('ocupados')
    desocupados = _get('desocupados')
    desalentados = _get('desalentados')
    fora_total = _get('fora_forca')
    fora_nao_desalentados = max(fora_total - desalentados, 0)

    return {
        'regiao': regiao,
        'trimestre': trimestre_label,
        'ocupados': ocupados,
        'desocupados': desocupados,
        'desalentados': desalentados,
        'fora_outros': fora_nao_desalentados,
        'total': ocupados + desocupados + desalentados + fora_nao_desalentados,
    }


def pnad_reg_ranking_estados(chave: str = 'taxa_desemprego',
                              trimestre_label: str = None) -> pd.DataFrame:
    """
    Retorna ranking dos 9 estados do NE para um indicador num trimestre.
    Não inclui o agregado Nordeste por default.

    Para indicadores onde "menor é melhor" (taxa de desemprego, pobreza),
    o consumidor pode ordenar ascendente para ver os melhores em cima.
    """
    df = pnad_regional()
    df = df[(df['indicador'] == chave) & (df['regiao'].isin(REGIOES_NE_ESTADOS))]

    if trimestre_label is None:
        trimestre_label = df['trimestre_label'].max()

    sub = df[df['trimestre_label'] == trimestre_label]
    return sub[['regiao', 'valor', 'trimestre_label']].sort_values(
        'valor', ascending=False
    ).reset_index(drop=True)


def pnad_reg_tabela_estados(trimestre_label: str = None) -> pd.DataFrame:
    """
    Retorna uma tabela wide com todos os 9 estados do NE no trimestre
    indicado, com colunas para cada indicador. Útil para data tables.
    """
    df = pnad_regional()
    df = df[df['regiao'].isin(REGIOES_NE_ESTADOS)]

    if trimestre_label is None:
        trimestre_label = df['trimestre_label'].max()

    sub = df[df['trimestre_label'] == trimestre_label]
    pivot = sub.pivot_table(
        index='regiao',
        columns='indicador',
        values='valor',
        aggfunc='first'
    ).reset_index()

    # Ordenar pela taxa de desemprego (ascendente = melhor primeiro)
    if 'taxa_desemprego' in pivot.columns:
        pivot = pivot.sort_values('taxa_desemprego').reset_index(drop=True)

    pivot['trimestre_label'] = trimestre_label
    return pivot


def pnad_reg_trimestres_disponiveis(regiao: str = 'Pernambuco') -> list:
    """
    Lista de trimestres disponíveis para uma região, mais recente primeiro.
    Retorna lista de strings 'YYYY-Tn'.
    """
    df = pnad_regional()
    df = df[df['regiao'] == regiao]
    trimestres = df[['data', 'trimestre_label']].drop_duplicates()
    trimestres = trimestres.sort_values('data', ascending=False)
    return trimestres['trimestre_label'].tolist()


# ============================================================================
# Consultas derivadas - Pobreza
# ============================================================================

def pobreza_serie(regiao: str = 'Pernambuco') -> pd.DataFrame:
    """
    Série temporal de pobreza e extrema pobreza para uma região.

    Retorna DataFrame com colunas: data, trimestre_label, indicador
    (pobreza ou extrema_pobreza), indicador_nome, valor (em pessoas).
    """
    df = pobreza_regional()
    df = df[df['regiao'] == regiao]
    return df.sort_values(['data', 'indicador']).reset_index(drop=True)


def pobreza_ultimo_trimestre(regiao: str = 'Pernambuco') -> dict:
    """
    Retorna os valores mais recentes de pobreza e extrema pobreza para
    uma região, mais o trimestre.
    """
    df = pobreza_serie(regiao)
    if df.empty:
        return {}
    ultima_data = df['data'].max()
    sub = df[df['data'] == ultima_data]
    out = {'trimestre': sub['trimestre_label'].iloc[0]}
    for _, row in sub.iterrows():
        out[row['indicador']] = float(row['valor'])
    return out


# ============================================================================
# Consultas derivadas - Informalidade
# ============================================================================

def informalidade_serie(regiao: str = 'Pernambuco') -> pd.DataFrame:
    """
    Série temporal da informalidade.

    A base original (PNAD) traz o número ABSOLUTO de pessoas em ocupação
    informal (não a taxa percentual, apesar do nome dizer "%" no
    metadado). Aqui calculamos a taxa real cruzando com ocupados:

        taxa_informalidade = informais / ocupados × 100

    Retorna DataFrame com colunas:
        data, trimestre, informais (pessoas), ocupados (pessoas),
        taxa (% sobre ocupados)
    """
    inf = pnad()
    inf = inf[inf['indicador'] == 'informalidade'][
        ['data', 'trimestre', 'valor']
    ].rename(columns={'valor': 'informais'})
    inf = inf[inf['informais'] > 0]  # zeros = sem dado na fonte

    if regiao == 'Pernambuco':
        ocup = pnad_regional()
        ocup = ocup[
            (ocup['indicador'] == 'ocupados') &
            (ocup['regiao'] == 'Pernambuco')
        ][['trimestre_label', 'valor']].rename(
            columns={'trimestre_label': 'trimestre', 'valor': 'ocupados'}
        )
    else:
        ocup = pnad_regional()
        ocup = ocup[
            (ocup['indicador'] == 'ocupados') &
            (ocup['regiao'] == regiao)
        ][['trimestre_label', 'valor']].rename(
            columns={'trimestre_label': 'trimestre', 'valor': 'ocupados'}
        )

    merged = inf.merge(ocup, on='trimestre', how='left')
    merged['taxa'] = (merged['informais'] / merged['ocupados']) * 100
    return merged.sort_values('data').reset_index(drop=True)


def informalidade_ultimo(regiao: str = 'Pernambuco') -> dict:
    """Último valor de informalidade + variação vs trimestre anterior."""
    df = informalidade_serie(regiao)
    if df.empty:
        return {'taxa': None, 'informais': None, 'trimestre': '—',
                'variacao_pp': None}

    ultimo = df.iloc[-1]
    anterior = df.iloc[-2] if len(df) >= 2 else None
    variacao_pp = (float(ultimo['taxa']) - float(anterior['taxa'])
                   if anterior is not None else None)

    return {
        'taxa': float(ultimo['taxa']),
        'informais': float(ultimo['informais']),
        'ocupados': float(ultimo['ocupados']),
        'trimestre': ultimo['trimestre'],
        'variacao_pp': variacao_pp,
    }


# ============================================================================
# Regiões de Desenvolvimento (RDs)
# ============================================================================

@lru_cache(maxsize=None)
def municipios_rd() -> pd.DataFrame:
    """
    Mapeamento município → RD.
    Colunas: cod_ibge_6, municipio, regiao_desenvolvimento.
    """
    return pd.read_parquet(MUNICIPIOS_RD)


@lru_cache(maxsize=None)
def lista_rds() -> list:
    """Lista de RDs disponíveis, em ordem alfabética."""
    df = municipios_rd()
    return sorted(df['regiao_desenvolvimento'].unique().tolist())


def rd_de_municipio(cod_ibge_6: int) -> str:
    """Retorna a RD de um município (ou None)."""
    df = municipios_rd()
    sub = df[df['cod_ibge_6'] == cod_ibge_6]
    if sub.empty:
        return None
    return sub.iloc[0]['regiao_desenvolvimento']


def municipios_da_rd(rd: str) -> pd.DataFrame:
    """Retorna todos os municípios de uma RD."""
    df = municipios_rd()
    return df[df['regiao_desenvolvimento'] == rd].reset_index(drop=True)


# ============================================================================
# Prefeitos e Vereadores (eleições 2024)
# ============================================================================

@lru_cache(maxsize=None)
def prefeitos() -> pd.DataFrame:
    """
    1 linha por município (com prefeito eleito).

    Fernando de Noronha não tem prefeito municipal — é distrito estadual
    administrado por administrador indicado pelo Governador. A base tem
    184 linhas (185 - Fernando de Noronha).
    """
    return pd.read_parquet(PREFEITOS)


@lru_cache(maxsize=None)
def vereadores() -> pd.DataFrame:
    """
    1 linha por vereador eleito. ~2149 vereadores em PE.

    Colunas: cod_ibge_6, municipio, vereador_nome, partido, genero
    """
    return pd.read_parquet(VEREADORES)


@lru_cache(maxsize=None)
def n_vereadores_por_municipio() -> pd.DataFrame:
    """
    Contagem de vereadores eleitos por município.
    Colunas: cod_ibge_6, municipio, n_vereadores
    """
    df = vereadores()
    return (df.groupby(['cod_ibge_6', 'municipio'])
              .size().reset_index(name='n_vereadores'))


def gestao_publica_consolidada() -> pd.DataFrame:
    """
    View consolidada para o mapa de Gestão Pública.

    Junta município + RD + prefeito + partido + gênero do prefeito +
    nº vereadores. 1 linha por município. Fernando de Noronha aparece
    sem prefeito (campos preenchidos como None / 0).
    """
    rd = municipios_rd()
    pref = prefeitos()
    nver = n_vereadores_por_municipio()

    df = rd.merge(pref[['cod_ibge_6', 'prefeito_nome',
                        'prefeito_partido', 'prefeito_genero']],
                  on='cod_ibge_6', how='left')
    df = df.merge(nver[['cod_ibge_6', 'n_vereadores']],
                  on='cod_ibge_6', how='left')
    df['n_vereadores'] = df['n_vereadores'].fillna(0).astype(int)
    return df


def estatisticas_estaduais_gestao() -> dict:
    """
    KPIs para o cabeçalho da aba Gestão Pública.
    """
    pref = prefeitos()
    ver = vereadores()

    total_partidos = (set(pref['prefeito_partido'].unique()) |
                      set(ver['partido'].unique()))

    pref_fem = (pref['prefeito_genero'] == 'FEMININO').sum()
    pref_masc = (pref['prefeito_genero'] == 'MASCULINO').sum()
    pct_pref_fem = (pref_fem / len(pref) * 100) if len(pref) else 0

    ver_fem = (ver['genero'] == 'FEMININO').sum()
    ver_masc = (ver['genero'] == 'MASCULINO').sum()
    pct_ver_fem = (ver_fem / len(ver) * 100) if len(ver) else 0

    return {
        'total_prefeitos': len(pref),
        'total_vereadores': len(ver),
        'total_partidos': len(total_partidos),
        'prefeitos_fem': pref_fem,
        'prefeitos_masc': pref_masc,
        'pct_prefeitos_fem': pct_pref_fem,
        'vereadores_fem': ver_fem,
        'vereadores_masc': ver_masc,
        'pct_vereadores_fem': pct_ver_fem,
    }


def ranking_partidos_prefeitos() -> pd.DataFrame:
    """Partidos com mais prefeitos, em ordem decrescente."""
    pref = prefeitos()
    return (pref.groupby('prefeito_partido').size()
            .reset_index(name='n_prefeitos')
            .sort_values('n_prefeitos', ascending=False)
            .reset_index(drop=True))


def ranking_partidos_vereadores() -> pd.DataFrame:
    """Partidos com mais vereadores, em ordem decrescente."""
    ver = vereadores()
    return (ver.groupby('partido').size()
            .reset_index(name='n_vereadores')
            .sort_values('n_vereadores', ascending=False)
            .reset_index(drop=True))


# ============================================================================
# Carregamento - Regiões de Desenvolvimento, Prefeitos, Vereadores
# ============================================================================

@lru_cache(maxsize=None)
def municipios_rd() -> pd.DataFrame:
    """
    Mapeamento de municípios para Regiões de Desenvolvimento (RD).
    Colunas: cod_ibge_6, municipio, regiao_desenvolvimento.

    PE tem 12 RDs administrativas (Metropolitana, Mata Norte, Mata Sul,
    Agreste Central, Agreste Setentrional, Agreste Meridional, Pajeú,
    Sertão Central, do Araripe, do São Francisco, Itaparica, Moxotó).
    """
    return pd.read_parquet(MUNICIPIOS_RD)


@lru_cache(maxsize=None)
def prefeitos() -> pd.DataFrame:
    """
    Prefeitos eleitos por município (1 por linha).
    Colunas: cod_ibge_6, municipio, prefeito_nome, prefeito_partido,
             prefeito_genero.

    Fernando de Noronha não aparece (não tem prefeito).
    """
    return pd.read_parquet(PREFEITOS)


@lru_cache(maxsize=None)
def vereadores() -> pd.DataFrame:
    """
    Vereadores eleitos por município (várias linhas por município).
    Colunas: cod_ibge_6, municipio, vereador_nome, partido, genero.
    """
    return pd.read_parquet(VEREADORES)


# ============================================================================
# Consultas derivadas - RD
# ============================================================================

def rd_lookup_por_cod(cod_ibge_6: int) -> str:
    """Retorna o nome da RD de um município (ou '—' se não encontrar)."""
    df = municipios_rd()
    sub = df[df['cod_ibge_6'] == cod_ibge_6]
    if sub.empty:
        return '—'
    return sub['regiao_desenvolvimento'].iloc[0]


def municipios_de_rd(rd_nome: str) -> pd.DataFrame:
    """Lista de cod_ibge_6 + municipio da RD informada."""
    df = municipios_rd()
    return df[df['regiao_desenvolvimento'] == rd_nome][
        ['cod_ibge_6', 'municipio']
    ].reset_index(drop=True)


def lista_rds() -> list:
    """Lista das 12 RDs (ordenadas por nome)."""
    df = municipios_rd()
    return sorted(df['regiao_desenvolvimento'].unique().tolist())


# ============================================================================
# Consultas derivadas - Vereadores
# ============================================================================

def n_vereadores_por_municipio() -> pd.DataFrame:
    """
    Contagem de vereadores por município.
    Retorna: cod_ibge_6, municipio, n_vereadores.
    """
    df = vereadores()
    agg = df.groupby(['cod_ibge_6', 'municipio'], as_index=False).size()
    agg = agg.rename(columns={'size': 'n_vereadores'})
    return agg


def vereadores_por_municipio(cod_ibge_6: int) -> int:
    """Retorna o número de vereadores de um município."""
    df = vereadores()
    return int((df['cod_ibge_6'] == cod_ibge_6).sum())


def n_vereadores_por_partido() -> pd.DataFrame:
    """Contagem de vereadores por partido (para ranking estadual)."""
    df = vereadores()
    agg = df.groupby('partido', as_index=False).size().rename(
        columns={'size': 'n_vereadores'}
    )
    return agg.sort_values('n_vereadores', ascending=False).reset_index(drop=True)


def n_prefeitos_por_partido() -> pd.DataFrame:
    """Contagem de prefeitos por partido (para ranking estadual)."""
    df = prefeitos()
    agg = df.groupby('prefeito_partido', as_index=False).size().rename(
        columns={'size': 'n_prefeitos', 'prefeito_partido': 'partido'}
    )
    return agg.sort_values('n_prefeitos', ascending=False).reset_index(drop=True)


def distribuicao_genero_prefeitos() -> dict:
    """Distribuição de prefeitos por gênero. Retorna {genero: contagem}."""
    df = prefeitos()
    return df['prefeito_genero'].value_counts().to_dict()


# ============================================================================
# Tabela consolidada de gestão pública (1 linha por município)
# ============================================================================

@lru_cache(maxsize=None)
def gestao_publica_municipal() -> pd.DataFrame:
    """
    Tabela consolidada de gestão pública por município:
        cod_ibge_6, municipio, prefeito_nome, prefeito_partido,
        prefeito_genero, n_vereadores, regiao_desenvolvimento

    Útil para popular mapa, hover, tabela e cards.
    """
    pref = prefeitos()
    n_ver = n_vereadores_por_municipio()
    rd = municipios_rd()

    # Começamos do CAGED como base canônica de 185 municípios
    caged = pd.read_parquet(CAGED_MUNICIPAL)
    base = caged[['cod_ibge_6', 'municipio']].drop_duplicates().reset_index(drop=True)

    df = (base
          .merge(rd[['cod_ibge_6', 'regiao_desenvolvimento']],
                 on='cod_ibge_6', how='left')
          .merge(pref[['cod_ibge_6', 'prefeito_nome', 'prefeito_partido',
                       'prefeito_genero']],
                 on='cod_ibge_6', how='left')
          .merge(n_ver[['cod_ibge_6', 'n_vereadores']],
                 on='cod_ibge_6', how='left'))

    # Fernando de Noronha não tem prefeito → preencher com placeholder
    df['n_vereadores'] = df['n_vereadores'].fillna(0).astype(int)
    return df


# ============================================================================
# Carregamento - PIB municipal (SEPLAG-PE / IBGE)
# ============================================================================

@lru_cache(maxsize=None)
def pib_municipal() -> pd.DataFrame:
    """
    PIB dos municípios de Pernambuco em formato long.

    Colunas: cod_ibge_6, municipio, ano, pib, vab_total, impostos,
             pib_per_capita, regiao_desenvolvimento

    Cobertura:
    - 2010-2021: dados completos (PIB, VAB, Impostos, per capita)
    - 2022-2023: apenas PIB e PIB per capita (VAB ainda não publicado
      pelo IBGE - veja Nota Técnica 02/2024 do Sistema de Contas
      Nacionais)

    Valores em REAIS (não em milhares).
    """
    return pd.read_parquet(PIB_MUNICIPAL)


# ============================================================================
# Consultas derivadas - PIB
# ============================================================================

def pib_anos_disponiveis() -> list:
    """Lista de anos disponíveis no PIB municipal, mais recente primeiro."""
    df = pib_municipal()
    return sorted(df['ano'].unique().tolist(), reverse=True)


def pib_ultimo_ano() -> int:
    """Último ano com dados de PIB."""
    return pib_anos_disponiveis()[0]


def pib_municipal_ano(ano: int = None) -> pd.DataFrame:
    """
    Retorna PIB de todos os municípios em um ano específico, com dados
    da RD anexados e participações pré-calculadas:
        cod_ibge_6, municipio, ano, pib, pib_per_capita,
        regiao_desenvolvimento,
        pib_rd       (PIB total da RD)
        pib_estado   (PIB total do estado)
        part_na_rd   (% do município no PIB da RD)
        part_no_estado (% do município no PIB do estado)
    """
    if ano is None:
        ano = pib_ultimo_ano()

    df = pib_municipal()
    df_ano = df[df['ano'] == ano].copy()

    # Agregação por RD
    soma_rd = df_ano.groupby('regiao_desenvolvimento', as_index=False)[
        'pib'].sum().rename(columns={'pib': 'pib_rd'})
    df_ano = df_ano.merge(soma_rd, on='regiao_desenvolvimento', how='left')

    # Soma estadual
    pib_estado = df_ano['pib'].sum()
    df_ano['pib_estado'] = pib_estado

    df_ano['part_na_rd'] = 100 * df_ano['pib'] / df_ano['pib_rd']
    df_ano['part_no_estado'] = 100 * df_ano['pib'] / df_ano['pib_estado']

    return df_ano


def pib_estadual_serie() -> pd.DataFrame:
    """
    Série temporal do PIB do estado (soma de todos os municípios).
    Retorna: ano, pib, vab_total, impostos
    """
    df = pib_municipal()
    return (df.groupby('ano', as_index=False)
            .agg(pib=('pib', 'sum'),
                 vab_total=('vab_total', 'sum'),
                 impostos=('impostos', 'sum'))
            .sort_values('ano')
            .reset_index(drop=True))


def pib_ranking_rds(ano: int = None) -> pd.DataFrame:
    """
    Ranking das 12 RDs por PIB total em um ano.
    Colunas: regiao_desenvolvimento, pib, n_municipios, part_no_estado
    """
    if ano is None:
        ano = pib_ultimo_ano()
    df = pib_municipal()
    df = df[df['ano'] == ano]
    agg = (df.groupby('regiao_desenvolvimento', as_index=False)
           .agg(pib=('pib', 'sum'),
                n_municipios=('cod_ibge_6', 'count')))
    total = agg['pib'].sum()
    agg['part_no_estado'] = 100 * agg['pib'] / total
    return agg.sort_values('pib', ascending=False).reset_index(drop=True)


def pib_ranking_municipios(ano: int = None, top_n: int = 10) -> pd.DataFrame:
    """Top N municípios por PIB em um ano."""
    df = pib_municipal_ano(ano)
    return df.nlargest(top_n, 'pib').reset_index(drop=True)


def pib_crescimento_estadual() -> pd.DataFrame:
    """
    Taxa de crescimento nominal anual do PIB estadual.
    Retorna: ano, pib, crescimento_pct (vs ano anterior)
    """
    df = pib_estadual_serie()
    df['crescimento_pct'] = df['pib'].pct_change() * 100
    return df


def pib_kpis_estaduais(ano: int = None) -> dict:
    """
    Indicadores-resumo do estado em um ano:
    - pib total estadual
    - PIB per capita médio (média ponderada)
    - taxa de crescimento vs ano anterior
    - município com maior PIB
    - participação dos top 5 municípios
    """
    if ano is None:
        ano = pib_ultimo_ano()
    df = pib_municipal_ano(ano)
    pib_total = df['pib'].sum()

    # Crescimento
    cresc = pib_crescimento_estadual()
    cresc_ano = cresc[cresc['ano'] == ano]
    cresc_pct = float(cresc_ano['crescimento_pct'].iloc[0]) if not cresc_ano.empty else None

    # Top município
    top1 = df.nlargest(1, 'pib').iloc[0]

    # Participação top 5
    top5 = df.nlargest(5, 'pib')
    part_top5 = 100 * top5['pib'].sum() / pib_total

    # PIB per capita médio (já vem ponderado)
    pc_medio = df['pib_per_capita'].mean()

    return {
        'ano': ano,
        'pib_total': float(pib_total),
        'pib_per_capita_medio': float(pc_medio) if pd.notna(pc_medio) else None,
        'crescimento_pct': cresc_pct,
        'top_municipio': top1['municipio'],
        'top_municipio_pib': float(top1['pib']),
        'top_municipio_part': float(top1['part_no_estado']),
        'part_top5_pct': float(part_top5),
    }


# ============================================================================
# VAB Setorial - participação dos municípios no VAB de cada setor da RD
# ============================================================================

# Caminho do parquet de VAB setorial (gerado pelo pib_etl)
VAB_SETORIAL = PIB_MUNICIPAL.parent / "pib_vab_setorial.parquet" if PIB_MUNICIPAL else None


@lru_cache(maxsize=None)
def vab_setorial() -> pd.DataFrame:
    """
    Participação de cada município no VAB setorial DA SUA RD.

    Colunas: cod_ibge_6, municipio, ano, setor, participacao_na_rd,
             regiao_desenvolvimento

    Setores: agropecuaria, industria, servicos, apu

    A participacao_na_rd é uma fração [0, 1]. Para cada (RD, ano, setor),
    a soma das participações dos municípios da RD = 1.0.

    Cobertura: 2010-2021 (Tabela 4 do XLS - SEPLAG-PE).
    """
    return pd.read_parquet(VAB_SETORIAL)


def vab_setorial_anos_disponiveis() -> list:
    df = vab_setorial()
    return sorted(df['ano'].unique().tolist(), reverse=True)


def vab_setorial_por_rd(rd_nome: str, ano: int = None) -> pd.DataFrame:
    """
    Participações dos municípios de uma RD em cada setor (em %).

    Retorna DataFrame wide:
        cod_ibge_6, municipio, agropecuaria, industria, servicos, apu

    Onde cada coluna setorial é o % do VAB daquele setor da RD que o
    município produz. Ex: "Belo Jardim, indústria 32,8%" significa que
    Belo Jardim responde por 32,8% do VAB Industrial do Agreste Central.
    """
    df = vab_setorial()
    if ano is None:
        ano = df['ano'].max()
    sub = df[(df['regiao_desenvolvimento'] == rd_nome) & (df['ano'] == ano)]
    pivot = sub.pivot_table(
        index=['cod_ibge_6', 'municipio'],
        columns='setor',
        values='participacao_na_rd',
        aggfunc='first',
    ).reset_index()
    # Multiplicar por 100 (vinha em fração)
    for c in ['agropecuaria', 'industria', 'servicos', 'apu']:
        if c in pivot.columns:
            pivot[c] = pivot[c] * 100
    return pivot


# ============================================================================
# PIB - dados detalhados de um único município
# ============================================================================

def pib_municipio_detalhe(cod_ibge_6: int, ano: int = None) -> dict:
    """
    Retorna informações de PIB para um município específico em um ano.

    Saída:
        municipio, ano, pib, pib_per_capita,
        pib_rd, pib_estado,
        part_na_rd, part_no_estado,
        rank_estadual, rank_na_rd,
        impostos, dependencia_impostos_pct,
        regiao_desenvolvimento,
        n_municipios_estado (185)
    """
    if ano is None:
        ano = pib_ultimo_ano()

    df = pib_municipal_ano(ano)
    sub = df[df['cod_ibge_6'] == cod_ibge_6]
    if sub.empty:
        return None

    row = sub.iloc[0]

    # Ranking estadual
    df_sorted = df.sort_values('pib', ascending=False).reset_index(drop=True)
    rank_est = int(df_sorted[df_sorted['cod_ibge_6'] == cod_ibge_6].index[0]) + 1

    # Ranking na RD
    df_rd = df[df['regiao_desenvolvimento'] == row['regiao_desenvolvimento']]
    df_rd_sorted = df_rd.sort_values('pib', ascending=False).reset_index(drop=True)
    rank_rd = int(df_rd_sorted[df_rd_sorted['cod_ibge_6'] == cod_ibge_6].index[0]) + 1

    # Impostos & dependência
    df_full = pib_municipal()
    full_row = df_full[(df_full['cod_ibge_6'] == cod_ibge_6) &
                        (df_full['ano'] == ano)]
    impostos = float(full_row['impostos'].iloc[0]) if not full_row.empty and \
               pd.notna(full_row['impostos'].iloc[0]) else None
    dep = float(full_row['dependencia_impostos_pct'].iloc[0]) if not full_row.empty and \
          pd.notna(full_row['dependencia_impostos_pct'].iloc[0]) else None

    return {
        'cod_ibge_6': int(cod_ibge_6),
        'municipio': row['municipio'],
        'ano': int(ano),
        'pib': float(row['pib']),
        'pib_per_capita': float(row['pib_per_capita']) if pd.notna(row['pib_per_capita']) else None,
        'pib_rd': float(row['pib_rd']),
        'pib_estado': float(row['pib_estado']),
        'part_na_rd': float(row['part_na_rd']),
        'part_no_estado': float(row['part_no_estado']),
        'rank_estadual': rank_est,
        'rank_na_rd': rank_rd,
        'impostos': impostos,
        'dependencia_impostos_pct': dep,
        'regiao_desenvolvimento': row['regiao_desenvolvimento'],
        'n_municipios_estado': len(df),
        'n_municipios_rd': len(df_rd),
    }


def pib_serie_municipio(cod_ibge_6: int) -> pd.DataFrame:
    """Série temporal de PIB para um município específico."""
    df = pib_municipal()
    return df[df['cod_ibge_6'] == cod_ibge_6].sort_values('ano').reset_index(drop=True)


# ============================================================================
# Crescimento real (deflacionado pelo IPCA)
# ============================================================================

def pib_crescimento_estadual_real() -> pd.DataFrame:
    """
    Taxa de crescimento NOMINAL e REAL anual do PIB estadual.

    Retorna: ano, pib_nominal, pib_real_2023,
             cresc_nominal_pct, cresc_real_pct
    """
    df = pib_municipal()
    estado = (df.groupby('ano', as_index=False)
              .agg(pib_nominal=('pib', 'sum'),
                   pib_real_2023=('pib_real_2023', 'sum')))
    estado['cresc_nominal_pct'] = estado['pib_nominal'].pct_change() * 100
    estado['cresc_real_pct'] = estado['pib_real_2023'].pct_change() * 100
    return estado.sort_values('ano').reset_index(drop=True)


# ============================================================================
# VAB Setorial ABSOLUTO (Tabela 1 do VBA_PE)
# ============================================================================

VAB_ABSOLUTO = (PIB_MUNICIPAL.parent / "vab_setorial_absoluto.parquet"
                if PIB_MUNICIPAL else None)


@lru_cache(maxsize=None)
def vab_setorial_absoluto() -> pd.DataFrame:
    """
    VAB ABSOLUTO por setor por município (em reais).

    Colunas: cod_ibge_6, municipio, ano, setor, vab, regiao_desenvolvimento

    Setores: agropecuaria, industria, servicos, apu

    A soma dos 4 setores de um (município, ano) bate com vab_total do
    parquet de PIB (diferença máxima de R$ 1 por arredondamento).

    Cobertura: 2010-2021. Fonte: Tabela 1 do VBA_PE (SEPLAG-PE).
    """
    return pd.read_parquet(VAB_ABSOLUTO)


def vab_absoluto_por_municipio(cod_ibge_6: int, ano: int = None) -> dict:
    """
    Composição setorial de UM município em um ano:
        {agropecuaria: R$, industria: R$, servicos: R$, apu: R$, total: R$}

    Mais a composição percentual.
    """
    df = vab_setorial_absoluto()
    if ano is None:
        ano = df['ano'].max()
    sub = df[(df['cod_ibge_6'] == cod_ibge_6) & (df['ano'] == ano)]
    if sub.empty:
        return None
    out = {}
    for setor in ['agropecuaria', 'industria', 'servicos', 'apu']:
        v = sub[sub['setor'] == setor]['vab'].sum()
        out[setor] = float(v)
    out['total'] = sum(out.values())
    # composição em %
    if out['total'] > 0:
        for s in ['agropecuaria', 'industria', 'servicos', 'apu']:
            out[f'{s}_pct'] = 100 * out[s] / out['total']
    return out


def vab_absoluto_por_rd(rd_nome: str, ano: int = None) -> pd.DataFrame:
    """
    Agrega o VAB absoluto dos municípios de uma RD por setor.

    Retorna DataFrame wide: setor, vab (somado dos municípios da RD).

    Útil para mostrar composição setorial da RD inteira.
    """
    df = vab_setorial_absoluto()
    if ano is None:
        ano = df['ano'].max()
    sub = df[(df['regiao_desenvolvimento'] == rd_nome) & (df['ano'] == ano)]
    if sub.empty:
        return pd.DataFrame()
    agg = sub.groupby('setor', as_index=False)['vab'].sum()
    total = agg['vab'].sum()
    agg['pct'] = 100 * agg['vab'] / total
    return agg.reset_index(drop=True)


def vab_absoluto_top_setor_rd(rd_nome: str, setor: str,
                               ano: int = None, top_n: int = None) -> pd.DataFrame:
    """
    Para uma RD + setor + ano, retorna ranking dos municípios da RD
    pelos valores absolutos de VAB naquele setor.

    Se top_n é None, retorna todos os municípios da RD.
    """
    df = vab_setorial_absoluto()
    if ano is None:
        ano = df['ano'].max()
    sub = df[(df['regiao_desenvolvimento'] == rd_nome)
             & (df['ano'] == ano)
             & (df['setor'] == setor)]
    sub = sub.sort_values('vab', ascending=False).reset_index(drop=True)
    if top_n:
        sub = sub.head(top_n)
    return sub[['cod_ibge_6', 'municipio', 'vab']].copy()


# ============================================================================
# Carga tributária - % impostos sobre PIB (com filtro por RD)
# ============================================================================

def carga_tributaria_municipios(ano: int = None,
                                rd_nome: str = None) -> pd.DataFrame:
    """
    Ranking de municípios pela % de impostos no PIB.

    Antes chamado de "dependência de impostos", mas o termo está mais
    correto como "carga tributária sobre produtos" - é o ICMS+IPI+ISS
    incidente sobre a produção, não transferências da União.

    Parâmetros:
        ano : se None, usa o último com dados (2021, IBGE atrasou 2022/23)
        rd_nome : se informado, filtra apenas municípios da RD

    Retorna: cod_ibge_6, municipio, regiao_desenvolvimento, pib,
             impostos, dependencia_impostos_pct (já calculado no ETL)
    """
    df = pib_municipal()
    sub = df[df['dependencia_impostos_pct'].notna()].copy()

    if ano is None:
        # último ano com dados de impostos (2021 - IBGE atrasou 2022/23)
        ano = sub['ano'].max()
    sub = sub[sub['ano'] == ano]

    if rd_nome:
        sub = sub[sub['regiao_desenvolvimento'] == rd_nome]

    return sub[['cod_ibge_6', 'municipio', 'regiao_desenvolvimento',
                'pib', 'impostos', 'dependencia_impostos_pct']].sort_values(
        'dependencia_impostos_pct', ascending=False
    ).reset_index(drop=True)


# ============================================================================
# PIB nominal × real - deflacionado ao primeiro ano (2010)
# ============================================================================

def pib_estadual_nominal_e_real_base2010() -> pd.DataFrame:
    """
    Série temporal do PIB estadual com base = 2010.

    Diferente de pib_crescimento_estadual_real() que deflaciona TUDO
    para preços de 2023 (ano-base mais recente), aqui mostramos os dois
    fluxos ancorados em 2010, que é mais intuitivo visualmente:

    - PIB nominal: cresce rápido (acumula inflação + crescimento real)
    - PIB real (a preços de 2010): cresce devagar (só crescimento real)

    No gráfico, a área entre as duas linhas representa o efeito da
    inflação acumulada.

    Retorna: ano, pib_nominal, pib_real_base2010,
             cresc_nominal_pct, cresc_real_pct
    """
    df = pib_municipal()
    estado = (df.groupby('ano', as_index=False)
              .agg(pib_nominal=('pib', 'sum'),
                   pib_real_2023=('pib_real_2023', 'sum')))

    # PIB real a preços de 2010 = PIB real 2023 × (PIB nominal 2010 / PIB real 2023 em 2010)
    # Que é equivalente a: PIB nominal × deflator2010
    # deflator2010(ano) = 1 / inflação acumulada de 2010 até `ano`
    #
    # Forma mais direta: usar a razão entre pib_real_2023 do ano X e
    # pib_real_2023 de 2010 para reescalar.
    pib_real_2010_base = estado.loc[estado['ano'] == 2010, 'pib_real_2023'].iloc[0]
    pib_nominal_2010 = estado.loc[estado['ano'] == 2010, 'pib_nominal'].iloc[0]
    # Em 2010, real = nominal (em preços de 2010)
    # Para outros anos: pib_real_base2010 = pib_real_2023(ano) × (nominal2010 / real2023_em_2010)
    fator = pib_nominal_2010 / pib_real_2010_base
    estado['pib_real_base2010'] = estado['pib_real_2023'] * fator

    estado['cresc_nominal_pct'] = estado['pib_nominal'].pct_change() * 100
    estado['cresc_real_pct'] = estado['pib_real_base2010'].pct_change() * 100

    return estado.sort_values('ano').reset_index(drop=True)
