
import unicodedata
import pandas as pd

try:
    import ftfy
    _has_ftfy = True
except ImportError:
    _has_ftfy = False


# Aliases (chave normalizada -> nome canônico CAGED)
ALIASES = {
    # Da planilha de RD (5 inconsistências)
    'arquepelogo de fernando de noronha': 'fernando de noronha',
    'iguaracy': 'iguaraci',
    'santa maria do cumbuca': 'santa maria do cambuca',
    'sao caetano': 'sao caitano',
    'sao lorenco da mata': 'sao lourenco da mata',
    'viciencia': 'vicencia',

    # Do CSV de prefeitos (5 inconsistências, após ftfy)
    'belem do sao francisco': 'belem de sao francisco',
    'ilha de itamaraca': 'itamaraca',
    'jataoba': 'jatauba',
    'lagoa de itaenga': 'lagoa do itaenga',
    'timbaoba': 'timbauba',

    # Caso o ftfy falhe ou não esteja instalado
    'jata√oba': 'jatauba',
    'timba√oba': 'timbauba',
    'arquipelago de fernando de noronha': 'fernando de noronha',

    # Asterisco em "Pombos*" (PIB SEPLAG marca municípios com mudança de RD)
    'pombos*': 'pombos',
}


def normaliza_basico(s) -> str:
    """Lowercase + NFKD + remove acentos. Sem aliases."""
    if pd.isna(s):
        return ''
    s = str(s).strip()
    if _has_ftfy:
        s = ftfy.fix_text(s)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def normaliza_municipio(s) -> str:
    """Normaliza nome + aplica aliases para chegar na forma CAGED."""
    norm = normaliza_basico(s)
    return ALIASES.get(norm, norm)
