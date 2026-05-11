"""
etl/run_all.py
==============
Orquestrador. Roda todos os ETLs em ordem e gera o catálogo de dados.

O catálogo (data/processed/catalogo.json) é o "manifesto" do
observatório: lista cada dataset, sua fonte, quando foi atualizado pela
última vez, e quais campos tem. É a base para futuras funcionalidades
como "mostrar no dashboard quando os dados foram atualizados" ou
"avisar quando uma fonte está desatualizada há mais de N dias".

Como rodar:
    python -m etl.run_all
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    CAGED_MUNICIPAL, CAGED_GENERO, CAGED_SETOR, PNAD_PE,
    GEO_MUNICIPIOS, CATALOGO,
)
from etl import (caged_etl, pnad_etl, geo_etl, setor_etl,
                 pnad_regional_etl, rd_etl, prefeitos_etl, pib_etl)


def gerar_catalogo():
    """
    Gera o catálogo de metadados dos datasets processados.
    Para cada arquivo, registra: nome, caminho, tamanho, data de geração.
    """
    import pandas as pd

    from config import (
        CAGED_MUNICIPAL, CAGED_GENERO, CAGED_SETOR, PNAD_PE,
        PNAD_REGIONAL, POBREZA_REGIONAL,
        MUNICIPIOS_RD, PREFEITOS, VEREADORES,
        PIB_MUNICIPAL,
        GEO_MUNICIPIOS, CATALOGO,
    )

    catalogo = {
        'gerado_em': datetime.now().isoformat(timespec='seconds'),
        'datasets': []
    }

    arquivos = [
        (CAGED_MUNICIPAL, 'CAGED por município',
         'Novo CAGED · MTE/SE', 'mensal'),
        (CAGED_GENERO, 'CAGED por gênero (estadual)',
         'Novo CAGED · MTE/SE', 'mensal'),
        (CAGED_SETOR, 'CAGED por grande setor (estadual)',
         'Novo CAGED · MTE/SE', 'mensal'),
        (PNAD_PE, 'PNAD Contínua - Pernambuco',
         'PNAD Contínua · IBGE', 'trimestral'),
        (PNAD_REGIONAL, 'PNAD Contínua - 9 estados do NE',
         'PNAD Contínua · IBGE', 'trimestral'),
        (POBREZA_REGIONAL, 'Pobreza e extrema pobreza - regional',
         'PNAD Contínua · IBGE', 'trimestral'),
        (MUNICIPIOS_RD, 'Municípios × Regiões de Desenvolvimento',
         'SDEC · Governo de Pernambuco', 'estática'),
        (PREFEITOS, 'Prefeitos eleitos por município',
         'TSE · Eleições municipais', 'a cada 4 anos'),
        (VEREADORES, 'Vereadores eleitos por município',
         'TSE · Eleições municipais', 'a cada 4 anos'),
        (PIB_MUNICIPAL, 'PIB municipal de Pernambuco (2010-2023)',
         'SEPLAG-PE / IBGE · Sistema de Contas Regionais', 'anual'),
    ]

    for path, descricao, fonte, periodicidade in arquivos:
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        entry = {
            'arquivo': path.name,
            'descricao': descricao,
            'fonte': fonte,
            'periodicidade': periodicidade,
            'n_registros': len(df),
            'colunas': df.columns.tolist(),
            'tamanho_kb': round(path.stat().st_size / 1024, 1),
        }
        # Período coberto, se houver coluna data
        if 'data' in df.columns:
            entry['periodo_inicio'] = str(df['data'].min().date())
            entry['periodo_fim'] = str(df['data'].max().date())
        catalogo['datasets'].append(entry)

    if GEO_MUNICIPIOS.exists():
        catalogo['datasets'].append({
            'arquivo': GEO_MUNICIPIOS.name,
            'descricao': 'Malha territorial dos municípios de PE',
            'fonte': 'API de Malhas · IBGE',
            'periodicidade': 'estática',
            'tamanho_kb': round(GEO_MUNICIPIOS.stat().st_size / 1024, 1),
        })

    with open(CATALOGO, 'w', encoding='utf-8') as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=2)

    return catalogo


def main():
    print("=" * 60)
    print("OBSERVATÓRIO PE · ETL completo")
    print("=" * 60)
    print()

    geo_etl.main()
    print()
    caged_etl.main()
    print()
    pnad_etl.main()
    print()
    setor_etl.main()
    print()
    pnad_regional_etl.main()
    print()
    rd_etl.main()
    print()
    prefeitos_etl.main()
    print()
    pib_etl.main()
    print()

    print("[CAT] Gerando catálogo de metadados...")
    catalogo = gerar_catalogo()
    print(f"[CAT] {len(catalogo['datasets'])} datasets registrados")
    print(f"[CAT] Salvo: {CATALOGO.name}")
    print()
    print("✓ ETL concluído.")


if __name__ == '__main__':
    main()
