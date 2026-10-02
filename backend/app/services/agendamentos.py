"""Regras de agendamento (README "Regras de agendamento" e estrutura.md, 2.13 e 2.14).

- O serviço define a duração (pode ser ajustada) e o preço (congelado no agendamento).
- Só profissionais habilitados para o serviço (servico_funcionarios).
- Com o módulo Locais ativo: local obrigatório, ativo, permitido para o serviço (serviço sem local
  vinculado aceita qualquer um) e livre no horário (o banco garante com EXCLUDE).
- Dentro da jornada do perfil do profissional e fora dos bloqueios.
- Sem conflito de horário do profissional (EXCLUDE no banco, mensagem traduzida em app/erros.py).
- Módulo Serviços desligado: agendamento sem serviço, com duração e preço manuais.
- Materiais do serviço copiados para agendamento_materiais; baixa no estoque ao concluir.

Visibilidade (2.13): leitura em Agenda da equipe vê todos; só Minha agenda vê os próprios.
Escrita segue a mesma divisão (useAcesso.js: agenda.ver / agenda.editar).
"""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, false, select
from sqlalchemy.orm import Session

from app.auth.dependencias import ContextoLoja
from app.models import (
    Agendamento,
    AgendamentoMaterial,
    Cliente,
    Funcionario,
    Local,
    Material,
    Servico,
    ServicoFuncionario,
    ServicoLocal,
    ServicoMaterial,
)
from app.models.enums import NivelAcesso, OrigemAgendamento, StatusAgendamento, TipoLocal
from app.schemas.agendamentos import AgendamentoEntrada, AgendamentoSaida, MaterialUsadoSaida
from app.services.comum import (
    com_autor,
    conflito,
    fuso,
    invalido,
    nao_encontrado,
    no_fuso,
    proibido,
    sincronizar_vinculos,
)
from app.services.disponibilidade import mensagem_indisponivel
from app.services.estoque import baixar_materiais, estornar_materiais

S = StatusAgendamento
MSG_404 = 'Agendamento não encontrado.'

ROTULOS = {
    S.pendente: 'Aguardando aceite',
    S.agendado: 'Agendado',
    S.confirmado: 'Confirmado',
    S.concluido: 'Concluído',
    S.cancelado: 'Cancelado',
    S.nao_compareceu: 'Não compareceu',
}
# Não ocupam o horário (mesma regra das restrições EXCLUDE do banco)
LIBERAM_HORARIO = (S.cancelado, S.nao_compareceu)
FINAIS = frozenset({S.concluido, S.cancelado, S.nao_compareceu})
# Fluxo de status (estrutura.md, 2.13). Dos finais só sai o Administrador, reabrindo.
TRANSICOES: dict[StatusAgendamento, frozenset[StatusAgendamento]] = {
    S.pendente: frozenset({S.confirmado, S.cancelado}),
    S.agendado: frozenset({S.confirmado, S.cancelado, S.nao_compareceu}),
    S.confirmado: frozenset({S.concluido, S.cancelado, S.nao_compareceu}),
}
STATUS_INICIAIS = frozenset({S.agendado, S.confirmado})


# --- Visibilidade --------------------------------------------------------------------------------


def filtro_visiveis(ctx: ContextoLoja) -> ColumnElement[bool] | None:
    """Condição para a consulta (None = vê todos)."""
    if ctx.pode('agenda_equipe'):
        return None
    if ctx.pode('agenda_propria'):
        return Agendamento.funcionario_id == ctx.funcionario.id
    return false()


def pode_ver(ctx: ContextoLoja, ag: Agendamento) -> bool:
    return ctx.pode('agenda_equipe') or (
        ctx.pode('agenda_propria') and ag.funcionario_id == ctx.funcionario.id
    )


def pode_editar(ctx: ContextoLoja, funcionario_id: UUID) -> bool:
    return ctx.pode('agenda_equipe', NivelAcesso.escrita) or (
        ctx.pode('agenda_propria', NivelAcesso.escrita) and funcionario_id == ctx.funcionario.id
    )


def buscar_visivel(ctx: ContextoLoja, agendamento_id: UUID) -> Agendamento:
    ag = ctx.db.scalar(
        select(Agendamento).where(Agendamento.id == agendamento_id, Agendamento.loja_id == ctx.loja_id)
    )
    if ag is None or not pode_ver(ctx, ag):
        raise nao_encontrado(MSG_404)
    return ag


