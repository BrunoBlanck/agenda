import { useState } from 'react'
import { App, Button, Form, Popconfirm, Skeleton } from 'antd'
import { DisconnectOutlined, ReloadOutlined, UserDeleteOutlined } from '@ant-design/icons'
import { useContaSiteCliente } from '../data/useContaSiteCliente.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { dataBR, horaCurta, soDigitos } from '../utils/formatos.js'
import EstadoVazio from './base/EstadoVazio.jsx'
import CodigoConfirmacao from './CodigoConfirmacao.jsx'
import './acesso-site.css'

const dataHoraCurta = (d) => (d ? `${dataBR(d)} às ${horaCurta(d.format('HH:mm'))}` : '—')

// Seção "Acesso ao site" na ficha do cliente (só com escrita em Clientes): conta criada pelo telefone,
// código pendente para a recepção repassar e remoção do acesso. Fica dentro do formulário do cliente,
// mas não tem campos: nada aqui conta como alteração não salva.
// telefoneSalvo: o acesso é sempre do telefone gravado; se a pessoa mudar o campo, a seção avisa.
export default function AcessoSiteCliente({ clienteId, telefoneSalvo }) {
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const acesso = useContaSiteCliente(clienteId)
  const { conta } = acesso
  const [removendo, setRemovendo] = useState(false)

  const remover = async () => {
    setRemovendo(true)
    try {
      await acesso.removerAcesso()
      message.success('Acesso ao site removido.')
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado: acesso.recarregar })
    } finally {
      setRemovendo(false)
    }
  }

  let conteudo
  if (acesso.erro && !conta) {
    conteudo = (
      <EstadoVazio
        compacto
        icone={<DisconnectOutlined />}
        titulo="Não foi possível ver o acesso ao site"
        descricao={acesso.erro.mensagem}
        acao={<Button onClick={acesso.recarregar}>Tentar de novo</Button>}
      />
    )
  } else if (!conta) {
    conteudo = (
      <div className="acesso-site-carregando">
        <Skeleton active title={false} paragraph={{ rows: 2, width: ['70%', '40%'] }} />
      </div>
    )
  } else {
    const pendente = conta.codigoPendente
    conteudo = (
      <>
        <p className="acesso-site-situacao">
          {/* Cada parte quebra inteira: a data nunca fica partida entre duas linhas */}
          {conta.possuiConta ? (
            <>
              <span className="sem-quebra">Conta criada em {dataBR(conta.criadaEm)}</span> ·{' '}
              <span className="sem-quebra">último acesso {dataHoraCurta(conta.ultimoAcessoEm)}</span>
            </>
          ) : (
            'Sem conta no site'
          )}
        </p>

        {pendente && (
          <div className="acesso-site-codigo">
            <div className="acesso-site-codigo-linha">
              <CodigoConfirmacao codigo={pendente.codigo} destaque />
              <span className="acesso-site-validade">vale até {horaCurta(pendente.expiraEm?.format('HH:mm'))}</span>
            </div>
            <p className="texto-apoio">Passe este código ao cliente para ele confirmar o telefone no site.</p>
          </div>
        )}

        {/* O formulário pode estar com outro telefone ainda não salvo */}
        <Form.Item noStyle shouldUpdate={(antes, depois) => antes.telefone !== depois.telefone}>
          {({ getFieldValue }) =>
            soDigitos(getFieldValue('telefone')) !== soDigitos(telefoneSalvo) && (
              <p className="acesso-site-aviso texto-apoio">
                Mostrando o acesso do telefone salvo. Salve o cliente para ver o do número novo.
              </p>
            )
          }
        </Form.Item>

        {conta.possuiConta && (
          <Popconfirm
            title="Remover acesso ao site?"
            description="O cliente sai de todos os aparelhos e precisará criar a senha de novo."
            okText="Remover acesso"
            okButtonProps={{ danger: true }}
            cancelText="Cancelar"
            onConfirm={remover}
          >
            <Button danger icon={<UserDeleteOutlined />} loading={removendo} className="acesso-site-remover">
              Remover acesso ao site
            </Button>
          </Popconfirm>
        )}
      </>
    )
  }

  return (
    <>
      {/* Título do grupo com a ação ao lado: o botão fica fora do h3 para não entrar no nome do título */}
      <div className="grupo-formulario grupo-com-acao">
        <h3>Acesso ao site</h3>
        <Button
          type="text"
          size="small"
          icon={<ReloadOutlined />}
          loading={!!acesso.atualizando}
          disabled={acesso.carregando || removendo}
          onClick={acesso.recarregar}
        >
          Atualizar
        </Button>
      </div>
      <div className="acesso-site">{conteudo}</div>
    </>
  )
}
