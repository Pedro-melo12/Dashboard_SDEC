"""
etl/pnad_regional_etl.py
========================
Consolida 8 bases trimestrais (2012-T1 a 2025-T3) para os 9 estados do
Nordeste + Nordeste consolidado:

    DESOCUPADOS, OCUPADOS, DESALENTADOS, FORÇA_DE_TRABALHO,
    FORA_DA_FORÇA_DE_TRABALHO, TAXA_DE_DESEMPREGO,
    RENDIMENTO_MEDIO_MENSAL, POBREZA

Formato do output (long):
    data, trimestre, ano, regiao, indicador, indicador_nome,
    valor, unidade

Saídas:
    data/processed/pnad_regional.parquet  -> 8 indicadores × 10 regiões
    data/processed/pobreza_regional.parquet -> só pobreza/extrema pobreza

Como rodar:
    python -m etl.pnad_regional_etl

Notas:
- Os arquivos têm o "Status" descrevendo o indicador, mas vem com
  códigos do PNAD (ex: "VD4001=2"). Usamos uma chave técnica limpa.
- Taxa de desemprego vem como string ("9,57%"). Normalizamos para float.
- População em pobreza vem em pessoas (não em milhares).
"""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_RAW, DATA_PROCESSED


PNAD_REGIONAL_DIR = DATA_RAW / "pnad_regional"
OUTPUT = DATA_PROCESSED / "pnad_regional.parquet"
OUTPUT_POBREZA = DATA_PROCESSED / "pobreza_regional.parquet"


# Mapeamento dos arquivos para metadados do indicador
INDICADORES = {
    'DESOCUPADOS.xlsx': {
        'chave': 'desocupados',
        'nome': 'Pessoas desocupadas',
        'unidade': 'pessoas',
    },
    'OCUPADOS.xlsx': {
        'chave': 'ocupados',
        'nome': 'Pessoas ocupadas',
        'unidade': 'pessoas',
    },
    'DESALENTADOS.xlsx': {
        'chave': 'desalentados',
        'nome': 'Pessoas desalentadas',
        'unidade': 'pessoas',
    },
    'FORÇA_DE_TRABALHO.xlsx': {
        'chave': 'forca_trabalho',
        'nome': 'Na força de trabalho',
        'unidade': 'pessoas',
    },
    'FORA_DA_FORÇA_DE_TRABALHO.xlsx': {
        'chave': 'fora_forca',
        'nome': 'Fora da força de trabalho',
        'unidade': 'pessoas',
    },
    'TAXA_DE_DESEMPREGO.xlsx': {
        'chave': 'taxa_desemprego',
        'nome': 'Taxa de desemprego',
        'unidade': '%',
    },
    'RENDIMENTO_MEDIO_MENSAL.xlsx': {
        'chave': 'rendimento_medio',
        'nome': 'Rendimento médio mensal',
        'unidade': 'R$',
    },
}


def _trimestre_para_data(ano: int, trimestre: int) -> pd.Timestamp:
    """
    Converte (ano, trimestre) em uma Timestamp do último mês do trimestre.
    Convenção do IBGE: T1 termina em março, T2 em junho, T3 em setembro,
    T4 em dezembro.
    """
    mes_final = trimestre * 3
    return pd.Timestamp(year=ano, month=mes_final, day=1)


def _normalizar_valor(v, unidade: str) -> float:
    """
    Converte valor (que pode vir como string com vírgula/pct) em float.

    A regra para números BR é simples mas tem armadilhas:
    - "9,57%" (taxa)         -> 9.57
    - "1.234,56" (rendimento) -> 1234.56
    - "59.603" (pessoas, sem vírgula) -> 59603 (NÃO 59.603!)
    - "3.731.164" (pessoas) -> 3731164
    - 770.76 (já é float)    -> 770.76 (deixa quieto)

    A chave: se a unidade NÃO É decimal por natureza (pessoas) e a
    string só tem pontos (sem vírgula), todos os pontos são separadores
    de milhar, NÃO casas decimais.
    """
    if pd.isna(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)

    s = str(v).strip().replace('%', '').replace(' ', '')

    if unidade == '%':
        # Formato "9,57%" -> 9.57
        s = s.replace(',', '.')
    elif unidade == 'pessoas':
        # SEMPRE inteiro: pontos são separadores de milhar
        s = s.replace('.', '')
        s = s.replace(',', '.')  # caso muito raro de vírgula
    else:
        # Rendimento (R$): pode ter decimal e milhar.
        # "1.234,56" -> 1234.56 (BR padrão)
        # "770,76" -> 770.76 (sem milhar)
        # "1234.56" -> 1234.56 (US, raro)
        if ',' in s and '.' in s:
            # BR: ponto = milhar, vírgula = decimal
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            # Só vírgula = decimal BR
            s = s.replace(',', '.')
        # Se só tem ponto, deixamos: pode ser US decimal "1234.56".
        # No caso da nossa PNAD, o rendimento sempre vem com vírgula
        # decimal, então essa branch raramente ativa.

    try:
        return float(s)
    except ValueError:
        return None


