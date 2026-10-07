"""Configurações › Avisos e e-mail (CFG-05, CFG-06): antecedência do cliente e SMTP da loja.

- A senha SMTP é cifrada (``app/services/cifra.py``), nunca sai pela API (só ``senha_definida``) e é
  mascarada na auditoria (migração 0008). Sem ``CHAVE_CIFRA`` no servidor, salvar uma senha dá 422.
- Em produção o servidor precisa resolver só para endereços públicos (SSRF, ``servidor_permitido``); a
  conferência se repete na hora de conectar (``app/services/envio_email.py``).
- "Enviar e-mail de teste" usa a configuração **salva**, no máximo 5 por loja a cada 10 min; o envio é
  feito pela rota depois de encerrar a transação (PER-05).
"""

from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.models import Loja, LojaConfiguracao
from app.schemas.notificacoes import ConfigNotificacoes, ConfigNotificacoesEntrada, EmailConfig
from app.services.cifra import cifra_disponivel, cifrar
from app.services.comum import fuso, nomes_funcionarios
from app.services.configuracoes import configuracao_da_loja
from app.services.envio_email import MSG_SERVIDOR_NAO_PERMITIDO, ConfigSmtp, servidor_permitido
from app.services.tarefa_notificacoes import config_smtp

MSG_OBRIGATORIO_ATIVO = 'Campo obrigatório para ativar o envio de e-mail.'
MSG_SEM_CHAVE = 'O servidor não está configurado para guardar senhas de e-mail.'
MSG_SENHA_DE_NOVO = 'Informe a senha de novo ao trocar o servidor ou o usuário.'
MSG_TESTE_SEM_CONFIG = 'Configure e ative o envio de e-mail antes de testar.'
PORTA_PADRAO = 587
OBRIGATORIOS_ATIVO = ('servidor', 'porta', 'seguranca', 'remetente_email')


def config_notificacoes(db: Session, loja: Loja) -> ConfigNotificacoes:
    c = configuracao_da_loja(db, loja.id)
    zona = fuso(loja.fuso_horario)
    autor = c.atualizado_por
    return ConfigNotificacoes(
        antecedencia_cliente_minutos=c.antecedencia_cliente_minutos,
        email=EmailConfig(
            ativo=c.smtp_ativo,
            servidor=c.smtp_servidor,
            porta=c.smtp_porta,
            seguranca=c.smtp_seguranca,  # type: ignore[arg-type]
            usuario=c.smtp_usuario,
            senha_definida=c.smtp_senha_cifrada is not None,
            remetente_email=c.smtp_remetente_email,
            remetente_nome=c.smtp_remetente_nome,
        ),
        whatsapp_disponivel=False,
        criado_em=c.criado_em.astimezone(zona),
        atualizado_em=c.atualizado_em.astimezone(zona),
        atualizado_por=autor,
        atualizado_por_nome=nomes_funcionarios(db, loja.id, [autor]).get(autor) if autor else None,
    )


def servidor_conferido(dados: ConfigNotificacoesEntrada) -> bool | None:
    """O servidor informado é permitido (SSRF)? None = sem servidor. Consulta o DNS em produção: a rota
    chama isto antes de abrir a transação (dependência declarada antes do contexto da loja)."""
    email = dados.email
    if not email.servidor:
        return None
    return servidor_permitido(email.servidor, email.porta or PORTA_PADRAO)


def _conferir(dados: ConfigNotificacoesEntrada, atual: LojaConfiguracao, servidor_ok: bool | None) -> None:
    """Regras que dependem de mais de um campo, do que está salvo ou do servidor: 422 por campo."""
    email = dados.email
    erros = []
    if email.ativo:
        erros += [
            {'type': 'regra', 'loc': ('body', 'email', campo), 'msg': MSG_OBRIGATORIO_ATIVO}
            for campo in OBRIGATORIOS_ATIVO
            if getattr(email, campo) is None
        ]
    if email.servidor and servidor_ok is False:
        erros.append(
            {'type': 'regra', 'loc': ('body', 'email', 'servidor'), 'msg': MSG_SERVIDOR_NAO_PERMITIDO}
        )
    if email.mudar_senha and email.senha is not None and not cifra_disponivel():
        erros.append({'type': 'regra', 'loc': ('body', 'email', 'senha'), 'msg': MSG_SEM_CHAVE})
    trocou_conta = email.servidor != atual.smtp_servidor or email.usuario != atual.smtp_usuario
    if atual.smtp_senha_cifrada is not None and trocou_conta and not email.mudar_senha:
        # A4: a senha salva não vai para outro servidor/usuário sem quem edita conhecê-la
        erros.append({'type': 'regra', 'loc': ('body', 'email', 'senha'), 'msg': MSG_SENHA_DE_NOVO})
    if erros:
        raise RequestValidationError(erros)


def salvar_config_notificacoes(
    db: Session, loja: Loja, dados: ConfigNotificacoesEntrada, servidor_ok: bool | None
) -> ConfigNotificacoes:
    """Grava o que mudou (o mesmo valor de novo não mexe na última alteração nem na auditoria).

    ``servidor_ok``: resultado de ``servidor_conferido`` (feito antes da transação).
    """
    c = configuracao_da_loja(db, loja.id)
    _conferir(dados, c, servidor_ok)
    email = dados.email
    novos = {
        'antecedencia_cliente_minutos': dados.antecedencia_cliente_minutos,
        'smtp_ativo': email.ativo,
        'smtp_servidor': email.servidor,
        'smtp_porta': email.porta,
        'smtp_seguranca': email.seguranca,
        'smtp_usuario': email.usuario,
        'smtp_remetente_email': email.remetente_email,
        'smtp_remetente_nome': email.remetente_nome,
    }
    if email.mudar_senha:
        novos['smtp_senha_cifrada'] = cifrar(email.senha) if email.senha is not None else None
    for coluna, valor in novos.items():
        if getattr(c, coluna) != valor:
            setattr(c, coluna, valor)
    db.flush()
    return config_notificacoes(db, loja)


def config_para_teste(db: Session, loja: Loja) -> ConfigSmtp | str | None:
    """A configuração salva para o teste: ``None`` = não configurada/ativa (409); texto = erro já sabido
    (senha que não abre); senão o SMTP pronto para enviar."""
    c = configuracao_da_loja(db, loja.id)
    if not c.smtp_ativo:
        return None
    return config_smtp(c)
