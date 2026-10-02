import { Drawer, Alert, Select, Switch, Flex, Typography, Divider, Button } from 'antd'
import { CrownOutlined } from '@ant-design/icons'
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
    <Drawer title="Demonstração" open={open} onClose={onClose}>
      <Alert
        type="info"
        showIcon
        title="Painel provisório"
        description="No sistema real o usuário vem do login, e os módulos e o tipo da loja são definidos no painel SUPERADMIN."
        style={{ marginBottom: 24 }}
      />

      <Typography.Title level={5}>Entrar como</Typography.Title>
      <Select
        style={{ width: '100%' }}
        value={sessao.usuarioId}
        onChange={sessao.entrarComo}
        options={funcionarios.itens
          .filter((f) => f.ativo)
          .map((f) => ({ value: f.id, label: `${f.nome} (${nomePerfil(f.perfilId)})` }))}
      />

      <Divider />

      <Typography.Title level={5}>Módulos da loja</Typography.Title>
      <Typography.Paragraph type="secondary">Ativados ou desativados pelo superadmin, um a um.</Typography.Paragraph>
      <Flex vertical gap={12}>
        {modulos
          .filter((m) => m.opcional)
          .map((m) => (
            <Flex key={m.codigo} justify="space-between" align="center">
              <span>{m.nome}</span>
              <Switch checked={!!ativos.ativos[m.codigo]} onChange={(v) => ativos.definir(m.codigo, v)} />
            </Flex>
          ))}
      </Flex>

      <Divider />

      <Typography.Title level={5}>Tipo da loja</Typography.Title>
      <Typography.Paragraph type="secondary">
        Não muda nada no painel da loja. Define qual site do consumidor final a loja usa.
      </Typography.Paragraph>
      <Select
        style={{ width: '100%' }}
        value={loja.dados.tipo}
        onChange={(tipo) => loja.atualizar({ tipo }, null)}
        options={opcoesTipoLoja}
      />

      <Divider />

      <Button
        block
        type="primary"
        icon={<CrownOutlined />}
        onClick={() => {
          onClose()
          navigate('/superadmin')
        }}
      >
        Abrir prévia do painel SUPERADMIN
      </Button>
    </Drawer>
  )
}
