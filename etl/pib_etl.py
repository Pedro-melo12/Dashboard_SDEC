"""
etl/pib_etl.py
==============
Lê o PIB dos municípios de Pernambuco fornecido pela SEPLAG-PE em duas
fontes complementares:

1) Tabelas históricas 2010-2021 (XLS, multi-tabelas):
   - Tabela 4: Participação dos municípios nos VAB setoriais das RDs
   - Tabela 5: PIB per capita dos municípios e das RDs
   - Tabela 6: VAB Total, Impostos e PIB em valores correntes
   - Tabela 7: Participação no total estadual
   - Tabela 8: Participação no total da RD

2) PIB 2022 e 2023 (PDF):
   Uma tabela simples com Município → PIB(2022), PIB(2023) e outra com
   PIB per capita.

Como rodar: python -m etl.pib_etl

Outputs:
    data/processed/pib_municipal.parquet
        cod_ibge_6, municipio, ano, pib, vab_total, impostos,
        pib_per_capita, regiao_desenvolvimento

A tabela é "long" (1 linha por município × ano). A integração com o RD
oficial (já carregado em municipios_rd.parquet) é feita no merge final.
"""

import pandas as pd
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_RAW, DATA_PROCESSED
from etl._aliases import normaliza_municipio


INPUT_XLS = DATA_RAW / "PIB_PE_2010_2021.xls"
INPUT_PDF = DATA_RAW / "PIB_PE_2022_2023.pdf"
INPUT_IPCA = DATA_RAW / "ipca_anual.csv"
INPUT_VAB_ABS = DATA_RAW / "VAB_setorial_absoluto.xls"
OUTPUT = DATA_PROCESSED / "pib_municipal.parquet"
OUTPUT_VAB_SETORIAL = DATA_PROCESSED / "pib_vab_setorial.parquet"
OUTPUT_VAB_ABSOLUTO = DATA_PROCESSED / "vab_setorial_absoluto.parquet"


# Lista das 12 RDs como aparecem no XLS da SEPLAG (para identificar
# linhas agregadoras). Algumas têm prefixo "Sertão" no XLS mas não na
# planilha de RDs oficial, então normalizamos depois.
RDS_NO_XLS = [
    'Agreste Central', 'Agreste Meridional', 'Agreste Setentrional',
    'Mata Norte', 'Mata Sul', 'Metropolitana',
    'Sertão Central', 'Sertão de Itaparica', 'Sertão do Araripe',
    'Sertão do Moxotó', 'Sertão do Pajeú', 'Sertão do São Francisco',
]

# Mapeamento RD do XLS -> nome canônico usado no município_rd.parquet
RD_ALIASES = {
    'Sertão de Itaparica': 'Itaparica',
    'Sertão do Araripe': 'do Araripe',
    'Sertão do Moxotó': 'Moxotó',
    'Sertão do Pajeú': 'Pajeú',
    'Sertão do São Francisco': 'do São Francisco',
}


