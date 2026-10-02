import { ColorPicker, Flex, Form, Input, Select, Switch, Tag } from 'antd'
import CadastroTabela from '../components/CadastroTabela.jsx'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'

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
      return 'A loja precisa de pelo menos um Administrador ativo.'
    }
  }

  const colunas = [
    {
      title: 'Nome',
      dataIndex: 'nome',
      sorter: (a, b) => a.nome.localeCompare(b.nome),
      render: (nome, f) => (
        <Flex align="center" gap={8}>
          <span className="agenda-cor" style={{ background: f.cor ?? '#64748b' }} />
          {nome}
        </Flex>
      ),
    },
    { title: 'Cargo', dataIndex: 'cargo', filters: cargos.map((c) => ({ text: c, value: c })), onFilter: (v, r) => r.cargo === v },
    {
      title: 'Perfil de acesso',
      dataIndex: 'perfilId',
      render: (id) => <Tag color={perfil(id)?.acessoTotal ? 'gold' : 'default'}>{perfil(id)?.nome ?? '—'}</Tag>,
    },
    { title: 'E-mail', dataIndex: 'email' },
    { title: 'Telefone', dataIndex: 'telefone' },
    {
      title: 'Situação',
      dataIndex: 'ativo',
      render: (ativo) => (ativo ? <Tag color="green">Ativo</Tag> : <Tag>Inativo</Tag>),
    },
  ]

  return (
    <CadastroTabela
      titulo="Funcionário"
      lista={funcionarios}
      colunas={colunas}
      somenteLeitura={!pode('funcionarios', 'escrita')}
      permitirExcluir={false}
      validar={validar}
      campos={
        <>
          <Form.Item name="nome" label="Nome" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="cargo" label="Cargo" rules={[{ required: true }]} extra="Informativo. Quem define o acesso é o perfil.">
            <Select options={cargos.map((c) => ({ value: c, label: c }))} />
          </Form.Item>
          <Form.Item name="perfilId" label="Perfil de acesso" rules={[{ required: true }]}>
            <Select options={opcoesPerfil} />
          </Form.Item>
          <Form.Item name="email" label="E-mail (login)" rules={[{ required: true }]}><Input type="email" /></Form.Item>
          <Form.Item name="telefone" label="Telefone"><Input /></Form.Item>
          <Form.Item name="cor" label="Cor na agenda" initialValue="#0f766e" getValueFromEvent={(cor) => cor.toHexString()}>
            <ColorPicker disabledAlpha presets={[{ label: 'Sugestões', colors: ['#0f766e', '#2563eb', '#d97706', '#9333ea', '#dc2626', '#0891b2', '#65a30d', '#db2777'] }]} />
          </Form.Item>
          <Form.Item name="ativo" label="Ativo" valuePropName="checked" initialValue={true}><Switch /></Form.Item>
        </>
      }
    />
  )
}
