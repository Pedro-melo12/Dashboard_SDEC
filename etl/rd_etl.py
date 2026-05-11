"""
etl/rd_etl.py
=============
Lê a planilha de Municípios × Regiões de Desenvolvimento (RD) e gera
um parquet relacionando cada município (via cod_ibge_6) com sua RD.

A planilha vem com a coluna RD mesclada (preenchida só na primeira linha
de cada bloco), então fazemos forward-fill antes de processar.

Output:
    data/processed/municipios_rd.parquet
    Colunas: cod_ibge_6, municipio, regiao_desenvolvimento

Como rodar: python -m etl.rd_etl
"""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_RAW, DATA_PROCESSED
from etl._aliases import normaliza_municipio


INPUT = DATA_RAW / "Municípios_RD_PE.xlsx"
OUTPUT = DATA_PROCESSED / "municipios_rd.parquet"


def main():
    print("[RD] Lendo planilha de Regiões de Desenvolvimento...")
    df = pd.read_excel(INPUT, sheet_name='Planilha1')

    # A planilha tem 2 colunas úteis (RD, Município) e umas vazias
    df = df.iloc[:, :2]
    df.columns = ['rd', 'municipio']

    # Forward-fill: coluna RD vem com células mescladas no Excel
    df['rd'] = df['rd'].ffill()

    # Limpar prefixo "RD " do nome
    df['rd'] = df['rd'].str.replace(r'^RD\s+', '', regex=True).str.strip()

    # Corrigir typo conhecido
    df['rd'] = df['rd'].replace({'Agreste Setrentrional': 'Agreste Setentrional'})

    # Match com CAGED via nome normalizado
    caged = pd.read_parquet(DATA_PROCESSED / 'caged_municipal.parquet')
    caged_map = caged[['cod_ibge_6', 'municipio']].drop_duplicates()
    caged_map['key'] = caged_map['municipio'].apply(normaliza_municipio)
    df['key'] = df['municipio'].apply(normaliza_municipio)
    merged = df.merge(caged_map[['cod_ibge_6', 'key']], on='key', how='left')

    nao_casados = merged[merged['cod_ibge_6'].isna()]
    if len(nao_casados) > 0:
        print(f"[RD] AVISO: {len(nao_casados)} municípios sem match com CAGED:")
        for _, r in nao_casados.iterrows():
            print(f"      - {r['municipio']!r} (key={r['key']!r})")

    final = merged.dropna(subset=['cod_ibge_6']).copy()
    final['cod_ibge_6'] = final['cod_ibge_6'].astype(int)
    final = final[['cod_ibge_6', 'municipio', 'rd']].rename(
        columns={'rd': 'regiao_desenvolvimento'}
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    final.to_parquet(OUTPUT, index=False)

    print(f"[RD] {len(final)} municípios mapeados em "
          f"{final['regiao_desenvolvimento'].nunique()} RDs")
    print(f"[RD] Distribuição:")
    for rd, n in final.groupby('regiao_desenvolvimento').size().sort_values(
        ascending=False).items():
        print(f"      {rd:30s} {n:3d}")
    print(f"[RD] Gerado: {OUTPUT.name}")


if __name__ == '__main__':
    main()
