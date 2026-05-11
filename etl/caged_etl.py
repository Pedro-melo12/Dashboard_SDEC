
import pandas as pd
import sys
from pathlib import Path

# Adiciona a raiz do projeto ao sys.path para conseguir importar `config`
# quando este script é executado diretamente.
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CAGED_RAW, CAGED_MUNICIPAL, CAGED_GENERO


# Mapeia o nome do mês em português para número
MESES_PT = {
    'Janeiro': 1, 'Fevereiro': 2, 'Março': 3, 'Abril': 4,
    'Maio': 5, 'Junho': 6, 'Julho': 7, 'Agosto': 8,
    'Setembro': 9, 'Outubro': 10, 'Novembro': 11, 'Dezembro': 12,
}


def parse_data_pt(s: str) -> pd.Timestamp:
    """Converte 'Janeiro/2020' para Timestamp(2020-01-01)."""
    mes_str, ano = s.split('/')
    return pd.Timestamp(year=int(ano), month=MESES_PT[mes_str], day=1)


def processar_municipal() -> pd.DataFrame:
    """Lê a aba Plan1 (dados por município) e retorna DataFrame limpo."""
    df = pd.read_excel(CAGED_RAW, sheet_name='Plan1')

    # Renomear colunas para nomes técnicos (sem acentos, sem espaços).
    # Isso é importante porque vamos usar essas colunas em código.
    df.columns = [
        'uf', 'cod_ibge_6', 'municipio', 'admissoes',
        'desligamentos', 'saldo', 'var_relativa', 'data_str'
    ]

    # Converter data textual para datetime
    df['data'] = df['data_str'].apply(parse_data_pt)

    # Adicionar coluna ano e mes (úteis para filtros)
    df['ano'] = df['data'].dt.year
    df['mes'] = df['data'].dt.month

    # Garantir tipos corretos
    df['cod_ibge_6'] = df['cod_ibge_6'].astype(int)

    # Ordenar
    df = df.sort_values(['data', 'municipio']).reset_index(drop=True)

    # Selecionar e ordenar colunas finais
    return df[[
        'data', 'ano', 'mes', 'uf', 'cod_ibge_6', 'municipio',
        'admissoes', 'desligamentos', 'saldo', 'var_relativa'
    ]]


def processar_genero() -> pd.DataFrame:
    """Lê a aba Caged MF (dados estaduais por gênero)."""
    df = pd.read_excel(CAGED_RAW, sheet_name='Caged MF')

    # A coluna DATA está como serial number do Excel.
    # origin='1899-12-30' é o ponto zero do Excel.
    df['data'] = pd.to_datetime(df['DATA'], origin='1899-12-30', unit='D')
    # Normalizar para o primeiro dia do mês
    df['data'] = df['data'].dt.to_period('M').dt.to_timestamp()

    # Renomear (atenção: ADMISSÂO está com til diferente no original)
    df = df.rename(columns={
        'SEXO': 'sexo',
        'ADMISSÂO': 'admissoes',
        'DESLIGAMENTO': 'desligamentos',
        'SALDO': 'saldo',
        'UF': 'uf',
    })

    df['ano'] = df['data'].dt.year
    df['mes'] = df['data'].dt.month

    df = df.sort_values(['data', 'sexo']).reset_index(drop=True)

    return df[['data', 'ano', 'mes', 'uf', 'sexo',
               'admissoes', 'desligamentos', 'saldo']]


def main():
    print("[CAGED] Lendo aba Plan1 (municipal)...")
    df_mun = processar_municipal()
    print(f"        {len(df_mun):,} registros, "
          f"{df_mun['municipio'].nunique()} municípios, "
          f"período {df_mun['data'].min().date()} a {df_mun['data'].max().date()}")

    print("[CAGED] Lendo aba Caged MF (gênero)...")
    df_gen = processar_genero()
    print(f"        {len(df_gen):,} registros, "
          f"período {df_gen['data'].min().date()} a {df_gen['data'].max().date()}")

    # Garantir que a pasta processed existe
    CAGED_MUNICIPAL.parent.mkdir(parents=True, exist_ok=True)

    df_mun.to_parquet(CAGED_MUNICIPAL, index=False)
    df_gen.to_parquet(CAGED_GENERO, index=False)

    print(f"[CAGED] Gerado: {CAGED_MUNICIPAL.name}")
    print(f"[CAGED] Gerado: {CAGED_GENERO.name}")


if __name__ == '__main__':
    main()
