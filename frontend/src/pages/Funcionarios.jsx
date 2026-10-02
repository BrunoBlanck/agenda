import { ColorPicker, Col, Form, Input, Row, Select, Switch } from 'antd'
import { LockOutlined } from '@ant-design/icons'
import CadastroTabela from '../components/CadastroTabela.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import PontoCor from '../components/base/PontoCor.jsx'
import { EtiquetaSituacao } from '../components/Etiquetas.jsx'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { COR_PADRAO } from '../components/agenda/util.js'
import { mascaraTelefone } from '../utils/formatos.js'
import { coresAgenda } from '../tema.js'

const cargos = ['Dentista', 'Médico(a)', 'Fisioterapeuta', 'Enfermeiro(a)', 'Recepcionista', 'Administrador']

export default function Funcionarios() {
  const { funcionarios, perfis } = useData()
  const { pode, perfil: meuPerfil } = useAcesso()

  const perfil = (id) => perfis.itens.find((p) => p.id === id)
  const ehAdmin = (f) => !!perfil(f.perfilId)?.acessoTotal
  const souAdmin = !!meuPerfil?.acessoTotal

  // Só um Administrador atribui (ou altera) o perfil Administrador
  const opcoesPerfil = perfis.itens.map((p) => ({ value: p.id, label: p.nome, disabled: p.acessoTotal && !souAdmin }))

  const validar = (valores, item) => {
    if (!item.id) return
    if (ehAdmin(item) && !souAdmin) return 'Só um Administrador pode alterar outro Administrador.'
    const continuaAdmin = valores.ativo && perfil(valores.perfilId)?.acessoTotal
    const outrosAdmins = funcionarios.itens.filter((f) => f.id !== item.id && f.ativo && ehAdmin(f))
    if (ehAdmin(item) && !continuaAdmin && outrosAdmins.length === 0) {
      return 'A loja precisa de pelo menos um Administrador ativo. Defina outro antes de mudar este.'
    }
  }

  const colunas = [
    {
      title: 'Nome',
      dataIndex: 'nome',
      sorter: (a, b) => a.nome.localeCompare(b.nome),
      render: (nome, f) => (
        <span className="com-ponto">
          <PontoCor cor={f.cor ?? COR_PADRAO} />
          <strong>{nome}</strong>
        </span>
      ),
    },
    { title: 'Cargo', dataIndex: 'cargo', filters: cargos.map((c) => ({ text: c, value: c })), onFilter: (v, r) => r.cargo === v },
    {
      title: 'Perfil',
      dataIndex: 'perfilId',
      render: (id) =>
        perfil(id)?.acessoTotal ? (
          <Etiqueta tom="tinta" icone={<LockOutlined />}>
            {perfil(id).nome}
          </Etiqueta>
        ) : (
          <Etiqueta tom="contorno">{perfil(id)?.nome ?? '—'}</Etiqueta>
        ),
    },
    { title: 'E-mail (login)', dataIndex: 'email' },
    { title: 'Telefone', dataIndex: 'telefone' },
    { title: 'Situação', dataIndex: 'ativo', render: (ativo) => <EtiquetaSituacao ativo={ativo} /> },
  ]

  return (
    <CadastroTabela
      titulo="Funcionários"
      descricao="Quem trabalha na loja. O perfil de cada um define o que ele acessa e a jornada de trabalho."
      item="funcionário"
      lista={funcionarios}
      colunas={colunas}
      somenteLeitura={!pode('funcionarios', 'escrita')}
      permitirExcluir={false}
      validar={validar}
      valoresNovo={{ cor: coresAgenda[0], ativo: true }}
      corRegistro={(f) => f.cor ?? COR_PADRAO}
      campos={
        <>
          <h3 className="grupo-formulario">Dados do funcionário</h3>
          <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
            <Input maxLength={100} />
          </Form.Item>
          <Row gutter={12}>
            <Col xs={24} sm={12}>
              <Form.Item name="cargo" label="Cargo" rules={[{ required: true, message: 'Escolha o cargo' }]} extra="Informativo. Quem define o acesso é o perfil.">
                <Select options={cargos.map((c) => ({ value: c, label: c }))} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item name="telefone" label="Telefone" normalize={mascaraTelefone}>
                <Input inputMode="tel" placeholder="Opcional" />
              </Form.Item>
            </Col>
          </Row>

          <h3 className="grupo-formulario">Acesso ao sistema</h3>
          <Form.Item
            name="email"
            label="E-mail (login)"
            validateTrigger="onBlur"
            rules={[
              { required: true, message: 'Informe o e-mail de login' },
              { type: 'email', message: 'E-mail inválido. Confira o @ e o domínio' },
            ]}
          >
            <Input type="email" />
          </Form.Item>
          <Form.Item
            name="perfilId"
            label="Perfil"
            rules={[{ required: true, message: 'Escolha o perfil' }]}
            extra="Acessos e jornada vêm do perfil (Configurações, Perfis e horários)."
          >
            <Select options={opcoesPerfil} />
          </Form.Item>
          <Form.Item name="ativo" label="Ativo" valuePropName="checked" extra="Inativo não entra no sistema.">
            <Switch />
          </Form.Item>

          <h3 className="grupo-formulario">Agenda</h3>
          <Form.Item name="cor" label="Cor na agenda" getValueFromEvent={(cor) => cor.toHexString()}>
            <ColorPicker disabledAlpha presets={[{ label: 'Sugestões', colors: coresAgenda }]} />
          </Form.Item>
        </>
      }
    />
  )
}