def _to_float(v, eh_decimal: bool = False):
    """
    Converte valor (str ou número) para float, tratando '-' como NaN.

    eh_decimal : se True, o número é decimal por natureza (ex: PIB per
        capita 19.724,98). Se False (default), pontos são separadores
        de milhar (ex: 60.078.764 = 60 milhões e tantos).

    Casos cobertos:
      "60.078.764"   -> 60078764     (eh_decimal=False)
      "624.055"      -> 624055       (eh_decimal=False)
      "19.724,98"    -> 19724.98     (eh_decimal=True ou auto-detect com vírgula)
      "1.234,56"     -> 1234.56      (eh_decimal=True)
      "770,76"       -> 770.76       (sempre, vírgula = decimal)
      0.027665       -> 0.027665     (já é float)
    """
    if pd.isna(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in ('-', '', '...'):
        return None

    if ',' in s:
        # Vírgula = decimal BR. Pontos (se houver) = milhar.
        s = s.replace('.', '').replace(',', '.')
    elif eh_decimal:
        # Marcado como decimal mas sem vírgula = número simples já em float
        pass
    elif s.count('.') >= 1 and not eh_decimal:
        # Sem vírgula + tem ponto + NÃO é decimal = milhar BR ("60.078.764")
        s = s.replace('.', '')

    try:
        return float(s)
    except ValueError:
        return None


def _ler_tabela_6(path: Path) -> pd.DataFrame:
    """
    Lê Tabela 6 (VAB Total, Impostos, PIB) e retorna um DataFrame long:
        nome | ano | vab_total | impostos | pib

    A planilha mistura linhas de RDs (totais agregados) com municípios.
    Identificamos as RDs por nome e descartamos elas, ficando só com
    municípios.
    """
    df = pd.read_excel(path, sheet_name='Tabela 6', header=[1, 2])
    # Achatar header multi-nivel
    df.columns = [
        '_'.join(str(x) for x in c).strip().replace('Unnamed: 0_level_0_', '')
        for c in df.columns
    ]
    df = df.rename(columns={'RD/Município': 'nome'})

    # Manter só linhas com nome (corta cabeçalhos vazios e rodapé)
    df = df[df['nome'].notna()].copy()
    df['nome'] = df['nome'].astype(str).str.strip()

    # Remover linhas de "Fonte:" e notas
    df = df[~df['nome'].str.startswith(('Fonte', '*'))]

    # Pivot longo - cada (nome, ano) vira uma linha
    # Os valores no XLS vêm em R$ 1.000, então multiplicamos por 1.000
    # para ficar coerente com o PDF (que também é convertido).
    long_rows = []
    anos = list(range(2010, 2022))
    for _, row in df.iterrows():
        nome = row['nome']
        for ano in anos:
            vab = _to_float(row.get(f'{ano}_VAB Total'))
            imp = _to_float(row.get(f'{ano}_Impostos'))
            pib = _to_float(row.get(f'{ano}_PIB'))
            if vab is None and pib is None:
                continue
            long_rows.append({
                'nome': nome, 'ano': ano,
                'vab_total': vab * 1000 if vab is not None else None,
                'impostos': imp * 1000 if imp is not None else None,
                'pib': pib * 1000 if pib is not None else None,
            })

    return pd.DataFrame(long_rows)


def _ler_tabela_5_per_capita(path: Path) -> pd.DataFrame:
    """
    Tabela 5 - PIB per capita por município/RD (em R$).
    Retorna long: nome, ano, pib_per_capita.
    """
    df = pd.read_excel(path, sheet_name='Tabela 5', header=1)
    df = df.rename(columns={'RD/Município': 'nome'})
    df = df[df['nome'].notna()].copy()
    df['nome'] = df['nome'].astype(str).str.strip()
    df = df[~df['nome'].str.startswith(('Fonte', '*'))]

    long_rows = []
    for _, row in df.iterrows():
        nome = row['nome']
        for ano in range(2010, 2022):
            v = _to_float(row.get(ano))
            if v is None:
                continue
            long_rows.append({'nome': nome, 'ano': ano, 'pib_per_capita': v})

    return pd.DataFrame(long_rows)


def _ler_pdf_2022_2023() -> pd.DataFrame:
    """
    O PDF de 2022/2023 traz duas tabelas: PIB total (R$ 1.000) e PIB per
    capita (R$). Vamos usar pdfplumber para extrair texto e parsear.

    Schema: nome, ano, pib (R$, não em mil), pib_per_capita
    """
    try:
        import pdfplumber
    except ImportError:
        print("[PIB] AVISO: pdfplumber não instalado, pulando 2022/2023")
        return pd.DataFrame()

    rows_pib = {}
    rows_pc = {}
    secao = None  # 'pib' ou 'pc'

    with pdfplumber.open(INPUT_PDF) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split('\n'):
                if 'PIB dos Municípios' in line and 'R$ 1.000' in line:
                    secao = 'pib'
                    continue
                if 'PIB per Capita' in line:
                    secao = 'pc'
                    continue
                if secao is None:
                    continue
                # Linha tipo: "Abreu e Lima 1.942.161 2.129.775"
                # ou: "Cabo de Santo Agostinho 14.474.714 15.897.620"
                # ou per capita: "Abreu e Lima 19.724,98 21.630,43"
                m = re.match(r'^(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$', line.strip())
                if not m:
                    continue
                nome = m.group(1).strip()
                # Pular cabeçalhos/notas
                if nome in ('Município', 'Municípios') or 'Fonte' in nome:
                    continue
                v22 = _to_float(m.group(2), eh_decimal=(secao == 'pc'))
                v23 = _to_float(m.group(3), eh_decimal=(secao == 'pc'))
                if v22 is None or v23 is None:
                    continue
                if secao == 'pib':
                    # Valores estão em R$ 1.000 - converter para reais
                    rows_pib[(nome, 2022)] = v22 * 1000
                    rows_pib[(nome, 2023)] = v23 * 1000
                else:
                    rows_pc[(nome, 2022)] = v22
                    rows_pc[(nome, 2023)] = v23

    long = []
    nomes_munis = set(k[0] for k in rows_pib.keys())
    for nome in nomes_munis:
        for ano in (2022, 2023):
            row = {
                'nome': nome, 'ano': ano,
                'pib': rows_pib.get((nome, ano)),
                'pib_per_capita': rows_pc.get((nome, ano)),
            }
            long.append(row)
    return pd.DataFrame(long)


def _calcular_deflator_ipca(ano_base: int = 2023) -> dict:
    """
    Lê IPCA anual e calcula o deflator para trazer cada ano ao ano-base.

    Retorna dict {ano: deflator}, onde:
        PIB_real(ano) = PIB_nominal(ano) × deflator(ano)
        PIB_real(ano_base) = PIB_nominal(ano_base) (deflator = 1)

    Para anos anteriores ao base, deflator > 1 (corrige inflação acumulada).
    Para anos posteriores ao base, deflator < 1 (raro, ignorado aqui).
    """
    df_ipca = pd.read_csv(INPUT_IPCA)
    ipca = dict(zip(df_ipca['ano'], df_ipca['ipca_pct']))

    deflatores = {ano_base: 1.0}
    # Para trás: vai acumulando inflação
    fator = 1.0
    for ano in range(ano_base - 1, min(ipca.keys()) - 1, -1):
        # IPCA do ano (ano+1) já foi aplicado no fator
        # Para trazer ano X ao ano_base: multiplicamos pela inflação
        # acumulada de X+1 até ano_base
        inflacao_ano_seguinte = ipca.get(ano + 1, 0) / 100
        fator *= (1 + inflacao_ano_seguinte)
        deflatores[ano] = fator

    return deflatores


def _ler_tabela_4_vab_setorial(path: Path) -> pd.DataFrame:
    """
    Tabela 4 - Participação dos municípios nos VAB setoriais das RDs.
    Cada município contribui com X% do VAB de cada setor de SUA RD.
    A RD em si tem valor 1.0 em cada coluna (somatório dos municípios).

    Retorna long: nome, ano, setor, participacao (em [0, 1])
    """
    df = pd.read_excel(path, sheet_name='Tabela 4', header=[1, 2])
    df.columns = [
        '_'.join(str(x) for x in c).strip().replace('Unnamed: 0_level_0_', '')
        for c in df.columns
    ]
    df = df.rename(columns={'RD/Município': 'nome'})
    df = df[df['nome'].notna()].copy()
    df['nome'] = df['nome'].astype(str).str.strip()
    df = df[~df['nome'].str.startswith(('Fonte', '*'))]

    setores_xls = [
        ('VAB Agropecuária', 'agropecuaria'),
        ('VAB Indústria', 'industria'),
        ('VAB Serviços exclusive APU', 'servicos'),
        ('VAB APU', 'apu'),
    ]

    long_rows = []
    for _, row in df.iterrows():
        nome = row['nome']
        for ano in range(2010, 2022):
            for col_xls, setor in setores_xls:
                v = _to_float(row.get(f'{ano}_{col_xls}'))
                if v is None:
                    continue
                long_rows.append({
                    'nome': nome, 'ano': ano, 'setor': setor,
                    'participacao': v,  # fração [0, 1]
                })
    return pd.DataFrame(long_rows)


def _processar_vab_setorial() -> pd.DataFrame:
    """
    Processa Tabela 4 do XLS e devolve DataFrame com:
        cod_ibge_6, municipio, ano, setor, participacao_na_rd,
        regiao_desenvolvimento

    Não inclui as linhas de RD (essas têm valor 1.0 em cada setor).
    """
    df = _ler_tabela_4_vab_setorial(INPUT_XLS)

    # Remover linhas de RD (totais)
    df = df[~df['nome'].isin(RDS_NO_XLS)].copy()
    df = df[df['nome'] != 'Total'].copy()

    # Cruzar com CAGED
    caged = pd.read_parquet(DATA_PROCESSED / 'caged_municipal.parquet')
    caged_map = caged[['cod_ibge_6', 'municipio']].drop_duplicates()
    caged_map['key'] = caged_map['municipio'].apply(normaliza_municipio)
    df['key'] = df['nome'].apply(normaliza_municipio)
    merged = df.merge(caged_map, on='key', how='left')

    merged = merged.dropna(subset=['cod_ibge_6']).copy()
    merged['cod_ibge_6'] = merged['cod_ibge_6'].astype(int)

    rd = pd.read_parquet(DATA_PROCESSED / 'municipios_rd.parquet')
    merged = merged.merge(
        rd[['cod_ibge_6', 'regiao_desenvolvimento']],
        on='cod_ibge_6', how='left',
    )

    return merged[['cod_ibge_6', 'municipio', 'ano', 'setor',
                   'participacao', 'regiao_desenvolvimento']].rename(
        columns={'participacao': 'participacao_na_rd'}
    ).reset_index(drop=True)


def _processar_vab_absoluto() -> pd.DataFrame:
    """
    Lê Tabela 1 do VBA_PE: VAB ABSOLUTO por setor por município.

    Para cada (município, ano) temos VAB_Agropecuária, VAB_Indústria,
    VAB_Serviços, VAB_APU - tudo em R$ (não em milhares).

    A soma dos 4 setores deve bater com vab_total da Tabela 6 do PIB.

    Retorna long: cod_ibge_6, municipio, ano, setor, vab,
                  regiao_desenvolvimento
    """
    df = pd.read_excel(INPUT_VAB_ABS, sheet_name='Tabela 1', header=[1, 2])
    df.columns = ['_'.join(str(x) for x in c).strip() for c in df.columns]
    df = df.rename(columns={'Unnamed: 1_level_0_RD/Município': 'nome'})
    df = df[df['nome'].notna()].copy()
    df['nome'] = df['nome'].astype(str).str.strip()
    df = df[~df['nome'].str.startswith(('Fonte', '*'))]

    setores_xls = [
        ('VAB Agropecuária', 'agropecuaria'),
        ('VAB Indústria', 'industria'),
        ('VAB Serviços exclusive APU', 'servicos'),
        ('VAB APU', 'apu'),
    ]

    # Long: 1 linha por (nome, ano, setor)
    long_rows = []
    for _, row in df.iterrows():
        nome = row['nome']
        for ano in range(2010, 2022):
            for col_xls, setor in setores_xls:
                v = _to_float(row.get(f'{ano}_{col_xls}'))
                if v is None:
                    continue
                long_rows.append({
                    'nome': nome, 'ano': ano, 'setor': setor,
                    'vab': v * 1000,  # arquivo está em R$ 1.000
                })
    long_df = pd.DataFrame(long_rows)

    # Remover linhas das RDs (totais) - vamos calcular agregando os
    # municípios pra ficar consistente
    long_df = long_df[~long_df['nome'].isin(RDS_NO_XLS)].copy()
    long_df = long_df[long_df['nome'] != 'Total'].copy()

    # Cruzar com CAGED
    caged = pd.read_parquet(DATA_PROCESSED / 'caged_municipal.parquet')
    caged_map = caged[['cod_ibge_6', 'municipio']].drop_duplicates()
    caged_map['key'] = caged_map['municipio'].apply(normaliza_municipio)
    long_df['key'] = long_df['nome'].apply(normaliza_municipio)
    merged = long_df.merge(caged_map, on='key', how='left')

    merged = merged.dropna(subset=['cod_ibge_6']).copy()
    merged['cod_ibge_6'] = merged['cod_ibge_6'].astype(int)

    # Pombos: mesma deduplicação do PIB (tem entrada com asterisco e sem)
    # Para VAB, valores são iguais nos dois - mantemos um só.
    merged = merged.drop_duplicates(
        subset=['cod_ibge_6', 'ano', 'setor'], keep='first'
    )

    rd = pd.read_parquet(DATA_PROCESSED / 'municipios_rd.parquet')
    merged = merged.merge(
        rd[['cod_ibge_6', 'regiao_desenvolvimento']],
        on='cod_ibge_6', how='left',
    )

    return merged[['cod_ibge_6', 'municipio', 'ano', 'setor', 'vab',
                   'regiao_desenvolvimento']].reset_index(drop=True)


def main():
    print("[PIB] Lendo Tabela 6 (VAB Total, Impostos, PIB)...")
    df_pib = _ler_tabela_6(INPUT_XLS)
    print(f"      {len(df_pib)} registros (município × ano)")

    print("[PIB] Lendo Tabela 5 (PIB per capita)...")
    df_pc = _ler_tabela_5_per_capita(INPUT_XLS)
    print(f"      {len(df_pc)} registros")

    # Mesclar PIB + per capita (2010-2021)
    df_2010_2021 = df_pib.merge(df_pc, on=['nome', 'ano'], how='left')
    print(f"      total 2010-2021 mesclado: {len(df_2010_2021)} linhas")

    # Adicionar 2022/2023 do PDF
    print("[PIB] Lendo PDF 2022-2023...")
    df_2223 = _ler_pdf_2022_2023()
    if not df_2223.empty:
        # PDF não tem VAB nem impostos
        df_2223['vab_total'] = None
        df_2223['impostos'] = None
        print(f"      {len(df_2223)} registros (2022, 2023)")
    else:
        print(f"      vazio (pdfplumber pode não estar instalado)")

    # Concatenar
    df_total = pd.concat([df_2010_2021, df_2223], ignore_index=True)

    # Remover RDs (queremos só municípios, agregação será calculada)
    df_total = df_total[~df_total['nome'].isin(RDS_NO_XLS)].copy()
    # Remover linha "Total" (estado todo) também
    df_total = df_total[df_total['nome'] != 'Total'].copy()
    print(f"      após remover linhas-RD: {len(df_total)} registros")

    # Cruzar com CAGED para pegar cod_ibge_6
    caged = pd.read_parquet(DATA_PROCESSED / 'caged_municipal.parquet')
    caged_map = caged[['cod_ibge_6', 'municipio']].drop_duplicates()
    caged_map['key'] = caged_map['municipio'].apply(normaliza_municipio)

    df_total['key'] = df_total['nome'].apply(normaliza_municipio)
    merged = df_total.merge(caged_map, on='key', how='left')

    nao_casados = merged[merged['cod_ibge_6'].isna()]['nome'].unique()
    if len(nao_casados):
        print(f"[PIB] AVISO: {len(nao_casados)} municípios sem match com CAGED:")
        for n in sorted(nao_casados)[:20]:
            print(f"      - {n!r}")

    merged = merged.dropna(subset=['cod_ibge_6']).copy()
    merged['cod_ibge_6'] = merged['cod_ibge_6'].astype(int)

    # Adicionar RD oficial via municipios_rd.parquet
    rd = pd.read_parquet(DATA_PROCESSED / 'municipios_rd.parquet')
    merged = merged.merge(
        rd[['cod_ibge_6', 'regiao_desenvolvimento']],
        on='cod_ibge_6', how='left',
    )

    final = merged[[
        'cod_ibge_6', 'municipio', 'ano',
        'pib', 'vab_total', 'impostos', 'pib_per_capita',
        'regiao_desenvolvimento',
    ]].sort_values(['ano', 'cod_ibge_6']).reset_index(drop=True)

    # Pombos aparece duas vezes em 2019-2021 (mudou de RD em 2018, com
    # asterisco no nome no período de transição). Consolidamos: para
    # cada (cod_ibge_6, ano), pegamos a linha com pib_per_capita > 0.
    # Isso porque o asterisco gera uma linha "fantasma" com pc=0.
    final = (final
             .sort_values(['cod_ibge_6', 'ano', 'pib_per_capita'],
                          ascending=[True, True, False])
             .drop_duplicates(subset=['cod_ibge_6', 'ano'], keep='first')
             .sort_values(['ano', 'cod_ibge_6'])
             .reset_index(drop=True))

    # Calcular PIB real (deflacionado pelo IPCA, ano-base = 2023)
    print("[PIB] Aplicando deflator IPCA (ano-base 2023)...")
    deflatores = _calcular_deflator_ipca(ano_base=2023)
    final['deflator_ipca'] = final['ano'].map(deflatores)
    final['pib_real_2023'] = final['pib'] * final['deflator_ipca']
    final['pib_per_capita_real_2023'] = (
        final['pib_per_capita'] * final['deflator_ipca']
    )

    # Calcular dependência de impostos (% do PIB)
    final['dependencia_impostos_pct'] = (
        100 * final['impostos'] / final['pib']
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    final.to_parquet(OUTPUT, index=False)

    print()
    print(f"[PIB] {len(final)} linhas finais (PIB nominal e real)")
    print(f"[PIB] Cobertura por ano:")
    for ano, n in final.groupby('ano').size().items():
        print(f"        {ano}: {n} municípios")
    print(f"[PIB] Top 5 PIB 2023:")
    sub = final[final['ano'] == 2023].nlargest(5, 'pib')
    for _, r in sub.iterrows():
        print(f"        {r['municipio']:30s} R$ {r['pib']/1e9:.2f} bi")
    print(f"[PIB] Gerado: {OUTPUT.name}")

    # Comparação nominal vs real - amostra
    print(f"[PIB] Crescimento estadual nominal vs real:")
    estado = final.groupby('ano').agg(
        pib_nominal=('pib', 'sum'),
        pib_real=('pib_real_2023', 'sum'),
    ).reset_index()
    estado['cresc_nominal'] = estado['pib_nominal'].pct_change() * 100
    estado['cresc_real'] = estado['pib_real'].pct_change() * 100
    for _, r in estado.tail(5).iterrows():
        print(f"        {int(r['ano'])}: nominal {r['cresc_nominal']:+.1f}%, "
              f"real {r['cresc_real']:+.1f}%")

    # ============================================================
    # VAB Setorial - Tabela 4 (participação relativa dentro da RD)
    # ============================================================
    print()
    print("[PIB] Processando Tabela 4 (participação dos municípios no VAB da RD)...")
    df_vab = _processar_vab_setorial()
    df_vab.to_parquet(OUTPUT_VAB_SETORIAL, index=False)
    print(f"[PIB] {len(df_vab)} linhas de VAB setorial (relativo)")
    print(f"[PIB] Gerado: {OUTPUT_VAB_SETORIAL.name}")

    # ============================================================
    # VAB Setorial ABSOLUTO - Tabela 1 do VBA_PE
    # ============================================================
    print()
    print("[PIB] Processando Tabela 1 do VBA_PE (VAB absoluto por setor)...")
    df_abs = _processar_vab_absoluto()
    df_abs.to_parquet(OUTPUT_VAB_ABSOLUTO, index=False)
    print(f"[PIB] {len(df_abs)} linhas de VAB absoluto")
    print(f"[PIB] Setores: {sorted(df_abs['setor'].unique().tolist())}")
    print(f"[PIB] Período: {df_abs['ano'].min()}-{df_abs['ano'].max()}")

    # Validação: para Caruaru 2021, soma dos setores deve = vab_total
    val = df_abs[(df_abs['municipio'] == 'Caruaru') & (df_abs['ano'] == 2021)]
    if not val.empty:
        soma = val['vab'].sum()
        pib_caruaru = final[(final['municipio'] == 'Caruaru')
                            & (final['ano'] == 2021)]
        if not pib_caruaru.empty:
            vab_ref = float(pib_caruaru['vab_total'].iloc[0])
            diff = abs(soma - vab_ref)
            print(f"[PIB] Validação Caruaru 2021: "
                  f"soma setores R$ {soma/1e9:.3f} bi vs "
                  f"vab_total R$ {vab_ref/1e9:.3f} bi "
                  f"(diferença R$ {diff:.0f})")
    print(f"[PIB] Gerado: {OUTPUT_VAB_ABSOLUTO.name}")


if __name__ == '__main__':
    main()
