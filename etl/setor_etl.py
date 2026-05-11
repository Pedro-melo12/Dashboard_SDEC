"""
etl/setor_etl.py
================
ETL da base CAGED por setor (5 grandes setores: Agropecuária, Indústria,
Construção, Comércio, Serviços), nível estadual, mensal.

Fonte:
    data/raw/CAGED_SETOR_PE.xlsx

A base original tem uma única aba ('Página3') com colunas:
    DATA, CATEGORIA, ADMITIDOS, DEMITIDOS, SALDO, ESTOQUE, UF

Cuidado: a coluna ESTOQUE pode vir vazia em alguns períodos
(o MTE só publica estoque em determinados meses).

Saída:
    data/processed/caged_setor.parquet

Como rodar:
    python -m etl.setor_etl
"""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_RAW, DATA_PROCESSED


# Caminhos específicos deste ETL (também serão expostos no config.py)
SETOR_RAW = DATA_RAW / "CAGED_SETOR_PE.xlsx"
SETOR_PARQUET = DATA_PROCESSED / "caged_setor.parquet"


def main():
    print("[SETOR] Lendo CAGED_SETOR_PE.xlsx...")
    df = pd.read_excel(SETOR_RAW, sheet_name='Página3')

    # Normalizar nomes de coluna para snake_case
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns={
        'data': 'data',
        'categoria': 'setor',
        'admitidos': 'admissoes',
        'demitidos': 'desligamentos',
        'saldo': 'saldo',
        'estoque': 'estoque',
        'uf': 'uf',
    })

    # Garantir tipos
    df['data'] = pd.to_datetime(df['data'])
    # Normalizar pra primeiro dia do mês (evita ruído com dias 7, etc)
    df['data'] = df['data'].dt.to_period('M').dt.to_timestamp()

    df['ano'] = df['data'].dt.year
    df['mes'] = df['data'].dt.month

    df = df.sort_values(['data', 'setor']).reset_index(drop=True)

    # Selecionar colunas finais
    df = df[['data', 'ano', 'mes', 'uf', 'setor',
             'admissoes', 'desligamentos', 'saldo', 'estoque']]

    SETOR_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SETOR_PARQUET, index=False)

    setores_unicos = df['setor'].unique().tolist()
    print(f"[SETOR] {len(df):,} registros, {len(setores_unicos)} setores: "
          f"{', '.join(setores_unicos)}")
    print(f"[SETOR] Período: {df['data'].min().date()} a {df['data'].max().date()}")
    print(f"[SETOR] Gerado: {SETOR_PARQUET.name}")


if __name__ == '__main__':
    main()
