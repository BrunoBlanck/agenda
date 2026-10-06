"""Cores do site do consumidor (SIT-09, SIT-13 a SIT-15): paleta padrão, contraste e o CSS da loja.

A loja escolhe duas cores (topo e destaque); vazia = cor da paleta do tipo da loja. O texto branco
precisa de contraste de pelo menos 4,5:1 sobre cada cor (WCAG AA, SIT-14). No modo escuro do site o
topo usa a cor escolhida e o destaque é clareado até ter 4,5:1 sobre o fundo escuro (SIT-15).

Só cálculo (sem banco): usado pela validação da entrada, pelas rotas e pelas páginas do site.

📌 ``PALETAS`` tem os mesmos valores de ``app/static/site/site.css`` (``tests/test_cores_site.py``
confere): o CSS continua sendo o padrão de quem não escolheu cor. ``topo_escuro`` só alimenta o
``<meta name="theme-color">`` do modo escuro (``cores_do_topo``).
"""

import re
from dataclasses import dataclass

from app.models.enums import TipoLoja

MSG_FORMATO_COR = 'Informe a cor no formato #RRGGBB.'
MSG_CONTRASTE_COR = 'Cor muito clara: o texto branco fica difícil de ler. Escolha uma cor mais escura.'
CONTRASTE_MINIMO = 4.5
CLASSE_CORES = 'cores-da-loja'  # classe do <body> quando a loja escolheu alguma cor

Rgb = tuple[int, int, int]
BRANCO: Rgb = (255, 255, 255)
_HEX = re.compile(r'#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})')
# Fração da cor de destaque no fundo suave (resumo do pedido): sobre o branco e sobre a superfície escura
SUAVE_CLARO, SUAVE_ESCURO = 0.12, 0.18


@dataclass(frozen=True)
class Paleta:
    topo: str
    destaque: str
    fundo_escuro: str
    superficie_escura: str
    topo_escuro: str


PALETAS: dict[TipoLoja, Paleta] = {
    TipoLoja.clinica: Paleta(
        '#0d4b4f', '#0b6767', fundo_escuro='#0e1617', superficie_escura='#162123', topo_escuro='#0a3437'
    ),
    TipoLoja.barbearia: Paleta(
        '#1f2230', '#8f4a1c', fundo_escuro='#141210', superficie_escura='#1f1c19', topo_escuro='#15171f'
    ),
    TipoLoja.escola: Paleta(
        '#2a357f', '#3a45a6', fundo_escuro='#11121c', superficie_escura='#1a1c2a', topo_escuro='#1c2358'
    ),
}


@dataclass(frozen=True)
class CoresDoTopo:
    """Cor do topo no modo claro e no escuro: vai no ``<meta name="theme-color">`` (barra do navegador)."""

    claro: str
    escuro: str


def paleta_do_tipo(tipo: TipoLoja | str) -> Paleta:
    """Paleta do tipo da loja; tipo desconhecido fica com a da clínica (o padrão do CSS, ``:root``)."""
    try:
        return PALETAS[TipoLoja(tipo)]
    except ValueError:
        return PALETAS[TipoLoja.clinica]


# --- Cor e contraste -------------------------------------------------------------------------------


def ler_cor(texto: str | None) -> Rgb | None:
    """``#rrggbb`` (minúsculas, como gravado) em RGB; qualquer outra coisa = None."""
    achado = _HEX.fullmatch(texto) if texto else None
    if achado is None:
        return None
    r, g, b = (int(parte, 16) for parte in achado.groups())
    return r, g, b


def escrever_cor(rgb: Rgb) -> str:
    """RGB em ``#rrggbb``: o CSS gerado só recebe cores reescritas daqui (nunca o texto gravado)."""
    return '#{:02x}{:02x}{:02x}'.format(*rgb)


def normalizar_cor(texto: str) -> str | None:
    """``#RRGGBB`` com ou sem maiúsculas e espaços em volta vira ``#rrggbb``; formato inválido = None."""
    cor = texto.strip().lower()
    return cor if ler_cor(cor) is not None else None


