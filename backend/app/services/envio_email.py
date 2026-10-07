"""Envio de e-mail pelo SMTP de cada loja (CFG-06, NOT-04, NOT-07), com provedor trocável.

- ``EnvioSmtp``: o envio de verdade (``smtplib``), TLS com o certificado conferido (``ssl`` = SMTPS na
  conexão, ``starttls`` = STARTTLS obrigatório) e, em produção, só para servidores com endereço público (SSRF:
  o endereço é resolvido e conferido na hora de conectar, inclusive IPv4 embutido em IPv6, e a conexão vai
  para o IP conferido, sem nova consulta ao DNS). Chamado fora de qualquer transação, numa thread.
- **Prazo total** (``PRAZO_ENVIO``, 15 s): o tempo limite do socket vale por operação, e um servidor que
  manda um byte por segundo nunca o estoura. Um vigia (``threading.Timer``) fecha o socket quando o prazo do
  envio inteiro (conectar, TLS, login e mensagem) acaba; o envio falha com ``MSG_DEMOROU``.
- ``EnvioFalso``: guarda o que seria enviado; é o provedor em ``AMBIENTE=teste`` (nada sai para a rede).

Erros viram ``FalhaEnvio`` com mensagem pronta para a tela e para ``notificacoes.email_erro``: nunca a
senha, o stack ou a resposta crua do servidor. ``definitiva`` = repetir não adianta (usuário/senha,
remetente ou destinatário recusados, servidor não permitido). ``conexao`` = o servidor não respondeu
(não conecta, TLS, prazo): os outros e-mails da mesma loja nem são tentados neste ciclo.
"""

import contextlib
import ipaddress
import smtplib
import socket
import ssl
import threading
import time
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Literal, Protocol

from app.config import get_settings

PRAZO_ENVIO = 15.0  # segundos para o envio inteiro (NOT-07); também o tempo limite de cada operação

MSG_CONECTAR = 'Não foi possível conectar ao servidor de e-mail.'
MSG_DEMOROU = 'O servidor de e-mail demorou demais para responder.'
MSG_TLS = 'Não foi possível abrir uma conexão segura com o servidor de e-mail.'
MSG_SEGURANCA = 'O servidor de e-mail não aceita a segurança escolhida.'
MSG_LOGIN = 'O servidor de e-mail recusou o usuário ou a senha.'
MSG_REMETENTE = 'O servidor de e-mail recusou o remetente.'
MSG_DESTINO = 'O servidor de e-mail recusou o destinatário.'
MSG_ACENTOS = 'O servidor de e-mail não aceita endereços com acentos ou caracteres especiais.'
MSG_RECUSOU = 'O servidor de e-mail não aceitou a mensagem.'
MSG_SERVIDOR_NAO_PERMITIDO = 'Servidor não permitido.'
MSG_SENHA_ILEGIVEL = 'Não foi possível ler a senha do e-mail da loja. Salve a senha de novo.'

Seguranca = Literal['ssl', 'starttls']

# Prefixos IPv6 que carregam um IPv4 nos últimos 32 bits (NAT64 RFC 6052/8215, IPv4-compatível)
_NAT64 = (ipaddress.ip_network('64:ff9b::/96'), ipaddress.ip_network('64:ff9b:1::/48'))
_COMPATIVEL = ipaddress.ip_network('::/96')


@dataclass(frozen=True)
class ConfigSmtp:
    servidor: str
    porta: int
    seguranca: Seguranca
    usuario: str | None
    senha: str | None = field(repr=False)
    remetente_email: str
    remetente_nome: str | None


@dataclass(frozen=True)
class Email:
    destino: str
    assunto: str
    corpo: str


class FalhaEnvio(Exception):
    def __init__(self, mensagem: str, *, definitiva: bool = False, conexao: bool = False) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.definitiva = definitiva
        self.conexao = conexao


class EnvioEmail(Protocol):
    def enviar(self, config: ConfigSmtp, email: Email) -> None:
        """Envia ou levanta ``FalhaEnvio``."""
        ...


# --- Endereço do servidor (SSRF) -------------------------------------------------------------------


