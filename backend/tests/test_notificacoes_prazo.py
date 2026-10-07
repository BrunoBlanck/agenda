"""Prazo total do envio de e-mail em cada fase (A6) e ciclo que não espera loja atrasada.

Servidores locais de verdade: um que trava no meio do handshake TLS (manda o começo de um registro e
goteja um byte por segundo) e um que completa o handshake e goteja a resposta seguinte. Os dois em STARTTLS
e em SMTPS. O certificado é autoassinado: o cliente aceita só nestes testes (contexto sem verificação).
"""

import socket
import ssl
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from app.services import envio_email
from app.services.envio_email import MSG_DEMOROU, ConfigSmtp, Email, EnvioFalso, EnvioSmtp, FalhaEnvio
from app.services.tarefa_notificacoes import Despachante, processar
from tests.clinica import SEGUNDA, montar_clinica
from tests.test_notificacoes import criar_no_painel, dar_email, ligar_smtp
from tests.test_notificacoes_envio import fila

PRAZO = 2.0
GOTEJAR = 40  # segundos que o servidor seguraria a conexão sem o vigia


@pytest.fixture(scope='module')
def certificado(tmp_path_factory) -> tuple[str, str]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    pasta = tmp_path_factory.mktemp('tls')
    chave = ec.generate_private_key(ec.SECP256R1())
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'smtp.teste.local')])
    agora = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(1)
        .not_valid_before(agora - timedelta(days=1))
        .not_valid_after(agora + timedelta(days=1))
        .sign(chave, hashes.SHA256())
    )
    arquivo_cert, arquivo_chave = pasta / 'cert.pem', pasta / 'chave.pem'
    arquivo_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    arquivo_chave.write_bytes(
        chave.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    return str(arquivo_cert), str(arquivo_chave)


@pytest.fixture
def sem_verificar_certificado(monkeypatch):
    monkeypatch.setattr(
        envio_email.ssl,
        'create_default_context',
        lambda *a, **k: ssl._create_unverified_context(),  # noqa: S323 (certificado autoassinado do teste)
    )


def _gotejar(conexao, prefixo: bytes, byte: bytes, parar: threading.Event) -> None:
    conexao.sendall(prefixo)
    for _ in range(GOTEJAR):
        if parar.is_set():
            return
        time.sleep(1)
        conexao.sendall(byte)


@pytest.fixture
def servidor_tls(certificado):
    """Fábrica: ``servidor_tls(seguranca, fase)`` sobe um servidor e devolve a porta.

    fase ``handshake``: trava no meio do handshake; fase ``depois``: completa o handshake e goteja a
    próxima resposta (a saudação no SMTPS, a resposta ao EHLO no STARTTLS)."""
    parar = threading.Event()
    abertos: list[socket.socket] = []
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.load_cert_chain(*certificado)

    def atender(conexao: socket.socket, seguranca: str, fase: str, antes: float) -> None:
        try:
            if seguranca == 'starttls':
                conexao.sendall(b'220 ')
                for _ in range(int(antes / 0.25)):  # saudação lenta: gasta o prazo antes do TLS
                    time.sleep(0.25)
                    conexao.sendall(b'x')
                conexao.sendall(b'\r\n')
                conexao.recv(1000)  # EHLO
                conexao.sendall(b'250-oi\r\n250 STARTTLS\r\n')
                conexao.recv(1000)  # STARTTLS
                conexao.sendall(b'220 pode\r\n')
            if fase == 'handshake':
                conexao.recv(4000)  # ClientHello
                _gotejar(conexao, bytes([0x16, 0x03, 0x03, 0x3E, 0x80]), b'\x00', parar)  # registro de 16 KB
                return
            tls = contexto.wrap_socket(conexao, server_side=True)
            if seguranca == 'starttls':
                tls.recv(1000)  # EHLO, já cifrado
                _gotejar(tls, b'250-', b'y', parar)
            else:
                _gotejar(tls, b'220-', b'x', parar)
        except OSError:
            pass
        finally:
            conexao.close()

    def subir(seguranca: str, fase: str, antes: float = 0) -> int:
        servidor = socket.socket()
        servidor.bind(('127.0.0.1', 0))
        servidor.listen(4)
        servidor.settimeout(0.2)
        abertos.append(servidor)

        def aceitar() -> None:
            while not parar.is_set():
                try:
                    conexao, _ = servidor.accept()
                except (TimeoutError, OSError):
                    continue
                threading.Thread(target=atender, args=(conexao, seguranca, fase, antes), daemon=True).start()

        threading.Thread(target=aceitar, daemon=True).start()
        return servidor.getsockname()[1]

    yield subir
    parar.set()
    for servidor in abertos:
        servidor.close()


def enviar_com_prazo(porta: int, seguranca: str) -> float:
    config = ConfigSmtp('127.0.0.1', porta, seguranca, None, None, 'avisos@loja.com', None)  # type: ignore[arg-type]
    inicio = time.monotonic()
    with pytest.raises(FalhaEnvio) as erro:
        EnvioSmtp(prazo=PRAZO).enviar(config, Email('maria@example.com', 'Oi', 'Corpo'))
    duracao = time.monotonic() - inicio
    assert (erro.value.mensagem, erro.value.conexao) == (MSG_DEMOROU, True)
    return duracao


# --- Cada fase, STARTTLS e SMTPS ------------------------------------------------------------------------


@pytest.mark.parametrize('seguranca', ['starttls', 'ssl'])
def test_prazo_estoura_no_dns(seguranca, monkeypatch):
    def dns_travado(servidor, porta):
        time.sleep(GOTEJAR)
        return ['127.0.0.1']

    monkeypatch.setattr(envio_email, 'enderecos_do_servidor', dns_travado)
    assert enviar_com_prazo(25, seguranca) < PRAZO + 1


@pytest.mark.parametrize('seguranca', ['starttls', 'ssl'])
def test_prazo_estoura_durante_o_handshake_tls(seguranca, servidor_tls, sem_verificar_certificado):
    porta = servidor_tls(seguranca, 'handshake')
    assert enviar_com_prazo(porta, seguranca) < PRAZO + 1.5


@pytest.mark.parametrize('seguranca', ['starttls', 'ssl'])
def test_prazo_estoura_depois_do_handshake(seguranca, servidor_tls, sem_verificar_certificado):
    porta = servidor_tls(seguranca, 'depois')
    assert enviar_com_prazo(porta, seguranca) < PRAZO + 1.5


def test_vigia_que_dispara_no_handshake_do_starttls_segura_o_resto(servidor_tls, sem_verificar_certificado):
    """O cenário da revisão: a saudação lenta gasta quase todo o prazo e ele acaba no meio do handshake do
    STARTTLS (que, sozinho, teria o tempo limite inteiro de uma operação); o envio para no prazo."""
    porta = servidor_tls('starttls', 'handshake', antes=1.5)
    inicio = time.monotonic()
    with pytest.raises(FalhaEnvio):
        EnvioSmtp(prazo=PRAZO).enviar(
            ConfigSmtp('127.0.0.1', porta, 'starttls', 'u', 's', 'avisos@loja.com', None),
            Email('maria@example.com', 'Oi', 'Corpo'),
        )
    assert time.monotonic() - inicio < PRAZO + 0.8


def test_vigia_registrado_depois_do_disparo_derruba_na_hora():
    vigia = envio_email._Vigia(0.01)
    with vigia:
        time.sleep(0.1)
        with pytest.raises(FalhaEnvio):
            vigia.conferir()
        a, b = socket.socketpair()
        vigia.registrar(a)
        try:
            lido = a.recv(10)
        except OSError:  # Windows pode recusar a leitura depois do shutdown: também volta na hora
            lido = b''
        assert lido == b''  # derrubado: a leitura não fica esperando
        b.close()
    assert a.fileno() == -1  # fechado ao sair do vigia


# --- O ciclo não espera loja atrasada ---------------------------------------------------------------------


@pytest.fixture
def despachante():
    proprio = Despachante()
    yield proprio
    proprio.encerrar()


def test_ciclo_nao_espera_loja_atrasada_e_ela_fica_fora_do_seguinte(cliente, lojas, engine_dono, despachante):
    atrasada, outra = montar_clinica(cliente, lojas[0]), montar_clinica(cliente, lojas[1])
    for clinica, email in ((atrasada, 'a@example.com'), (outra, 'b@example.com')):
        ligar_smtp(engine_dono, clinica.lt.loja.id)
        dar_email(engine_dono, clinica.maria, email)
        criar_no_painel(cliente, clinica)
    liberar, enviando = threading.Event(), threading.Event()
    enviados: list[str] = []

    class Preso:
        def enviar(self, config, email):
            if email.destino == 'a@example.com':
                enviando.set()
                liberar.wait(30)  # um envio no pior caso (o prazo real é de 15 s)
            enviados.append(email.destino)

    inicio = time.monotonic()
    ciclo = processar(envio=Preso(), despachante=despachante, espera=1)
    assert time.monotonic() - inicio < 3  # não esperou a loja presa
    assert enviando.is_set()
    assert (ciclo.lojas, ciclo.enviados) == (2, 1)
    assert enviados == ['b@example.com']
    assert despachante.em_andamento() == {atrasada.lt.loja.id}

    # Enquanto ela envia, um aviso novo dela não é pego por outro ciclo deste processo
    criar_no_painel(cliente, atrasada, inicio=f'{SEGUNDA}T10:00')
    segundo = processar(envio=Preso(), despachante=despachante, espera=1)
    assert segundo.enviados == 0
    assert sorted(linha['email_tentativas'] for linha in fila(engine_dono)) == [0, 1, 1]

    liberar.set()
    limite = time.monotonic() + 10
    while despachante.em_andamento() and time.monotonic() < limite:
        time.sleep(0.05)
    assert despachante.em_andamento() == set()
    assert processar(envio=Preso(), despachante=despachante).enviados == 1
    assert sorted(enviados) == ['a@example.com', 'a@example.com', 'b@example.com']
    assert {linha['status_email'] for linha in fila(engine_dono)} == {2}


def test_pool_de_threads_fixo_entre_ciclos(cliente, clinica, engine_dono, despachante):
    ligar_smtp(engine_dono, clinica.lt.loja.id)
    dar_email(engine_dono, clinica.maria)
    for hora in ('08:00', '09:00', '10:00', '11:00', '13:00'):
        criar_no_painel(cliente, clinica, inicio=f'{SEGUNDA}T{hora}')
        processar(envio=EnvioFalso(), despachante=despachante)
    nomes = [t.name for t in threading.enumerate() if t.name.startswith('notificacoes')]
    assert 1 <= len(nomes) <= 4