def exigir_edicao(ctx: ContextoLoja, ag: Agendamento) -> None:
    if not pode_editar(ctx, ag.funcionario_id):
        raise proibido('Você só pode alterar os seus próprios agendamentos.')


# --- Status --------------------------------------------------------------------------------------


def mudar_status(
    ctx: ContextoLoja, ag: Agendamento, novo: StatusAgendamento, motivo: str | None = None
) -> None:
    atual = ag.status
    if novo == atual:
        if novo == S.cancelado and motivo:
            ag.motivo_cancelamento = motivo
        return
    if novo == S.pendente:
        raise invalido('Só pedidos feitos pelo site ficam aguardando aceite.')
    if atual in FINAIS:
        if novo in FINAIS:
            raise conflito(f'Um agendamento "{ROTULOS[atual]}" não pode passar para "{ROTULOS[novo]}".')
        if not ctx.perfil.acesso_total:
            raise proibido(f'Só o Administrador pode reabrir um agendamento "{ROTULOS[atual]}".')
        if atual == S.concluido:
            estornar_materiais(ctx.db, ctx.loja_id, ag.id)
        ag.motivo_cancelamento = None
    elif novo not in TRANSICOES[atual]:
        raise conflito(f'Não é possível passar de "{ROTULOS[atual]}" para "{ROTULOS[novo]}".')
    if novo == S.cancelado:
        if not motivo:
            raise invalido('Informe o motivo do cancelamento.')
        ag.motivo_cancelamento = motivo
    ag.status = novo
    ctx.db.flush()
    if novo == S.concluido and ctx.acesso.modulo_ativo('materiais'):
        baixar_materiais(ctx.db, ctx.loja_id, ag.id)


# --- Criação e edição ----------------------------------------------------------------------------


def _carregar[M](db: Session, modelo: type[M], loja_id: UUID, id_: UUID, mensagem: str) -> M:
    obj = db.scalar(select(modelo).where(modelo.id == id_, modelo.loja_id == loja_id))  # type: ignore[attr-defined]
    if obj is None:
        raise invalido(mensagem)
    return obj


def _materiais_do_servico(db: Session, loja_id: UUID, servico_id: UUID) -> dict[UUID, dict]:
    linhas = db.execute(
        select(ServicoMaterial.material_id, ServicoMaterial.quantidade)
        .join(
            Material,
            (Material.id == ServicoMaterial.material_id) & (Material.loja_id == ServicoMaterial.loja_id),
        )
        .where(ServicoMaterial.loja_id == loja_id, ServicoMaterial.servico_id == servico_id)
    ).all()
    return {material_id: {'quantidade': quantidade} for material_id, quantidade in linhas}


