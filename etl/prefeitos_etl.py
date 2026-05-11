"""
etl/prefeitos_etl.py
====================
Lê o CSV de prefeitos/vereadores e gera dois parquets:

    data/processed/prefeitos.parquet
        cod_ibge_6, municipio, prefeito_nome, prefeito_partido, prefeito_genero
    data/processed/vereadores.parquet
        cod_ibge_6, municipio, vereador_nome, partido, genero

O CSV vem com mojibake duplo (UTF-8 lido como MacRoman) - corrigimos com
ftfy. Os nomes de municípios são normalizados via _aliases.

Como rodar: python -m etl.prefeitos_etl
"""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_RAW, DATA_PROCESSED
from etl._aliases import normaliza_municipio

try:
    import ftfy
    _has_ftfy = True
except ImportError:
    _has_ftfy = False


INPUT = DATA_RAW / "Prefeitos.csv"
OUTPUT_PREF = DATA_PROCESSED / "prefeitos.parquet"
OUTPUT_VER = DATA_PROCESSED / "vereadores.parquet"


def _fix(s):
    if pd.isna(s):
        return s
    if _has_ftfy:
        return ftfy.fix_text(str(s))
    return str(s)


def main():
    print("[PREF] Lendo CSV de prefeitos e vereadores...")
    df = pd.read_csv(INPUT, encoding='utf-8', sep=';')

    for col in ['Município', 'Nome', 'Partido']:
        df[col] = df[col].apply(_fix)

    df['key'] = df['Município'].apply(normaliza_municipio)

    caged = pd.read_parquet(DATA_PROCESSED / 'caged_municipal.parquet')
    caged_map = caged[['cod_ibge_6', 'municipio']].drop_duplicates()
    caged_map['key'] = caged_map['municipio'].apply(normaliza_municipio)

    merged = df.merge(caged_map, on='key', how='left',
                      suffixes=('_orig', ''))

    nao_casados = merged[merged['cod_ibge_6'].isna()]['Município'].unique()
    if len(nao_casados) > 0:
        print(f"[PREF] AVISO: municípios sem match com CAGED:")
        for m in sorted(nao_casados):
            print(f"      - {m!r}")

    merged = merged.dropna(subset=['cod_ibge_6']).copy()
    merged['cod_ibge_6'] = merged['cod_ibge_6'].astype(int)

    prefeitos = merged[merged['Cargo'] == 'PREFEITO'].copy()
    vereadores = merged[merged['Cargo'] == 'VEREADOR'].copy()

    prefeitos = prefeitos.rename(columns={
        'Nome': 'prefeito_nome',
        'Partido': 'prefeito_partido',
        'Genero': 'prefeito_genero',
    })[['cod_ibge_6', 'municipio', 'prefeito_nome',
         'prefeito_partido', 'prefeito_genero']]
    prefeitos = prefeitos.drop_duplicates(subset='cod_ibge_6')

    vereadores = vereadores.rename(columns={
        'Nome': 'vereador_nome',
        'Partido': 'partido',
        'Genero': 'genero',
    })[['cod_ibge_6', 'municipio', 'vereador_nome', 'partido', 'genero']]

    OUTPUT_PREF.parent.mkdir(parents=True, exist_ok=True)
    prefeitos.to_parquet(OUTPUT_PREF, index=False)
    vereadores.to_parquet(OUTPUT_VER, index=False)

    print(f"[PREF] {len(prefeitos)} prefeitos | {len(vereadores)} vereadores")
    print(f"[PREF] Top 5 partidos prefeitos:")
    for p, n in prefeitos['prefeito_partido'].value_counts().head().items():
        print(f"        {p:15s} {n:3d}")
    print(f"[PREF] Distribuição de gênero - prefeitos:")
    for g, n in prefeitos['prefeito_genero'].value_counts().items():
        pct = 100 * n / len(prefeitos)
        print(f"        {g:10s} {n:3d}  ({pct:.1f}%)")
    print(f"[PREF] Gerados: {OUTPUT_PREF.name}, {OUTPUT_VER.name}")


if __name__ == '__main__':
    main()
