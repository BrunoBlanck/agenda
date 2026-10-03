import { Form, Input, Switch } from 'antd'
import CadastroTabela from '../../components/CadastroTabela.jsx'
import Etiqueta from '../../components/base/Etiqueta.jsx'
import { EtiquetaSituacao } from '../../components/Etiquetas.jsx'
import { dataHoraBR } from '../../utils/formatos.js'
import { useUsuarios } from '../usePlataforma.js'
import SenhaProvisoria from '../SenhaProvisoria.jsx'

// superadmin_usuarios: só as contas de quem administra a plataforma.
// Funcionários das lojas são cadastrados na própria loja.
// Regras da API (409): ninguém se exclui nem se desativa, e sempre fica um usuário admin ativo.
export default function Usuarios() {
  const usuarios = useUsuarios()

  const colunas = [
    {
      title: 'Nome',
      dataIndex: 'nome',
      render: (n, u) => (
        <span className="com-ponto">
          <strong>{n}</strong>
          {u.voce && <Etiqueta tom="contorno">Você</Etiqueta>}
        </span>
      ),
    },
    { title: 'E-mail', dataIndex: 'email' },
    { title: 'Último acesso', dataIndex: 'ultimoLoginEm', render: (d) => (d ? dataHoraBR(d) : <span className="texto-apoio">Nunca entrou</span>) },
    { title: 'Situação', dataIndex: 'ativo', render: (a) => <EtiquetaSituacao ativo={a} /> },
  ]

  return (
    <CadastroTabela
      titulo="Usuários admin"
      descricao="Contas com acesso ao SUPERADMIN. Os funcionários das lojas são cadastrados dentro de cada loja."
      item="usuário admin"
      lista={usuarios}
      colunas={colunas}
      valoresNovo={{ ativo: true }}
      textoExcluir="A conta perde o acesso ao SUPERADMIN. O que ela fez continua na auditoria."
      antes={usuarios.senhaGerada && <SenhaProvisoria {...usuarios.senhaGerada} aoFechar={usuarios.esquecerSenha} />}
      campos={
        <>
          <Form.Item name="nome" label="Nome" rules={[{ required: true, whitespace: true, message: 'Informe o nome' }]}>
            <Input maxLength={150} />
          </Form.Item>
          <Form.Item
            name="email"
            label="E-mail (login)"
            rules={[
              { required: true, message: 'Informe o e-mail' },
              { type: 'email', message: 'E-mail inválido' },
            ]}
          >
            <Input type="email" />
          </Form.Item>
          <Form.Item noStyle dependencies={['id']}>
            {(form) => (
              <Form.Item
                name="senha"
                label={form.getFieldValue('id') ? 'Nova senha' : 'Senha'}
                rules={[{ min: 8, message: 'Use pelo menos 8 caracteres' }]}
                extra={
                  form.getFieldValue('id')
                    ? 'Preencha só para trocar a senha.'
                    : 'Em branco, o sistema gera uma senha provisória, mostrada uma única vez depois de salvar.'
                }
              >
                <Input.Password autoComplete="new-password" maxLength={200} />
              </Form.Item>
            )}
          </Form.Item>
          <Form.Item name="ativo" label="Ativo" valuePropName="checked">
            <Switch />
          </Form.Item>
        </>
      }
    />
  )
}