def salvar(ctx: ContextoLoja, dados: AgendamentoEntrada, atual: Agendamento | None = None) -> Agendamento:
    """Cria (atual = None) ou edita um agendamento aplicando todas as regras."""
    db, loja_id = ctx.db, ctx.loja_id
    zona = fuso(ctx.loja.fuso_horario)
    com_servicos = ctx.acesso.modulo_ativo('servicos')
    com_locais = ctx.acesso.modulo_ativo('locais')
    com_materiais = ctx.acesso.modulo_ativo('materiais')

    if not pode_editar(ctx, dados.funcionario_id):
        raise proibido('Você só pode agendar para você mesmo.')
    if atual is None:
        status_inicial = dados.status or S.agendado
        if status_inicial not in STATUS_INICIAIS:
            raise invalido('Um novo agendamento começa como "Agendado" ou "Confirmado".')
    else:
        exigir_edicao(ctx, atual)
        if atual.status in FINAIS:
            if dados.status is None or dados.status in FINAIS:
                raise conflito(
                    f'Agendamento "{ROTULOS[atual.status]}" não pode ser editado. '
                    'Só o Administrador pode reabri-lo.'
                )
            mudar_status(ctx, atual, dados.status)  # reabre (o Administrador) antes de editar

    # Cliente e profissional
    cliente = _carregar(db, Cliente, loja_id, dados.cliente_id, 'Cliente não encontrado.')
    if (atual is None or atual.cliente_id != cliente.id) and not cliente.ativo:
        raise invalido('Este cliente está inativo.')
    funcionario = _carregar(db, Funcionario, loja_id, dados.funcionario_id, 'Profissional não encontrado.')
    funcionario_mudou = atual is None or atual.funcionario_id != funcionario.id
    if funcionario_mudou and not funcionario.ativo:
        raise invalido('Este profissional está inativo.')

    # Serviço: define duração, preço e quem pode atender
    servico: Servico | None = None
    servico_id = atual.servico_id if atual is not None else None  # módulo desligado: mantém o que havia
    servico_mudou = False
    if com_servicos:
        if dados.servico_id is None:
            raise invalido('Escolha o serviço.')
        servico = _carregar(db, Servico, loja_id, dados.servico_id, 'Serviço não encontrado.')
        servico_mudou = atual is None or atual.servico_id != servico.id
        if servico_mudou and not servico.ativo:
            raise invalido('Este serviço está inativo.')
        if servico_mudou or funcionario_mudou:
            habilitado = db.scalar(
                select(ServicoFuncionario.funcionario_id).where(
                    ServicoFuncionario.loja_id == loja_id,
                    ServicoFuncionario.servico_id == servico.id,
                    ServicoFuncionario.funcionario_id == funcionario.id,
                )
            )
            if habilitado is None:
                raise invalido('Este profissional não realiza o serviço escolhido.')
        servico_id = servico.id

    if dados.duracao_minutos is not None:
        duracao = dados.duracao_minutos
    elif servico is not None and (servico_mudou or atual is None):
        duracao = servico.duracao_minutos
    elif atual is not None:
        duracao = int((atual.fim - atual.inicio).total_seconds() // 60)
    else:
        raise invalido('Informe a duração do atendimento.')
    if dados.preco is not None:
        preco = dados.preco
    elif servico is not None and servico_mudou:
        preco = servico.preco
    else:
        preco = atual.preco if atual is not None else None

    inicio = no_fuso(dados.inicio, zona)
    fim = inicio + timedelta(minutes=duracao)

    # Local
    local_id = atual.local_id if atual is not None else None
    link = atual.link_reuniao if atual is not None else None
    if com_locais:
        if dados.local_id is None:
            raise invalido('Escolha o local do atendimento.')
        local = _carregar(db, Local, loja_id, dados.local_id, 'Local não encontrado.')
        local_mudou = atual is None or atual.local_id != local.id
        if local_mudou and not local.ativo:
            raise invalido('Este local está inativo.')
        if servico is not None and (local_mudou or servico_mudou):
            permitidos = set(
                db.scalars(
                    select(ServicoLocal.local_id).where(
                        ServicoLocal.loja_id == loja_id, ServicoLocal.servico_id == servico.id
                    )
                )
            )
            if permitidos and local.id not in permitidos:
                raise invalido('Este local não é permitido para o serviço escolhido.')
        local_id = local.id
        link = dados.link_reuniao if local.tipo == TipoLocal.online else None

    # Disponibilidade: jornada do perfil e bloqueios (o conflito de horário fica com o banco)
    status_final = dados.status or (atual.status if atual is not None else status_inicial)
    horario_mudou = atual is None or funcionario_mudou or inicio != atual.inicio or fim != atual.fim
    if horario_mudou and status_final not in LIBERAM_HORARIO:
        aviso = mensagem_indisponivel(db, loja_id, funcionario, inicio, fim, zona)
        if aviso:
            raise invalido(aviso)

    valores = {
        'cliente_id': cliente.id,
        'servico_id': servico_id,
        'funcionario_id': funcionario.id,
        'local_id': local_id,
        'link_reuniao': link,
        'inicio': inicio,
        'fim': fim,
        'preco': preco,
        'observacoes': dados.observacoes,
    }
    if atual is None:
        ag = Agendamento(loja_id=loja_id, status=status_inicial, origem=OrigemAgendamento.painel, **valores)
        db.add(ag)
        db.flush()
        if com_materiais and servico is not None:
            for material_id, extra in _materiais_do_servico(db, loja_id, servico.id).items():
                db.add(
                    AgendamentoMaterial(
                        loja_id=loja_id, agendamento_id=ag.id, material_id=material_id, **extra
                    )
                )
            db.flush()
        return ag

    ag = atual
    for campo, valor in valores.items():
        if getattr(ag, campo) != valor:
            setattr(ag, campo, valor)
    db.flush()
    if com_materiais and servico is not None and servico_mudou and ag.status != S.concluido:
        materiais = _materiais_do_servico(db, loja_id, servico.id)
        sincronizar_vinculos(
            db, AgendamentoMaterial, loja_id, {'agendamento_id': ag.id}, 'material_id', materiais
        )
    if dados.status is not None and dados.status != ag.status:
        mudar_status(ctx, ag, dados.status, dados.motivo_cancelamento)
    return ag


def ajustar_materiais(ctx: ContextoLoja, ag: Agendamento, itens: dict[UUID, dict]) -> None:
    """O profissional ajusta o que usou antes de concluir (2.14)."""
    if not ctx.acesso.modulo_ativo('materiais'):
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Este módulo não está ativo na sua loja.')
    if ag.status in FINAIS:
        raise conflito('Os materiais só podem ser ajustados antes de concluir o atendimento.')
    encontrados = set(
        ctx.db.scalars(
            select(Material.id).where(Material.loja_id == ctx.loja_id, Material.id.in_(list(itens)))
        )
    )
    if len(encontrados) != len(itens):
        raise invalido('Material não encontrado.')
    sincronizar_vinculos(
        ctx.db, AgendamentoMaterial, ctx.loja_id, {'agendamento_id': ag.id}, 'material_id', itens
    )


# --- Saída ---------------------------------------------------------------------------------------


def descrever(
    ctx: ContextoLoja, agendamentos: list[Agendamento], *, com_materiais: bool = False
) -> list[AgendamentoSaida]:
    """Agendamentos com nomes (cliente, serviço, profissional, local), datas no fuso da loja."""
    db, loja_id = ctx.db, ctx.loja_id
    zona = fuso(ctx.loja.fuso_horario)

    def mapa(modelo, ids, *colunas):
        ids = {i for i in ids if i is not None}
        if not ids:
            return {}
        linhas = db.execute(
            select(modelo.id, *colunas)
            .where(modelo.loja_id == loja_id, modelo.id.in_(ids))
            .execution_options(incluir_excluidos=True)
        ).all()
        return {linha[0]: linha[1:] for linha in linhas}

    clientes = mapa(Cliente, (a.cliente_id for a in agendamentos), Cliente.nome, Cliente.sobrenome)
    servicos = mapa(Servico, (a.servico_id for a in agendamentos), Servico.nome)
    funcionarios = mapa(
        Funcionario, (a.funcionario_id for a in agendamentos), Funcionario.nome, Funcionario.cor_agenda
    )
    locais = mapa(Local, (a.local_id for a in agendamentos), Local.nome, Local.tipo, Local.link_padrao)
    materiais: dict[UUID, list[MaterialUsadoSaida]] = {}
    if com_materiais:
        for ag_id, quantidade, material in db.execute(
            select(AgendamentoMaterial.agendamento_id, AgendamentoMaterial.quantidade, Material)
            .join(
                Material,
                (Material.id == AgendamentoMaterial.material_id)
                & (Material.loja_id == AgendamentoMaterial.loja_id),
            )
            .where(
                AgendamentoMaterial.loja_id == loja_id,
                AgendamentoMaterial.agendamento_id.in_([a.id for a in agendamentos]),
            )
            .order_by(Material.nome)
        ):
            materiais.setdefault(ag_id, []).append(
                MaterialUsadoSaida(
                    material_id=material.id,
                    nome=material.nome,
                    unidade=material.unidade,
                    quantidade=quantidade,
                )
            )

    saida = []
    for a in agendamentos:
        item = AgendamentoSaida.model_validate(a)
        item.inicio, item.fim = a.inicio.astimezone(zona), a.fim.astimezone(zona)
        item.duracao_minutos = int((a.fim - a.inicio).total_seconds() // 60)
        if a.cliente_id in clientes:
            nome, sobrenome = clientes[a.cliente_id]
            item.cliente_nome = f'{nome} {sobrenome}'
        if a.servico_id in servicos:
            item.servico_nome = servicos[a.servico_id][0]
        if a.funcionario_id in funcionarios:
            item.funcionario_nome, item.cor_agenda = funcionarios[a.funcionario_id]
        if a.local_id in locais:
            item.local_nome, item.local_tipo, link_padrao = locais[a.local_id]
            item.link = a.link_reuniao or (link_padrao if item.local_tipo == TipoLocal.online else None)
        if com_materiais:
            item.materiais = materiais.get(a.id, [])
        saida.append(item)
    return com_autor(db, loja_id, saida)


def ocupa_intervalo(inicio: datetime, fim: datetime) -> list[ColumnElement[bool]]:
    """Condições de um agendamento que ocupa algum ponto de [inicio, fim)."""
    return [
        Agendamento.inicio < fim,
        Agendamento.fim > inicio,
        Agendamento.status.not_in(LIBERAM_HORARIO),
    ]
