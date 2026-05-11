"""
etl/pnad_etl.py
===============
Lê o arquivo PNAD_PE.xlsx (7 abas, uma por indicador) e produz um único
parquet em formato "long" (uma linha por trimestre × indicador).

Por que long? Porque é o formato natural para gráficos com múltiplas
séries no Plotly e para filtros dinâmicos. Em formato wide, adicionar
um novo indicador exigiria mudar o schema; em long, é só adicionar
linhas.

Schema final:
    data            -> último mês do trimestre (ex: 2024-03-01 para 1ºT/2024)
    trimestre       -> string legível (ex: "2024-T1")
    ano             -> ano numérico (útil para filtros)
    uf              -> "PE"
    indicador       -> chave técnica (ex: "taxa_desocupacao")
    indicador_nome  -> nome legível (ex: "Taxa de desocupação")
    valor           -> valor numérico
    unidade         -> unidade ("%", "pessoas", "R$")

Como rodar:
    python -m etl.pnad_etl
"""

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import PNAD_RAW, PNAD_PE


# Mapeamento aba -> (chave técnica, nome legível, unidade, multiplicador)
# multiplicador: a planilha tem "ocupados" em milhares; o original era em
# milhares de pessoas mas vem direto como "3512000" (3,5 milhões), então
# multiplicador = 1. Ajuste aqui se a fonte mudar.
INDICADORES = {
    'Saldo Ocupação': {
        'chave': 'ocupados',
        'nome': 'População ocupada',
        'unidade': 'pessoas',
        'mult': 1,
    },
    'Saldo Desocupação ': {  # atenção: tem espaço no fim no xlsx original
        'chave': 'desocupados',
        'nome': 'População desocupada',
        'unidade': 'pessoas',
        'mult': 1,
    },
    'Nivel de Ocupação': {
        'chave': 'nivel_ocupacao',
        'nome': 'Nível de ocupação',
        'unidade': '%',
        'mult': 1,
    },
    'Taxa de Desocupação': {
        'chave': 'taxa_desocupacao',
        'nome': 'Taxa de desocupação',
        'unidade': '%',
        'mult': 1,
    },
    'Informalidade': {
        'chave': 'informalidade',
        'nome': 'Taxa de informalidade',
        'unidade': '%',
        'mult': 1,
    },
    'Rendimento médio mensal': {
        'chave': 'rendimento_medio',
        'nome': 'Rendimento médio mensal',
        'unidade': 'R$',
        'mult': 1,
    },
    'Desalentados': {
        'chave': 'desalentados',
        'nome': 'Pessoas desalentadas',
        'unidade': 'pessoas',
        'mult': 1000,  # vem em milhares na planilha
    },
}


def trimestre_label(data: pd.Timestamp) -> str:
    """Converte 2024-03-01 -> '2024-T1', 2024-06-01 -> '2024-T2', etc."""
    q = (data.month - 1) // 3 + 1
    return f"{data.year}-T{q}"


def processar_aba(aba: str, meta: dict) -> pd.DataFrame:
    """Lê uma aba específica e padroniza o formato."""
    df = pd.read_excel(PNAD_RAW, sheet_name=aba)

    # Padronizar nomes de coluna (algumas têm espaço extra, capitalização)
    df.columns = [c.strip().lower() for c in df.columns]

    # Renomear para padrão técnico
    df = df.rename(columns={
        'região': 'uf',
        'regiao': 'uf',
        'trimestre': 'data',
        'valor': 'valor',
    })

    # As datas no original vêm como 2012-03-03, 2012-06-06, etc. Esse é o
    # padrão "último mês do trimestre" usado pelo IBGE em séries trimestrais.
    # Vamos normalizar para o primeiro dia desse mês final, que é uma boa
    # convenção para gráficos temporais.
    df['data'] = pd.to_datetime(df['data'])
    df['data'] = df['data'].dt.to_period('M').dt.to_timestamp()

    df['valor'] = df['valor'] * meta['mult']

    df['indicador'] = meta['chave']
    df['indicador_nome'] = meta['nome']
    df['unidade'] = meta['unidade']
    df['ano'] = df['data'].dt.year
    df['trimestre'] = df['data'].apply(trimestre_label)

    return df[['data', 'trimestre', 'ano', 'uf', 'indicador',
               'indicador_nome', 'valor', 'unidade']]


def main():
    print("[PNAD] Processando 7 indicadores...")
    dfs = []
    for aba, meta in INDICADORES.items():
        try:
            d = processar_aba(aba, meta)
            print(f"        {meta['chave']:20s} {len(d):4d} registros")
            dfs.append(d)
        except Exception as e:
            print(f"        ✗ ERRO em '{aba}': {e}")

    pnad = pd.concat(dfs, ignore_index=True)
    pnad = pnad.sort_values(['indicador', 'data']).reset_index(drop=True)

    # Aviso sobre Informalidade zerada (problema na fonte)
    inf = pnad[pnad['indicador'] == 'informalidade']
    if (inf['valor'] == 0).all():
        print()
        print("[PNAD] ⚠ AVISO: Indicador 'informalidade' está com todos os")
        print("[PNAD]   valores zerados na planilha. Será mantido no parquet")
        print("[PNAD]   mas o dashboard vai marcar como 'sem dados' até a")
        print("[PNAD]   correção da fonte.")

    PNAD_PE.parent.mkdir(parents=True, exist_ok=True)
    pnad.to_parquet(PNAD_PE, index=False)
    print()
    print(f"[PNAD] Gerado: {PNAD_PE.name} ({len(pnad)} linhas)")


if __name__ == '__main__':
    main()
