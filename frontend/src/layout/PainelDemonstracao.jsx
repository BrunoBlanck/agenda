import { Drawer, Alert, Select, Switch, Flex, Button, Form } from 'antd'
import { ControlOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useData } from '../data/DataContext.jsx'
import { modulos } from '../data/acesso.js'
import { opcoesTipoLoja } from '../data/plataforma.js'

// Só existe enquanto não há login nem painel SUPERADMIN: permite simular quem está logado
// e o que o superadmin liberou para a loja.
export default function PainelDemonstracao({ open, onClose }) {
  const { funcionarios, perfis, sessao, modulos: ativos, loja } = useData()
  const navigate = useNavigate()
  const nomePerfil = (id) => perfis.itens.find((p) => p.id === id)?.nome ?? '—'

  return (
    <Drawer
      title="Demonstração"
      open={open}
      onClose={onClose}
      footer={
        <Button
          block
          icon={<ControlOutlined />}
          onClick={() => {
            onClose()
            navigate('/superadmin')
          }}
        >
          Abrir a prévia do SUPERADMIN
        </Button>
      }
    >
      <Alert
        type="info"
        showIcon
        title="Painel provisório"
        description="No sistema real o usuário vem do login, e os módulos e o tipo da loja são definidos no SUPERADMIN."
        className="alerta-formulario"
      />

      <Form layout="vertical">
        <Form.Item label="Entrar como" extra="Troque para ver o painel com os acessos de outro perfil.">
          <Select
            value={sessao.usuarioId}
            onChange={sessao.entrarComo}
            options={funcionarios.itens
              .filter((f) => f.ativo)
              .map((f) => ({ value: f.id, label: `${f.nome} (${nomePerfil(f.perfilId)})` }))}
          />
        </Form.Item>

        <Form.Item label="Módulos da loja" extra="Ligados ou desligados pelo superadmin, um a um.">
          <Flex vertical gap={12} className="lista-modulos">
            {modulos
              .filter((m) => m.opcional)
              .map((m) => (
                <Flex key={m.codigo} justify="space-between" align="center" component="label">
                  <span>{m.nome}</span>
                  <Switch checked={!!ativos.ativos[m.codigo]} onChange={(v) => ativos.definir(m.codigo, v)} />
                </Flex>
              ))}
          </Flex>
        </Form.Item>

        <Form.Item label="Tipo da loja" extra="Não muda o painel. Define qual site do consumidor a loja usa.">
          <Select value={loja.dados.tipo} onChange={(tipo) => loja.atualizar({ tipo }, null)} options={opcoesTipoLoja} />
        </Form.Item>
      </Form>
    </Drawer>
  )
}