def _canal_linear(canal: int) -> float:
    c = canal / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminancia(rgb: Rgb) -> float:
    """Luminância relativa (WCAG 2.x)."""
    r, g, b = (_canal_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: Rgb, b: Rgb) -> float:
    claro, escuro = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


def legivel_com_branco(cor: str) -> bool:
    """SIT-14: texto branco sobre a cor com contraste de pelo menos 4,5:1."""
    rgb = ler_cor(cor)
    return rgb is not None and contraste(rgb, BRANCO) >= CONTRASTE_MINIMO


def misturar(cor: Rgb, base: Rgb, fracao: float) -> Rgb:
    """``fracao`` de ``cor`` sobre ``base`` (0 = só a base, 1 = só a cor)."""
    r, g, b = (round(c * fracao + f * (1 - fracao)) for c, f in zip(cor, base, strict=True))
    return r, g, b


def clarear_ate_contraste(cor: Rgb, fundo: Rgb) -> Rgb:
    """SIT-15: mistura a cor com branco, aos poucos, até ter 4,5:1 sobre o fundo escuro."""
    for passo in range(101):
        clara = misturar(BRANCO, cor, passo / 100)
        if contraste(clara, fundo) >= CONTRASTE_MINIMO:
            return clara
    return BRANCO


# --- CSS da loja -----------------------------------------------------------------------------------


def cores_do_topo(tipo: TipoLoja | str, topo: str | None) -> CoresDoTopo:
    """Cor da barra do navegador (DIR-004): a mesma do topo do site, em cada modo.

    Topo escolhido pela loja vale nos dois modos, como no ``css_da_loja``; sem escolha (ou fora do
    formato), as do tipo da loja. Só sai cor reescrita por ``escrever_cor`` ou da paleta fixa.
    """
    rgb = ler_cor(topo)
    if rgb is not None:
        cor = escrever_cor(rgb)
        return CoresDoTopo(claro=cor, escuro=cor)
    paleta = paleta_do_tipo(tipo)
    return CoresDoTopo(claro=paleta.topo, escuro=paleta.topo_escuro)


def css_da_loja(tipo: TipoLoja | str, topo: str | None, destaque: str | None) -> str | None:
    """Variáveis CSS das cores escolhidas, por cima da paleta do tipo; None = nada escolhido.

    Vai num ``<style nonce>`` da página (``app/routers/site/paginas.py``) com o seletor
    ``body.cores-da-loja``, mais específico que ``.tipo-*`` do ``site.css``. O topo vale também no
    modo escuro (está fora do ``@media``); o destaque tem a versão clara e a escura (SIT-15). Cor
    gravada fora do formato (o CHECK do banco não deixa) é ignorada: fica a do tipo.
    """
    paleta = paleta_do_tipo(tipo)
    rgb_topo, rgb_destaque = ler_cor(topo), ler_cor(destaque)
    claro: list[str] = []
    escuro: list[str] = []
    if rgb_topo is not None:
        claro.append(f'--cor-topo:{escrever_cor(rgb_topo)}')
    if rgb_destaque is not None:
        claro += [
            f'--cor-destaque:{escrever_cor(rgb_destaque)}',
            f'--cor-destaque-texto:{escrever_cor(BRANCO)}',
            f'--cor-destaque-suave:{escrever_cor(misturar(rgb_destaque, BRANCO, SUAVE_CLARO))}',
        ]
        superficie = ler_cor(paleta.superficie_escura) or BRANCO
        destaque_escuro = clarear_ate_contraste(rgb_destaque, superficie)
        escuro += [
            f'--cor-destaque:{escrever_cor(destaque_escuro)}',
            # O fundo escuro é mais escuro que a superfície: o texto sobre o destaque também passa de 4,5:1
            f'--cor-destaque-texto:{paleta.fundo_escuro}',
            f'--cor-destaque-suave:{escrever_cor(misturar(destaque_escuro, superficie, SUAVE_ESCURO))}',
        ]
    if not claro:
        return None
    seletor = f'body.{CLASSE_CORES}'
    css = f'{seletor}{{{";".join(claro)}}}'
    if escuro:
        css += f'@media (prefers-color-scheme: dark){{{seletor}{{{";".join(escuro)}}}}}'
    return css
