"""Início: resumo do dia conforme o acesso de cada perfil."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.models import Agendamento, Cliente, Material, MovimentacaoEstoque, RegistroPonto
from app.models.enums import OrigemAgendamento, StatusAgendamento, TipoMovimentacao
from tests.fabricas import inserir, usuario_com

URL = '/api/loja/inicio'
SP = ZoneInfo('America/Sao_Paulo')


def _cenario(engine, lt):
    maria = inserir(engine, Cliente(loja_id=lt.loja.id, nome='Maria', sobrenome='Lima', telefone='1'))
    excluido = inserir(engine, Cliente(loja_id=lt.loja.id, nome='Ex', sobrenome='Cluído', telefone='2'))
    with engine.begin() as conexao:
        conexao.execute(
            Cliente.__table__.update().where(Cliente.id == excluido.id).values(excluido_em=datetime.now(UTC))
        )
    agora = datetime.now(SP).replace(hour=10, minute=0, second=0, microsecond=0)

    def agendar(funcionario, inicio, status=StatusAgendamento.agendado, origem=OrigemAgendamento.painel):
        return inserir(
            engine,
            Agendamento(
                loja_id=lt.loja.id,
                cliente_id=maria.id,
                funcionario_id=funcionario.id,
                inicio=inicio,
                fim=inicio + timedelta(minutes=30),
                status=status,
                origem=origem,
            ),
        ).id

    ids = {
        'prof_hoje': agendar(lt.prof, agora),
        'admin_hoje': agendar(lt.admin, agora.replace(hour=9)),
        'amanha': agendar(lt.prof, agora + timedelta(days=1)),
        'pendente': agendar(
            lt.prof, agora + timedelta(days=2), StatusAgendamento.pendente, OrigemAgendamento.site
        ),
    }
    inserir(
        engine,
        RegistroPonto(
            loja_id=lt.loja.id, funcionario_id=lt.recepcao.id, entrada=datetime.now(UTC) - timedelta(hours=1)
        ),
    )
    inserir(
        engine,
        RegistroPonto(
            loja_id=lt.loja.id,
            funcionario_id=lt.prof.id,
            entrada=datetime.now(UTC) - timedelta(hours=3),
            saida=datetime.now(UTC) - timedelta(hours=2),
        ),
    )
    gaze = inserir(engine, Material(loja_id=lt.loja.id, nome='Gaze', unidade='pct', estoque_minimo=15))
    luvas = inserir(engine, Material(loja_id=lt.loja.id, nome='Luvas', unidade='cx', estoque_minimo=10))
    inserir(
        engine,
        MovimentacaoEstoque(
            loja_id=lt.loja.id, material_id=gaze.id, tipo=TipoMovimentacao.entrada, quantidade=3
        ),
    )
    inserir(
        engine,
        MovimentacaoEstoque(
            loja_id=lt.loja.id, material_id=luvas.id, tipo=TipoMovimentacao.entrada, quantidade=25
        ),
    )
    return ids


def test_resumo_do_administrador(cliente, lojas, engine_dono):
    a, _ = lojas
    ids = _cenario(engine_dono, a)
    resumo = cliente.get(URL, headers=a.h_admin).json()
    assert resumo['data'] == datetime.now(SP).date().isoformat()
    assert [ag['id'] for ag in resumo['agenda_hoje']] == [str(ids['admin_hoje']), str(ids['prof_hoje'])]
    assert resumo['so_propria'] is False
    assert [ag['id'] for ag in resumo['solicitacoes_site']] == [str(ids['pendente'])]
    assert resumo['clientes_cadastrados'] == 1  # o excluído não conta
    assert resumo['funcionarios_em_servico'] == 1
    [em_servico] = resumo['equipe_em_servico']
    assert (em_servico['funcionario_id'], em_servico['nome']) == (str(a.recepcao.id), 'Recepção')
    assert em_servico['entrada'].endswith('-03:00')  # fuso da loja
    assert [(m['nome'], m['quantidade_atual']) for m in resumo['materiais_a_repor']] == [('Gaze', 3)]


def test_resumo_do_profissional_e_de_quem_nao_ve_nada(cliente, lojas, engine_dono):
    a, _ = lojas
    ids = _cenario(engine_dono, a)
    do_prof = cliente.get(URL, headers=a.h_prof).json()
    assert [ag['id'] for ag in do_prof['agenda_hoje']] == [str(ids['prof_hoje'])]
    assert do_prof['so_propria'] is True
    assert do_prof['clientes_cadastrados'] == 1  # leitura em clientes
    assert do_prof['funcionarios_em_servico'] is None
    assert do_prof['equipe_em_servico'] is None
    assert do_prof['materiais_a_repor'] is None

    nada = usuario_com(engine_dono, a.loja, {})
    vazio = cliente.get(URL, headers=nada)
    assert vazio.status_code == 200
    corpo = vazio.json()
    assert corpo['agenda_hoje'] is None
    assert corpo['solicitacoes_site'] is None
    assert corpo['clientes_cadastrados'] is None


def test_isolamento_entre_lojas(cliente, lojas, engine_dono):
    a, b = lojas
    _cenario(engine_dono, a)
    da_b = cliente.get(URL, headers=b.h_admin).json()
    assert da_b['agenda_hoje'] == []
    assert da_b['solicitacoes_site'] == []
    assert da_b['clientes_cadastrados'] == 0
    assert da_b['funcionarios_em_servico'] == 0
    assert da_b['equipe_em_servico'] == []
    assert da_b['materiais_a_repor'] == []
