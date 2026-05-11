"""
tabs/__init__.py
================
Sistema de "registry" de abas. É o que permite o observatório crescer
sem mexer no app.py.

Como funciona:
1. Cada aba é um arquivo .py em tabs/ (exceto este e _template.py)
2. Cada arquivo expõe uma função registrar() que devolve um dicionário
   com a configuração da aba.
3. Este __init__ descobre automaticamente os arquivos no diretório e os
   carrega, ordenando pelo campo 'ordem'.
4. O resultado é uma lista que o app.py usa para montar a navegação.

Para adicionar uma aba nova:
    - Copie tabs/_template.py para tabs/sua_aba.py
    - Implemente as 3 funções: registrar(), layout(), callbacks()
    - A aba aparece no menu automaticamente

Cada aba tem dois níveis de identificação:
    eixo : str          -> "Mercado de trabalho", "PIB municipal", etc
                           (a navegação principal no topo)
    sub  : str          -> "Emprego formal", "Desemprego"
                           (sub-aba dentro do eixo)

Múltiplas abas podem compartilhar o mesmo eixo - elas viram sub-abas
agrupadas.
"""

import importlib
import pkgutil
from typing import Callable


# Registry global, populado em descobrir_abas()
_ABAS = []


def descobrir_abas():
    """
    Importa todos os módulos da pasta tabs/ que começam por letra
    minúscula (ignora __init__ e _template), e chama .registrar() em
    cada um. Cada chamada retorna um dict com a configuração.
    """
    global _ABAS
    if _ABAS:  # já descobertas, não repetir
        return _ABAS

    import tabs as este_pacote

    for finder, name, is_pkg in pkgutil.iter_modules(este_pacote.__path__):
        # Ignorar arquivos auxiliares (que começam com _) e pacotes
        if name.startswith('_') or is_pkg:
            continue

        modulo = importlib.import_module(f'tabs.{name}')
        if not hasattr(modulo, 'registrar'):
            continue

        config = modulo.registrar()
        config['module'] = modulo  # guarda referência ao módulo
        config['id'] = name        # ID técnico (usado em callbacks)
        _ABAS.append(config)

    # Ordenar por (eixo_ordem, sub_ordem)
    _ABAS.sort(key=lambda x: (x.get('eixo_ordem', 99), x.get('sub_ordem', 99)))
    return _ABAS


def listar_eixos():
    """Retorna a lista única de eixos na ordem correta, com seus subs."""
    abas = descobrir_abas()
    eixos = {}
    for aba in abas:
        eixo = aba['eixo']
        if eixo not in eixos:
            eixos[eixo] = {
                'nome': eixo,
                'ordem': aba.get('eixo_ordem', 99),
                'subs': []
            }
        eixos[eixo]['subs'].append(aba)
    return sorted(eixos.values(), key=lambda x: x['ordem'])


def aba_por_id(aba_id: str):
    """Retorna a config da aba pelo seu ID."""
    for aba in descobrir_abas():
        if aba['id'] == aba_id:
            return aba
    return None
