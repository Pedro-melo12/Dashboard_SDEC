"""
etl/geo_etl.py
==============
Baixa o GeoJSON dos municípios de Pernambuco direto do servidor do IBGE
e salva localmente.

Como rodar:
    python -m etl.geo_etl

Pontos importantes deste arquivo:
1. O servidor do IBGE costuma devolver gzip mesmo sem o cliente pedir,
   então detectamos isso pelo header e pelo magic byte.
2. A estrutura das features pode variar entre versões da API. Por isso
   tentamos múltiplas fontes para o código IBGE: properties.codarea,
   properties.CD_MUN, properties.GEOCODIGO, e finalmente feature.id.
3. Adicionamos `properties.cod_ibge_6` como STRING (e não int), porque
   o Plotly faz match texto-com-texto entre `locations` e `featureidkey`.
"""

import gzip
import json
import sys
import urllib.request
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import GEO_MUNICIPIOS, META


URL_IBGE = (
    f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{META['uf_codigo']}"
    f"?formato=application/vnd.geo+json&qualidade=intermediaria&intrarregiao=municipio"
)


def _descomprimir_se_preciso(raw: bytes, content_encoding: str) -> bytes:
    """
    Descomprime se o conteúdo veio em gzip ou deflate.
    Detecção dupla:
    1. Header HTTP `Content-Encoding`
    2. Magic bytes (0x1f 0x8b para gzip) - alguns servidores comprimem
       mesmo sem declarar no header (caso do IBGE).
    """
    if content_encoding == 'gzip' or raw[:2] == b'\x1f\x8b':
        return gzip.decompress(raw)
    if content_encoding == 'deflate':
        return zlib.decompress(raw)
    return raw


def baixar_geojson() -> dict:
    """Baixa e retorna o GeoJSON como dicionário Python."""
    print(f"[GEO] Baixando malha de PE do IBGE...")
    print(f"[GEO] URL: {URL_IBGE[:80]}...")

    req = urllib.request.Request(URL_IBGE, headers={
        'User-Agent': 'observatorio-pe/1.0 (Python urllib)',
        'Accept': 'application/json, application/vnd.geo+json',
        'Accept-Encoding': 'gzip, deflate',
    })

    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        encoding = resp.headers.get('Content-Encoding', '').lower()

    raw = _descomprimir_se_preciso(raw, encoding)
    data = json.loads(raw.decode('utf-8'))

    n_features = len(data.get('features', []))
    print(f"[GEO] Recebidas {n_features} features (municípios)")
    return data


def _extrair_codigo_ibge(feature: dict) -> str:
    """
    Tenta extrair o código IBGE de 7 dígitos de uma feature, testando
    todas as fontes prováveis. Retorna string ou None.

    A API do IBGE tem variado os nomes das propriedades ao longo dos
    anos. Esta função é defensiva: testa as principais.
    """
    props = feature.get('properties', {}) or {}

    candidatos = [
        props.get('codarea'),
        props.get('CD_MUN'),
        props.get('GEOCODIGO'),
        props.get('cd_geocmu'),
        feature.get('id'),  # último recurso
    ]

    for cand in candidatos:
        if cand is None:
            continue
        s = str(cand).strip()
        # Aceitar 7 dígitos (cód. completo) ou 6 (sem dígito verificador)
        if s.isdigit() and len(s) in (6, 7):
            return s
    return None


def adicionar_cod_6(geojson: dict) -> dict:
    """
    Garante que cada feature do GeoJSON tenha `properties.cod_ibge_6`
    como STRING de 6 dígitos.

    O CAGED do MTE usa códigos de 6 dígitos (sem dígito verificador).
    O IBGE usa de 7. Convertemos os 7 para 6 cortando o último dígito.
    """
    encontrados = 0
    perdidos = 0

    for f in geojson.get('features', []):
        props = f.setdefault('properties', {})
        cod = _extrair_codigo_ibge(f)
        if cod is None:
            perdidos += 1
            continue
        if len(cod) == 7:
            cod = cod[:6]  # remove dígito verificador
        # Salva como STRING - é o que o Plotly espera para o match
        props['cod_ibge_6'] = cod
        encontrados += 1

    print(f"[GEO] cod_ibge_6 atribuído a {encontrados} features "
          f"({perdidos} sem código identificado)")

    if encontrados == 0:
        # Falha total: imprime estrutura pra debug
        if geojson.get('features'):
            print(f"[GEO] ⚠ Nenhum código encontrado. Estrutura da 1ª feature:")
            primeira = geojson['features'][0]
            print(f"      keys: {list(primeira.keys())}")
            print(f"      properties keys: {list(primeira.get('properties', {}).keys())}")
            print(f"      id: {primeira.get('id')!r}")
    return geojson


def main():
    GEO_MUNICIPIOS.parent.mkdir(parents=True, exist_ok=True)

    if GEO_MUNICIPIOS.exists():
        print(f"[GEO] Arquivo já existe em {GEO_MUNICIPIOS}")
        print(f"[GEO] Para forçar redownload, apague o arquivo e rode de novo.")
        return

    geo = baixar_geojson()
    geo = adicionar_cod_6(geo)

    with open(GEO_MUNICIPIOS, 'w', encoding='utf-8') as f:
        json.dump(geo, f, ensure_ascii=False)

    size_kb = GEO_MUNICIPIOS.stat().st_size / 1024
    print(f"[GEO] Salvo: {GEO_MUNICIPIOS.name} ({size_kb:.1f} KB)")


if __name__ == '__main__':
    main()