def _ipv4_embutido(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip.teredo is not None:
        return ip.teredo[1]
    if any(ip in rede for rede in _NAT64) or (ip in _COMPATIVEL and int(ip) > 1):
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def _publico(endereco: str) -> bool:
    ip = ipaddress.ip_address(endereco.split('%', 1)[0])
    if not ip.is_global or ip.is_multicast:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        embutido = _ipv4_embutido(ip)
        if embutido is not None:
            return embutido.is_global and not embutido.is_multicast
    return True


def exigir_endereco_publico() -> bool:
    """Só em produção o servidor precisa ter endereço público (em dev e testes vale um SMTP local)."""
    return get_settings().ambiente == 'producao'


def enderecos_do_servidor(servidor: str, porta: int) -> list[str]:
    """IPs do servidor (vazio se o nome não resolve)."""
    try:
        infos = socket.getaddrinfo(servidor, porta, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return []
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


def servidor_permitido(servidor: str, porta: int) -> bool:
    """Todos os endereços do servidor são públicos (nada de loopback, rede privada, link-local, NAT64 para
    endereço interno...). Faz consulta ao DNS em produção: chame fora de transação."""
    if not exigir_endereco_publico():
        return True
    enderecos = enderecos_do_servidor(servidor, porta)
    return bool(enderecos) and all(_publico(e) for e in enderecos)


class _Vigia:
    """Prazo total do envio (A2/A6). Cada socket da conexão é registrado assim que existe: o TCP bruto
    (antes do TLS) e o TLS (antes do handshake). Quando o prazo acaba, o timer faz ``shutdown(SHUT_RDWR)``
    em todos, o que destrava qualquer leitura bloqueada (inclusive no meio do handshake do STARTTLS ou do
    SMTPS); socket registrado depois do disparo é derrubado na hora, e toda operação seguinte confere o
    prazo antes (``conferir``). Fechar os sockets fica para a thread do envio (sem corrida de descritor)."""

    def __init__(self, prazo: float) -> None:
        self.limite = time.monotonic() + prazo
        self.estourou = False
        self._sockets: list[socket.socket] = []
        self._trava = threading.Lock()
        self._timer = threading.Timer(prazo, self._disparar)
        self._timer.daemon = True

    def restante(self) -> float:
        return self.limite - time.monotonic()

    def conferir(self) -> None:
        if self.estourou or self.restante() <= 0:
            self.estourou = True
            raise FalhaEnvio(MSG_DEMOROU, conexao=True)

    def registrar(self, sock: socket.socket) -> None:
        with self._trava:
            self._sockets.append(sock)
            disparado = self.estourou
        if disparado:
            _derrubar(sock)

    def _disparar(self) -> None:
        with self._trava:
            self.estourou = True
            sockets = list(self._sockets)
        for sock in sockets:
            _derrubar(sock)

    def fechar(self) -> None:
        for sock in self._sockets:
            with contextlib.suppress(OSError):
                sock.close()

    def __enter__(self) -> '_Vigia':
        self._timer.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._timer.cancel()
        self.fechar()


def _derrubar(sock: socket.socket) -> None:
    with contextlib.suppress(OSError):  # o TCP bruto já desligado pelo TLS (detach) recusa: tudo bem
        sock.shutdown(socket.SHUT_RDWR)


def _resolver(servidor: str, porta: int, vigia: _Vigia) -> list[str]:
    """DNS dentro do prazo: ``getaddrinfo`` não pode ser interrompido, então roda numa thread (daemon, que
    termina sozinha quando o sistema desiste) e o envio falha se o prazo acabar antes."""
    resultado: list[list[str]] = []
    fio = threading.Thread(
        target=lambda: resultado.append(enderecos_do_servidor(servidor, porta)), daemon=True
    )
    fio.start()
    fio.join(max(vigia.restante(), 0))
    vigia.conferir()
    if not resultado:  # a thread terminou sem resultado (não deveria): trata como não resolvido
        return []
    return resultado[0]


def _conectar(servidor: str, porta: int, vigia: _Vigia, origem: tuple[str, int] | None) -> socket.socket:
    """Resolve, confere (SSRF, em produção) e conecta ao IP conferido, tudo dentro do prazo."""
    vigia.conferir()
    enderecos = _resolver(servidor, porta, vigia)
    if not enderecos:
        raise FalhaEnvio(MSG_CONECTAR, conexao=True)
    if exigir_endereco_publico() and not all(_publico(e) for e in enderecos):
        raise FalhaEnvio(MSG_SERVIDOR_NAO_PERMITIDO, definitiva=True)
    vigia.conferir()
    sock = socket.create_connection((enderecos[0], porta), min(vigia.restante(), PRAZO_ENVIO), origem)
    vigia.registrar(sock)
    vigia.conferir()
    return sock


class _ContextoVigiado:
    """Embrulha o ``SSLContext``: o socket TLS é registrado no vigia **antes** do handshake."""

    def __init__(self, contexto: ssl.SSLContext, vigia: _Vigia) -> None:
        self._contexto = contexto
        self._vigia = vigia

    def wrap_socket(
        self, sock: socket.socket, server_hostname: str | None = None, **_: object
    ) -> ssl.SSLSocket:
        self._vigia.conferir()
        tls = self._contexto.wrap_socket(sock, server_hostname=server_hostname, do_handshake_on_connect=False)
        self._vigia.registrar(tls)
        self._vigia.conferir()
        tls.settimeout(max(self._vigia.restante(), 0.01))  # o handshake inteiro cabe no que sobrou do prazo
        tls.do_handshake()
        self._vigia.conferir()
        return tls


class _SmtpConferido(smtplib.SMTP):
    """Conecta só ao IP conferido (o nome continua valendo para o TLS) e confere o prazo a cada envio de
    comando ou dado ao servidor."""

    vigia: _Vigia | None = None

    def _get_socket(self, host: str, port: int, timeout: float) -> socket.socket:
        if self.vigia is None:
            raise RuntimeError('Conexão SMTP sem vigia.')
        return _conectar(host, port, self.vigia, self.source_address)

    def send(self, s: str | bytes) -> None:
        if self.vigia is not None:
            self.vigia.conferir()
            if self.sock is not None:  # a leitura da resposta também fica dentro do que sobrou do prazo
                self.sock.settimeout(max(self.vigia.restante(), 0.01))
        super().send(s)


class _SmtpSslConferido(smtplib.SMTP_SSL, _SmtpConferido):
    """SMTPS: ``SMTP_SSL._get_socket`` chama o de ``_SmtpConferido`` e embrulha no TLS (contexto vigiado)."""


# --- Mensagem ----------------------------------------------------------------------------------------


def _uma_linha(texto: str) -> str:
    return ' '.join(texto.split())


def montar_mensagem(config: ConfigSmtp, email: Email) -> EmailMessage:
    """Texto simples (NOT-08), UTF-8, sem quebra de linha nos cabeçalhos (injeção de cabeçalho)."""
    mensagem = EmailMessage()
    mensagem['From'] = formataddr((_uma_linha(config.remetente_nome or ''), config.remetente_email))
    mensagem['To'] = email.destino
    mensagem['Subject'] = _uma_linha(email.assunto)
    mensagem['Date'] = formatdate(localtime=False)
    mensagem['Message-ID'] = make_msgid(domain=config.remetente_email.rpartition('@')[2] or None)
    mensagem.set_content(email.corpo)
    return mensagem


# --- Provedores ----------------------------------------------------------------------------------------


class EnvioSmtp:
    def __init__(self, prazo: float = PRAZO_ENVIO) -> None:
        self.prazo = prazo

    def _conversa(self, conexao: smtplib.SMTP, config: ConfigSmtp, email: Email, vigia: _Vigia) -> None:
        conexao.connect(config.servidor, config.porta)
        if config.seguranca == 'starttls':
            try:
                conexao.starttls(context=_ContextoVigiado(ssl.create_default_context(), vigia))  # type: ignore[arg-type]
            except smtplib.SMTPNotSupportedError:
                raise FalhaEnvio(MSG_SEGURANCA, definitiva=True) from None
        vigia.conferir()
        if config.usuario and config.senha:
            conexao.login(config.usuario, config.senha)
        vigia.conferir()
        try:
            conexao.send_message(montar_mensagem(config, email))
        except smtplib.SMTPNotSupportedError:  # endereço não ASCII e o servidor sem SMTPUTF8
            raise FalhaEnvio(MSG_ACENTOS, definitiva=True) from None
        conexao.quit()

    def enviar(self, config: ConfigSmtp, email: Email) -> None:
        vigia = _Vigia(self.prazo)
        tempo = min(self.prazo, PRAZO_ENVIO)  # tempo limite de cada operação (o vigia cuida do total)
        conexao: smtplib.SMTP = (
            _SmtpSslConferido(timeout=tempo, context=_ContextoVigiado(ssl.create_default_context(), vigia))  # type: ignore[arg-type]
            if config.seguranca == 'ssl'
            else _SmtpConferido(timeout=tempo)
        )
        conexao.vigia = vigia  # type: ignore[attr-defined]
        try:
            with vigia:
                self._conversa(conexao, config, email, vigia)
        except FalhaEnvio:
            raise
        except smtplib.SMTPAuthenticationError:
            raise FalhaEnvio(MSG_LOGIN, definitiva=True) from None
        except smtplib.SMTPSenderRefused:
            raise FalhaEnvio(MSG_REMETENTE, definitiva=True) from None
        except smtplib.SMTPRecipientsRefused:
            raise FalhaEnvio(MSG_DESTINO, definitiva=True) from None
        except (smtplib.SMTPException, ssl.SSLError, OSError, UnicodeError, ValueError) as erro:
            raise _falha_de_conexao(erro, estourou=vigia.estourou) from None
        finally:
            conexao.close()


def _falha_de_conexao(erro: Exception, *, estourou: bool) -> FalhaEnvio:
    if estourou or isinstance(erro, TimeoutError):
        return FalhaEnvio(MSG_DEMOROU, conexao=True)
    if isinstance(erro, ssl.SSLError):
        return FalhaEnvio(MSG_TLS, conexao=True)
    if isinstance(erro, smtplib.SMTPResponseException) and not isinstance(erro, smtplib.SMTPConnectError):
        return FalhaEnvio(MSG_RECUSOU)
    return FalhaEnvio(MSG_CONECTAR, conexao=True)  # DNS, conexão recusada ou derrubada


@dataclass
class EnvioFalso:
    """Guarda as mensagens; ``falhas`` (uma por envio, na ordem) simula erros do servidor."""

    enviados: list[tuple[ConfigSmtp, Email]] = field(default_factory=list)
    falhas: list[FalhaEnvio] = field(default_factory=list)

    def enviar(self, config: ConfigSmtp, email: Email) -> None:
        if self.falhas:
            raise self.falhas.pop(0)
        self.enviados.append((config, email))


SMTP = EnvioSmtp()
FALSO = EnvioFalso()


def provedor_de_email() -> EnvioEmail:
    """O provedor do ambiente: nos testes, o falso (nada sai para a rede)."""
    return FALSO if get_settings().ambiente == 'teste' else SMTP