def processar_indicador(arquivo: str, meta: dict) -> pd.DataFrame:
    """Lê um arquivo e padroniza ao schema final."""
    path = PNAD_REGIONAL_DIR / arquivo
    df = pd.read_excel(path, sheet_name='Planilha1')

    # Normalizar colunas (snake_case)
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns={'região': 'regiao', 'regiao': 'regiao'})

    # Converter valor e construir data
    df['valor'] = df['valor'].apply(lambda v: _normalizar_valor(v, meta['unidade']))
    df['data'] = df.apply(
        lambda r: _trimestre_para_data(int(r['ano']), int(r['trimestre'])),
        axis=1,
    )
    df['trimestre_label'] = df.apply(
        lambda r: f"{int(r['ano'])}-T{int(r['trimestre'])}",
        axis=1,
    )

    df['indicador'] = meta['chave']
    df['indicador_nome'] = meta['nome']
    df['unidade'] = meta['unidade']

    return df[['data', 'trimestre_label', 'ano', 'trimestre', 'regiao',
               'indicador', 'indicador_nome', 'valor', 'unidade']]


def processar_pobreza() -> pd.DataFrame:
    """
    Pobreza tem schema ligeiramente diferente: coluna Categoria em vez
    de Status, e valor é Pop_Ponderada (pessoas). Processamos à parte.
    """
    df = pd.read_excel(PNAD_REGIONAL_DIR / 'POBREZA.xlsx', sheet_name='Pobreza')
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns={
        'região': 'regiao',
        'pop_ponderada': 'valor',
        'categoria': 'categoria',
    })

    df['data'] = df.apply(
        lambda r: _trimestre_para_data(int(r['ano']), int(r['trimestre'])),
        axis=1,
    )
    df['trimestre_label'] = df.apply(
        lambda r: f"{int(r['ano'])}-T{int(r['trimestre'])}",
        axis=1,
    )

    # Padronizar nomes: "Extrema_Pobreza" -> "extrema_pobreza"
    df['indicador'] = df['categoria'].str.lower()

    nomes_legiveis = {
        'extrema_pobreza': 'Em extrema pobreza',
        'pobreza': 'Em situação de pobreza',
    }
    df['indicador_nome'] = df['indicador'].map(nomes_legiveis)
    df['unidade'] = 'pessoas'

    return df[['data', 'trimestre_label', 'ano', 'trimestre', 'regiao',
               'indicador', 'indicador_nome', 'valor', 'unidade']]


def main():
    print("[PNAD-REG] Processando indicadores regionais...")
    dfs = []
    for arquivo, meta in INDICADORES.items():
        try:
            d = processar_indicador(arquivo, meta)
            print(f"           {meta['chave']:18s} {len(d):4d} registros")
            dfs.append(d)
        except Exception as e:
            print(f"           ✗ ERRO em {arquivo}: {e}")

    consolidado = pd.concat(dfs, ignore_index=True)
    consolidado = consolidado.sort_values(
        ['indicador', 'regiao', 'data']
    ).reset_index(drop=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    consolidado.to_parquet(OUTPUT, index=False)

    regioes = consolidado['regiao'].unique().tolist()
    print()
    print(f"[PNAD-REG] {len(consolidado):,} linhas consolidadas")
    print(f"[PNAD-REG] {len(regioes)} regiões: {', '.join(regioes)}")
    print(f"[PNAD-REG] Período: "
          f"{consolidado['trimestre_label'].min()} a "
          f"{consolidado['trimestre_label'].max()}")
    print(f"[PNAD-REG] Gerado: {OUTPUT.name}")

    print()
    print("[POBREZA] Processando pobreza/extrema pobreza...")
    df_pob = processar_pobreza()
    df_pob.to_parquet(OUTPUT_POBREZA, index=False)
    print(f"[POBREZA] {len(df_pob):,} registros, "
          f"{df_pob['regiao'].nunique()} regiões, "
          f"período {df_pob['trimestre_label'].min()} a "
          f"{df_pob['trimestre_label'].max()}")
    print(f"[POBREZA] Gerado: {OUTPUT_POBREZA.name}")


if __name__ == '__main__':
    main()
