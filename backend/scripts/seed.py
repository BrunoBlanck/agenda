"""Seed de desenvolvimento: reproduz frontend/src/data/mock.js e plataforma.js.

Idempotente: procura cada registro pela chave natural (e-mail, slug, nome, CPF...) e só cria o
que falta. Agendamentos, bloqueios, jornadas e registros de ponto (que não têm chave natural e usam
datas relativas a hoje) só são criados se a loja ainda não tiver nenhum.

Senhas de desenvolvimento (ver backend/README.md):
- superadmins: superadmin123
- funcionários de todas as lojas: senha123

Uso: uv run python -m scripts.seed
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.auth.senhas import gerar_hash
from app.config import get_settings
from app.db import definir_contexto, get_engine
from app.models import (
    Agendamento,
    AgendamentoMaterial,
    BloqueioAgenda,
    Cargo,
    CategoriaMaterial,
    Cliente,
    Funcionalidade,
    Funcionario,
    Local,
    Loja,
    LojaFuncionalidade,
    Material,
    MovimentacaoEstoque,
    Perfil,
    PerfilHorario,
    Plano,
    RegistroPonto,
    Servico,
    ServicoFuncionario,
    ServicoLocal,
    ServicoMaterial,
    SuperadminUsuario,
)
from app.models.enums import (
    CanalCliente,
    OrigemAgendamento,
    StatusAgendamento,
    TipoLocal,
    TipoLoja,
    TipoMovimentacao,
)
from app.services.lojas import provisionar_loja

SENHA_SUPERADMIN = 'superadmin123'
SENHA_FUNCIONARIO = 'senha123'

SUPERADMINS = [
    ('Rafael Mendes', 'rafael@agendaplataforma.com'),
    ('Camila Rocha', 'camila@agendaplataforma.com'),
]

PLANOS = [
    ('Básico', 'Para quem está começando', Decimal('89.90')),
    ('Profissional', 'Equipes de até 15 pessoas', Decimal('189.90')),
    ('Rede', 'Para redes com várias unidades e equipe grande', Decimal('449.90')),
]

# Funcionários: (nome, email, perfil, cargo, cor, telefone, ativo)
LOJAS = [
    {
        'dados': {
            'tipo': TipoLoja.clinica,
            'slug': 'clinica-sorriso',
            'nome_fantasia': 'Clínica Sorriso',
            'nome': 'Clínica Sorriso Serviços Odontológicos Ltda',
            'cnpj': '11.222.333/0001-81',
            'telefone': '(11) 3333-4444',
            'email': 'contato@clinicasorriso.com',
            'cep': '01310-100',
            'logradouro': 'Avenida Paulista',
            'numero': '1000',
            'complemento': 'Sala 52',
            'bairro': 'Bela Vista',
            'cidade': 'São Paulo',
            'uf': 'SP',
        },
        'plano': 'Profissional',
        'modulos': {'servicos': True, 'materiais': True, 'controle_tempo': True, 'locais': True},
        'rotulos': ('Consultório', 'Consultórios'),
        'funcionarios': [
            (
                'Dra. Ana Souza',
                'ana@clinica.com',
                'Administrador',
                'Dentista',
                '#0f766e',
                '(11) 99999-0001',
                True,
            ),
            (
                'Dr. Carlos Lima',
                'carlos@clinica.com',
                'Profissional',
                'Fisioterapeuta',
                '#2563eb',
                '(11) 99999-0002',
                True,
            ),
            (
                'Juliana Alves',
                'juliana@clinica.com',
                'Recepção',
                'Recepcionista',
                '#d97706',
                '(11) 99999-0003',
                True,
            ),
        ],
    },
    {
        'dados': {
            'tipo': TipoLoja.barbearia,
            'slug': 'barbearia-navalha',
            'nome_fantasia': 'Barbearia Navalha',
            'nome': 'Navalha Cortes Masculinos ME',
            'email': 'contato@navalha.com',
            'telefone': '(19) 3222-1010',
            'cidade': 'Campinas',
            'uf': 'SP',
        },
        'plano': 'Básico',
        'modulos': {'servicos': True, 'materiais': False, 'controle_tempo': False, 'locais': True},
        'observacoes': {'locais': 'Cortesia: agenda por cadeira'},
        'rotulos': ('Cadeira', 'Cadeiras'),
        'funcionarios': [
            ('Marcos Silva', 'marcos@navalha.com', 'Administrador', None, None, None, True),
            ('Diego Alves', 'diego@navalha.com', 'Profissional', None, None, None, True),
        ],
    },
    {
        'dados': {
            'tipo': TipoLoja.escola,
            'slug': 'escola-harmonia',
            'nome_fantasia': 'Escola de Música Harmonia',
            'nome': 'Harmonia Ensino Musical Ltda',
            'email': 'secretaria@harmonia.com',
            'telefone': '(31) 3555-2020',
            'cidade': 'Belo Horizonte',
            'uf': 'MG',
        },
        'plano': 'Profissional',
        'modulos': {'servicos': True, 'materiais': False, 'controle_tempo': True, 'locais': True},
        'observacoes': {'materiais': 'Escola não usa estoque'},
        'rotulos': ('Sala', 'Salas'),
        'funcionarios': [
            ('Paula Antunes', 'paula@harmonia.com', 'Administrador', None, None, None, True),
            ('Lucas Prado', 'lucas@harmonia.com', 'Profissional', None, None, None, True),
            ('Beatriz Lima', 'beatriz@harmonia.com', 'Profissional', None, None, None, True),
            ('Renata Dias', 'renata@harmonia.com', 'Recepção', None, None, None, True),
        ],
    },
    {
        'dados': {
            'tipo': TipoLoja.clinica,
            'slug': 'clinica-bem-estar',
            'nome_fantasia': 'Clínica Bem Estar',
            'nome': 'Bem Estar Fisioterapia Ltda',
            'email': 'contato@bemestar.com',
            'telefone': '(21) 3444-3030',
            'cidade': 'Rio de Janeiro',
            'uf': 'RJ',
            'status': 'suspensa',
        },
        'plano': 'Básico',
        'modulos': {'servicos': True, 'materiais': False, 'controle_tempo': False, 'locais': False},
        'funcionarios': [('Sérgio Nunes', 'sergio@bemestar.com', 'Administrador', None, None, None, True)],
    },
    {
        'dados': {
            'tipo': TipoLoja.barbearia,
            'slug': 'dom-corte',
            'nome_fantasia': 'Dom Corte',
            'nome': 'Dom Corte Barbearia ME',
            'email': 'domcorte@email.com',
            'telefone': '(41) 3111-4040',
            'cidade': 'Curitiba',
            'uf': 'PR',
            'status': 'cancelada',
        },
        'plano': 'Básico',
        'modulos': {'servicos': True, 'materiais': False, 'controle_tempo': False, 'locais': False},
        'funcionarios': [('Igor Campos', 'igor@domcorte.com', 'Administrador', None, None, None, False)],
    },
]


def _obter(db: Session, modelo, *condicoes):
    return db.scalar(select(modelo).where(*condicoes))


def _vazio(db: Session, modelo, loja_id: UUID) -> bool:
    total = db.scalar(select(func.count()).select_from(modelo).where(modelo.loja_id == loja_id))
    return not total


class _Relogio:
    """Converte 'dia relativo a hoje + hora' do fuso da loja para timestamptz."""

    def __init__(self, fuso: str) -> None:
        self.fuso = ZoneInfo(fuso)
        self.hoje = datetime.now(self.fuso).date()

    def dia(self, dias: int) -> date:
        return self.hoje + timedelta(days=dias)

    def em(self, dias: int | date, hora: str) -> datetime:
        data = dias if isinstance(dias, date) else self.dia(dias)
        h, m = (int(p) for p in hora.split(':'))
        return datetime.combine(data, time(h, m), tzinfo=self.fuso)

    def proxima_segunda(self) -> date:
        # dayjs().day(8): segunda-feira da semana que vem
        domingo = self.hoje - timedelta(days=(self.hoje.weekday() + 1) % 7)
        return domingo + timedelta(days=8)


def _superadmins(db: Session) -> SuperadminUsuario:
    hash_senha = gerar_hash(SENHA_SUPERADMIN)
    primeiro = None
    for nome, email in SUPERADMINS:
        sa = _obter(db, SuperadminUsuario, func.lower(SuperadminUsuario.email) == email)
        if sa is None:
            sa = SuperadminUsuario(nome=nome, email=email, senha_hash=hash_senha)
            db.add(sa)
            db.flush()
        primeiro = primeiro or sa
    if primeiro is None:
        raise RuntimeError('Nenhum superadmin cadastrado.')
    return primeiro


def _loja(db: Session, modelo: dict, planos: dict[str, Plano]) -> tuple[Loja, dict[str, Perfil]]:
    loja = _obter(db, Loja, Loja.slug == modelo['dados']['slug'])
    if loja is None:
        loja = Loja(**modelo['dados'], plano_id=planos[modelo['plano']].id)
        db.add(loja)
        db.flush()
        rotulo, plural = modelo.get('rotulos', ('Local', 'Locais'))
        provisionar_loja(db, loja.id, modelo['modulos'], rotulo, plural)
        for codigo, observacao in modelo.get('observacoes', {}).items():
            registro = db.scalar(
                select(LojaFuncionalidade)
                .join(Funcionalidade, Funcionalidade.id == LojaFuncionalidade.funcionalidade_id)
                .where(LojaFuncionalidade.loja_id == loja.id, Funcionalidade.codigo == codigo)
            )
            registro.observacao = observacao
    perfis = {p.nome: p for p in db.scalars(select(Perfil).where(Perfil.loja_id == loja.id))}
    return loja, perfis


def _funcionarios(db: Session, loja: Loja, perfis: dict[str, Perfil], lista: list) -> dict[str, Funcionario]:
    hash_senha = gerar_hash(SENHA_FUNCIONARIO)
    resultado: dict[str, Funcionario] = {}
    for nome, email, perfil, cargo_nome, cor, telefone, ativo in lista:
        cargo = None
        if cargo_nome:
            cargo = _obter(db, Cargo, Cargo.loja_id == loja.id, Cargo.nome == cargo_nome)
            if cargo is None:
                cargo = Cargo(loja_id=loja.id, nome=cargo_nome)
                db.add(cargo)
                db.flush()
        func_ = _obter(
            db, Funcionario, Funcionario.loja_id == loja.id, func.lower(Funcionario.email) == email
        )
        if func_ is None:
            func_ = Funcionario(
                loja_id=loja.id,
                perfil_id=perfis[perfil].id,
                cargo_id=cargo.id if cargo else None,
                nome=nome,
                email=email,
                senha_hash=hash_senha,
                telefone=telefone,
                cor_agenda=cor,
                ativo=ativo,
            )
            db.add(func_)
            db.flush()
        resultado[email] = func_
    return resultado


def _clinica_sorriso(
    db: Session, loja: Loja, perfis: dict[str, Perfil], equipe: dict[str, Funcionario]
) -> None:
    """Dados do painel da loja (mock.js)."""
    lid = loja.id
    rel = _Relogio(loja.fuso_horario)
    ana, carlos = equipe['ana@clinica.com'], equipe['carlos@clinica.com']

    # Jornadas dos perfis
    if _vazio(db, PerfilHorario, lid):
        jornadas = [
            ('Administrador', [1, 2, 3, 4, 5], [('08:00', '12:00'), ('13:00', '18:00')]),
            ('Profissional', [1, 2, 3, 4, 5], [('09:00', '17:00')]),
            ('Profissional', [6], [('08:00', '12:00')]),
            ('Recepção', [1, 2, 3, 4, 5, 6], [('07:30', '17:00')]),
        ]
        for perfil, dias, faixas in jornadas:
            for dia in dias:
                for ini, fim in faixas:
                    db.add(
                        PerfilHorario(
                            loja_id=lid,
                            perfil_id=perfis[perfil].id,
                            dia_semana=dia,
                            hora_inicio=time.fromisoformat(ini),
                            hora_fim=time.fromisoformat(fim),
                        )
                    )

    # Bloqueios
    if _vazio(db, BloqueioAgenda, lid):
        segunda = rel.proxima_segunda()
        db.add(
            BloqueioAgenda(
                loja_id=lid, inicio=rel.em(segunda, '00:00'), fim=rel.em(segunda, '23:59'), motivo='Feriado'
            )
        )
        db.add(
            BloqueioAgenda(
                loja_id=lid,
                funcionario_id=carlos.id,
                inicio=rel.em(1, '15:00'),
                fim=rel.em(1, '17:00'),
                motivo='Consulta médica',
            )
        )

    # Clientes (chave: CPF)
    clientes_mock = [
        (
            'Maria',
            'Oliveira',
            '123.456.789-00',
            '(11) 98888-1111',
            'maria@email.com',
            date(1985, 4, 12),
            ['loja', 'whatsapp'],
        ),
        (
            'João',
            'Pereira',
            '987.654.321-00',
            '(11) 98888-2222',
            'joao@email.com',
            date(1990, 9, 30),
            ['whatsapp'],
        ),
        (
            'Fernanda',
            'Costa',
            '111.222.333-44',
            '(11) 98888-3333',
            'fernanda@email.com',
            date(1978, 1, 5),
            ['loja', 'site'],
        ),
    ]
    clientes = []
    for nome, sobrenome, cpf, telefone, email, nascimento, canais in clientes_mock:
        cliente = _obter(db, Cliente, Cliente.loja_id == lid, Cliente.cpf == cpf)
        if cliente is None:
            cliente = Cliente(
                loja_id=lid,
                nome=nome,
                sobrenome=sobrenome,
                cpf=cpf,
                telefone=telefone,
                email=email,
                data_nascimento=nascimento,
                canais=[CanalCliente(c) for c in canais],
            )
            db.add(cliente)
            db.flush()
        clientes.append(cliente)

    # Materiais (estoque inicial lançado como entrada)
    materiais_mock = [
        ('Luvas descartáveis (cx)', 'Descartáveis', 25, 10, 'cx'),
        ('Máscaras cirúrgicas (cx)', 'Descartáveis', 6, 10, 'cx'),
        ('Anestésico local', 'Medicamentos', 40, 20, 'un'),
        ('Gaze estéril', 'Curativos', 3, 15, 'pct'),
    ]
    materiais = []
    for nome, categoria_nome, quantidade, minimo, unidade in materiais_mock:
        categoria = _obter(
            db, CategoriaMaterial, CategoriaMaterial.loja_id == lid, CategoriaMaterial.nome == categoria_nome
        )
        if categoria is None:
            categoria = CategoriaMaterial(loja_id=lid, nome=categoria_nome)
            db.add(categoria)
            db.flush()
        material = _obter(db, Material, Material.loja_id == lid, Material.nome == nome)
        if material is None:
            material = Material(
                loja_id=lid,
                categoria_id=categoria.id,
                nome=nome,
                unidade=unidade,
                estoque_minimo=Decimal(minimo),
            )
            db.add(material)
            db.flush()
            db.add(
                MovimentacaoEstoque(
                    loja_id=lid,
                    material_id=material.id,
                    tipo=TipoMovimentacao.entrada,
                    quantidade=Decimal(quantidade),
                )
            )
        materiais.append(material)

    # Locais
    locais_mock = [
        ('Consultório 1', TipoLocal.presencial, 'Cadeira odontológica e raio-x', None),
        ('Consultório 2', TipoLocal.presencial, 'Cadeira odontológica', None),
        ('Sala de fisioterapia', TipoLocal.presencial, 'Macas e aparelhos', None),
        ('Online · Dr. Carlos', TipoLocal.online, None, 'https://meet.google.com/abc-defg-hij'),
    ]
    locais = []
    for nome, tipo, descricao, link in locais_mock:
        local = _obter(db, Local, Local.loja_id == lid, Local.nome == nome)
        if local is None:
            local = Local(loja_id=lid, nome=nome, tipo=tipo, descricao=descricao, link_padrao=link)
            db.add(local)
            db.flush()
        locais.append(local)

    # Serviços: (nome, duração, preço, profissionais, materiais [(índice, qtd)], locais)
    servicos_mock = [
        ('Limpeza', 60, 200, [ana], [(0, 1), (3, 2)], [0, 1]),
        ('Avaliação', 30, 100, [ana, carlos], [(0, 1), (1, 1)], []),
        ('Sessão de fisioterapia', 45, 150, [carlos], [], [2, 3]),
    ]
    servicos = []
    for nome, duracao, preco, profissionais, mats, locs in servicos_mock:
        servico = _obter(db, Servico, Servico.loja_id == lid, Servico.nome == nome)
        if servico is None:
            servico = Servico(loja_id=lid, nome=nome, duracao_minutos=duracao, preco=Decimal(preco))
            db.add(servico)
            db.flush()
            for prof in profissionais:
                db.add(ServicoFuncionario(loja_id=lid, servico_id=servico.id, funcionario_id=prof.id))
            for indice, qtd in mats:
                db.add(
                    ServicoMaterial(
                        loja_id=lid,
                        servico_id=servico.id,
                        material_id=materiais[indice].id,
                        quantidade=Decimal(qtd),
                    )
                )
            for indice in locs:
                db.add(ServicoLocal(loja_id=lid, servico_id=servico.id, local_id=locais[indice].id))
            db.flush()
        servicos.append(servico)

    # Agendamentos (mock.js). O nº 4 foi movido de 09:30 para 10:00: no mock ele se sobrepõe ao
    # nº 1 da mesma profissional, o que o banco não permite.
    if _vazio(db, Agendamento, lid):
        maria, joao, fernanda = clientes
        limpeza, avaliacao, fisio = servicos
        c1, c2, sala_fisio, online = locais
        st = StatusAgendamento
        agendamentos = [
            (maria, ana, c1, 0, '09:00', limpeza, st.confirmado),
            (joao, carlos, sala_fisio, 0, '10:30', fisio, st.agendado),
            (fernanda, ana, c2, 1, '14:00', avaliacao, st.agendado),
            (joao, ana, c2, 0, '10:00', avaliacao, st.agendado),
            (fernanda, carlos, online, 0, '14:00', fisio, st.confirmado),
            (maria, carlos, sala_fisio, -1, '11:00', fisio, st.concluido),
            (joao, ana, c1, -1, '16:00', limpeza, st.nao_compareceu),
            (fernanda, ana, c1, 2, '08:30', limpeza, st.agendado),
            (maria, carlos, c2, 2, '10:00', avaliacao, st.cancelado),
            (fernanda, carlos, c2, 1, '09:00', avaliacao, st.pendente),
        ]
        for cliente, prof, local, dia, hora, servico, status in agendamentos:
            inicio = rel.em(dia, hora)
            agendamento = Agendamento(
                loja_id=lid,
                cliente_id=cliente.id,
                funcionario_id=prof.id,
                local_id=local.id,
                servico_id=servico.id,
                inicio=inicio,
                fim=inicio + timedelta(minutes=servico.duracao_minutos),
                preco=servico.preco,
                status=status,
                origem=OrigemAgendamento.site if status == st.pendente else OrigemAgendamento.painel,
                motivo_cancelamento='Cliente desmarcou' if status == st.cancelado else None,
            )
            db.add(agendamento)
            db.flush()
            # Cópia dos materiais do serviço (estrutura.md, 2.14)
            for sm in db.scalars(select(ServicoMaterial).where(ServicoMaterial.servico_id == servico.id)):
                db.add(
                    AgendamentoMaterial(
                        loja_id=lid,
                        agendamento_id=agendamento.id,
                        material_id=sm.material_id,
                        quantidade=sm.quantidade,
                    )
                )

    # Ponto
    if _vazio(db, RegistroPonto, lid):
        juliana = equipe['juliana@clinica.com']
        db.add(RegistroPonto(loja_id=lid, funcionario_id=ana.id, entrada=rel.em(0, '08:00')))
        db.add(RegistroPonto(loja_id=lid, funcionario_id=juliana.id, entrada=rel.em(0, '07:45')))
        db.add(
            RegistroPonto(
                loja_id=lid, funcionario_id=carlos.id, entrada=rel.em(-1, '08:10'), saida=rel.em(-1, '17:05')
            )
        )


def _outras_lojas(db: Session, lojas: dict[str, Loja], equipes: dict[str, dict[str, Funcionario]]) -> None:
    """Poucos dados nas outras lojas, citados no histórico de plataforma.js."""
    navalha = lojas['barbearia-navalha']
    if _obter(db, Servico, Servico.loja_id == navalha.id, Servico.nome == 'Corte + barba') is None:
        servico = Servico(loja_id=navalha.id, nome='Corte + barba', duracao_minutos=50, preco=Decimal(70))
        db.add(servico)
        db.flush()
        diego = equipes['barbearia-navalha']['diego@navalha.com']
        db.add(ServicoFuncionario(loja_id=navalha.id, servico_id=servico.id, funcionario_id=diego.id))
    for nome in ('Cadeira 1', 'Cadeira 2'):
        if _obter(db, Local, Local.loja_id == navalha.id, Local.nome == nome) is None:
            db.add(Local(loja_id=navalha.id, nome=nome))

    harmonia = lojas['escola-harmonia']
    if _obter(db, Local, Local.loja_id == harmonia.id, Local.nome == 'Sala 101') is None:
        db.add(Local(loja_id=harmonia.id, nome='Sala 101', descricao='Piano de cauda, isolamento acústico'))


def executar(engine: Engine | None = None) -> None:
    if get_settings().ambiente == 'producao':
        raise SystemExit('O seed de desenvolvimento não roda em produção.')
    engine = engine or get_engine()
    with Session(engine, expire_on_commit=False) as db, db.begin():
        definir_contexto(db, origem='sistema')
        superadmin = _superadmins(db)
        # Como superadmin: enxerga todas as lojas (RLS) e fica registrado na auditoria
        definir_contexto(db, origem='sistema', superadmin_id=superadmin.id)

        planos = {}
        for nome, descricao, preco in PLANOS:
            plano = _obter(db, Plano, Plano.nome == nome)
            if plano is None:
                plano = Plano(nome=nome, descricao=descricao, preco_mensal=preco)
                db.add(plano)
                db.flush()
            planos[nome] = plano

        lojas: dict[str, Loja] = {}
        equipes: dict[str, dict[str, Funcionario]] = {}
        perfis_por_loja: dict[str, dict[str, Perfil]] = {}
        for modelo in LOJAS:
            loja, perfis = _loja(db, modelo, planos)
            slug = loja.slug
            lojas[slug] = loja
            perfis_por_loja[slug] = perfis
            equipes[slug] = _funcionarios(db, loja, perfis, modelo['funcionarios'])

        _clinica_sorriso(
            db, lojas['clinica-sorriso'], perfis_por_loja['clinica-sorriso'], equipes['clinica-sorriso']
        )
        _outras_lojas(db, lojas, equipes)


if __name__ == '__main__':
    executar()
    print('Seed concluído.')
