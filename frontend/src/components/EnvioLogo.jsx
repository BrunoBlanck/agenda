import { useRef, useState } from 'react'
import { Alert, App, Avatar, Button, Flex, Popconfirm } from 'antd'
import { DeleteOutlined, ShopOutlined, UploadOutlined } from '@ant-design/icons'
import { useTratarErro } from '../data/api/useTratarErro.js'

// Mesmos limites da API (backend/README.md, "Logo da loja"). Aqui é só para avisar antes de enviar:
// quem decide é a API, que confere o formato pelos bytes do arquivo.
const TIPOS_ACEITOS = ['image/png', 'image/jpeg', 'image/webp']
const TAMANHO_MAXIMO = 2 * 1024 * 1024
const MSG_FORMATO = 'Formato não aceito. Envie uma imagem PNG, JPEG ou WebP.'
const MSG_TAMANHO = 'A imagem deve ter no máximo 2 MB.'

function problemaNoArquivo(arquivo) {
  // Sem tipo informado pelo navegador (extensão desconhecida): a API decide
  if (arquivo.type && !TIPOS_ACEITOS.includes(arquivo.type)) return MSG_FORMATO
  if (arquivo.size > TAMANHO_MAXIMO) return MSG_TAMANHO
  return null
}

/**
 * Logo da loja com prévia, envio, troca e remoção (painel da loja e SUPERADMIN).
 * logoUrl: endereço já utilizável (urlDaApi) ou null. podeAlterar = false mostra só a prévia.
 * enviar(arquivo: File) => Promise e remover() => Promise vêm do hook da tela.
 * aoNaoEncontrado: 404 (loja excluída, no SUPERADMIN).
 */
export default function EnvioLogo({ logoUrl, nome, podeAlterar, enviar, remover, aoNaoEncontrado }) {
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const entrada = useRef(null)
  const [enviando, setEnviando] = useState(false)
  const [removendo, setRemovendo] = useState(false)
  const [aviso, setAviso] = useState(null)
  const ocupado = enviando || removendo

  const escolher = async (evento) => {
    const arquivo = evento.target.files?.[0]
    evento.target.value = '' // permite escolher o mesmo arquivo de novo depois de um erro
    if (!arquivo) return
    const problema = problemaNoArquivo(arquivo)
    setAviso(problema)
    if (problema) return

    setEnviando(true)
    try {
      await enviar(arquivo)
      message.success(logoUrl ? 'Logo trocada.' : 'Logo enviada.')
    } catch (e) {
      // 413 (tamanho) e 422 (formato, arquivo faltando): a mensagem do servidor fica ao lado da logo
      if (e?.status === 413 || e?.status === 422) {
        setAviso(e.campos?.length ? e.campos.map((c) => c.mensagem).join(' ') : e.mensagem)
      } else {
        tratarErro(e, { aoNaoEncontrado })
      }
    } finally {
      setEnviando(false)
    }
  }

  const tirar = async () => {
    setAviso(null)
    setRemovendo(true)
    try {
      await remover()
      message.success('Logo removida.')
    } catch (e) {
      tratarErro(e, { aoNaoEncontrado })
    } finally {
      setRemovendo(false)
    }
  }

  return (
    <Flex vertical gap={12}>
      <Flex align="center" gap={16} wrap>
        <Avatar
          shape="square"
          size={96}
          src={logoUrl || undefined}
          alt={nome ? `Logo de ${nome}` : 'Logo da loja'}
          icon={<ShopOutlined />}
          className="logo-loja"
        />
        {podeAlterar && (
          <Flex vertical gap={8} align="flex-start">
            <input
              ref={entrada}
              type="file"
              accept={TIPOS_ACEITOS.join(',')}
              hidden
              onChange={escolher}
              aria-label="Escolher imagem da logo"
            />
            <Flex gap={8} wrap>
              <Button icon={<UploadOutlined />} loading={enviando} disabled={removendo} onClick={() => entrada.current?.click()}>
                {logoUrl ? 'Trocar logo' : 'Enviar logo'}
              </Button>
              {logoUrl && (
                <Popconfirm
                  title="Remover a logo?"
                  description="O menu e o site passam a mostrar só o nome da loja."
                  okText="Remover"
                  okButtonProps={{ danger: true }}
                  cancelText="Cancelar"
                  onConfirm={tirar}
                  disabled={ocupado}
                >
                  <Button danger icon={<DeleteOutlined />} loading={removendo} disabled={enviando}>
                    Remover logo
                  </Button>
                </Popconfirm>
              )}
            </Flex>
            <span className="texto-apoio">PNG, JPEG ou WebP, até 2 MB.</span>
          </Flex>
        )}
      </Flex>
      {aviso && <Alert type="error" showIcon title={aviso} closable={{ onClose: () => setAviso(null) }} />}
    </Flex>
  )
}
