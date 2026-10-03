"""Endereço da loja (slug): formato e endereços reservados pelo sistema (PLA-16, GER-29).

O slug é o primeiro trecho da URL (``/clinica-sorriso`` e ``/clinica-sorriso/painel``), então não
pode coincidir com caminhos do próprio sistema. 📌 A migração 0005 (``ck_lojas_slug_reservado``) tem
esta mesma lista, escrita por extenso; ``tests/test_roteamento.py`` confere que as duas são iguais.
Para mudar a lista, crie uma migração nova e atualize os dois lugares.
"""

import re

SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
SLUG_TAMANHO_MAXIMO = 60

SLUGS_RESERVADOS: frozenset[str] = frozenset(
    {
        'superadmin',
        'api',
        'painel',
        'site',
        'docs',
        'redoc',
        'openapi',
        'admin',
        'login',
        'static',
        'assets',
        'app',
        'www',
        'saude',
        'health',
    }
)

MSG_SLUG_RESERVADO = 'Este endereço é reservado pelo sistema. Escolha outro.'


def endereco_de_loja(slug: str) -> bool:
    """O texto pode ser o endereço de uma loja? (formato válido e não reservado; não consulta o banco)."""
    return len(slug) <= SLUG_TAMANHO_MAXIMO and bool(SLUG.fullmatch(slug)) and slug not in SLUGS_RESERVADOS
