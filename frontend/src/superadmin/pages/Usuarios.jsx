import { Form, Input, Switch } from 'antd'
import CadastroTabela from '../../components/CadastroTabela.jsx'
import { EtiquetaSituacao } from '../../components/Etiquetas.jsx'
import { useData } from '../../data/DataContext.jsx'
import { dataHoraBR } from '../../utils/formatos.js'

// superadmin_usuarios: só as contas de quem administra a plataforma.
// Funcionários das lojas são cadastrados na própria loja.
export default function Usuarios() {
  const { superadmins } = useData()

  const colunas = [
    { title: 'Nome', dataIndex: 'nome', render: (n) => <strong>{n}</strong> },
    { title: 'E-mail', dataIndex: 'email' },
    { title: 'Último acesso', dataIndex: 'ultimoLoginEm', render: (d) => (d ? dataHoraBR(d) : <span className="texto-apoio">Nunca entrou</span>) },
    { title: 'Situação', dataIndex: 'ativo', render: (a) => <EtiquetaSituacao ativo={a} /> },
  ]

  return (
    <CadastroTabela
      titulo="Usuários admin"
      descricao="Contas com acesso ao SUPERADMIN. Os funcionários das lojas são cadastrados dentro de cada loja."
      item="usuário admin"
      lista={superadmins}
      colunas={colunas}
      permitirExcluir={false}
      valoresNovo={{ ativo: true }}
      validar={(v, item) =>
        !v.ativo && item.id && superadmins.itens.filter((s) => s.ativo && s.id !== item.id).length === 0
          ? 'A plataforma precisa de pelo menos um usuário admin ativo.'
          : undefined
      }
      campos={
        <>
          <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="email"
            label="E-mail"
            rules={[
              { required: true, message: 'Informe o e-mail' },
              { type: 'email', message: 'E-mail inválido' },
            ]}
            extra="Recebe um e-mail para definir a senha."
          >
            <Input type="email" />
          </Form.Item>
          <Form.Item name="ativo" label="Ativo" valuePropName="checked">
            <Switch />
          </Form.Item>
        </>
      }
    />
  )
}
