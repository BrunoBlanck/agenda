import { useState } from 'react'
import { App, Avatar, Button, Descriptions, Flex, Form, Upload } from 'antd'
import { DeleteOutlined, EyeOutlined, ShopOutlined, UploadOutlined } from '@ant-design/icons'
import { useData } from '../data/DataContext.jsx'
import { useAcesso } from '../data/useAcesso.js'
import { modulos } from '../data/acesso.js'
import { tiposLoja } from '../data/plataforma.js'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import { EtiquetaLoja } from '../components/Etiquetas.jsx'
import { CamposEmpresa, CamposEndereco } from '../components/CamposLoja.jsx'
import UltimaAlteracao from '../components/UltimaAlteracao.jsx'

const TIPOS_LOGO = ['image/png', 'image/jpeg', 'image/svg+xml']
const LOGO_MAX_MB = 2

// Configurações > Dados da loja (estrutura.md, 2.18)
export default function ConfigLoja() {
  const { loja, planos } = useData()
  const { pode, moduloAtivo } = useAcesso()
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [logo, setLogo] = useState(loja.dados.logoUrl)
  const somenteLeitura = !pode('config_loja', 'escrita')
  const dados = loja.dados

  const escolherLogo = (arquivo) => {
    if (!TIPOS_LOGO.includes(arquivo.type)) {
      message.error('Envie uma imagem PNG, JPG ou SVG.')
    } else if (arquivo.size > LOGO_MAX_MB * 1024 * 1024) {
      message.error(`A imagem tem mais de ${LOGO_MAX_MB} MB. Envie uma menor.`)
    } else {
      // No sistema real o arquivo vai para o storage e aqui fica só o caminho
      const leitor = new FileReader()
      leitor.onload = () => setLogo(leitor.result)
      leitor.readAsDataURL(arquivo)
    }
    return Upload.LIST_IGNORE
  }

  const salvar = (valores) => {
    loja.atualizar({ ...valores, logoUrl: logo })
    message.success('Dados da loja salvos.')
  }

  return (
    <Pagina
      titulo="Dados da loja"
      descricao="Aparecem no site de agendamento e nos avisos enviados aos clientes."
      acoes={
        somenteLeitura && (
          <Etiqueta icone={<EyeOutlined />} title="Seu perfil permite consultar, mas não alterar">
            Somente leitura
          </Etiqueta>
        )
      }
    >
      <div className="grade-principal">
        <Secao titulo="Identificação e contato">
          <Form form={form} layout="vertical" initialValues={dados} disabled={somenteLeitura} onFinish={salvar}>
            <CamposEmpresa />
            <h3 className="grupo-formulario">Endereço</h3>
            <CamposEndereco />
            <div className="rodape-formulario">
              <UltimaAlteracao item={dados} />
              {!somenteLeitura && (
                <Button type="primary" htmlType="submit">
                  Salvar dados
                </Button>
              )}
            </div>
          </Form>
        </Secao>

        <div className="pilha">
          <Secao titulo="Logo" descricao={`PNG, JPG ou SVG, até ${LOGO_MAX_MB} MB. Aparece no menu e no site da loja.`}>
            <Flex align="center" gap={16} wrap>
              <Avatar shape="square" size={96} src={logo} icon={!logo && <ShopOutlined />} className="logo-loja" />
              {!somenteLeitura && (
                <Flex gap={8} wrap>
                  <Upload accept={TIPOS_LOGO.join(',')} showUploadList={false} beforeUpload={escolherLogo}>
                    <Button icon={<UploadOutlined />}>{logo ? 'Trocar logo' : 'Enviar logo'}</Button>
                  </Upload>
                  {logo && <Button danger icon={<DeleteOutlined />} aria-label="Remover logo" onClick={() => setLogo(null)} />}
                </Flex>
              )}
            </Flex>
            {!somenteLeitura && logo !== dados.logoUrl && <p className="texto-apoio">Clique em Salvar dados para gravar a nova logo.</p>}
          </Secao>

          <Secao titulo="Definido pela plataforma" descricao="Para alterar, fale com o suporte.">
            <Descriptions column={1} size="small" colon={false}>
              <Descriptions.Item label="Tipo">{tiposLoja[dados.tipo]?.nome}</Descriptions.Item>
              <Descriptions.Item label="Endereço do site">/{dados.slug}</Descriptions.Item>
              <Descriptions.Item label="Plano">{planos.todos.find((p) => p.id === dados.planoId)?.nome}</Descriptions.Item>
              <Descriptions.Item label="Situação">
                <EtiquetaLoja status={dados.status} />
              </Descriptions.Item>
              <Descriptions.Item label="Fuso horário">{dados.fusoHorario}</Descriptions.Item>
              <Descriptions.Item label="Módulos">
                <Flex gap={4} wrap>
                  {modulos
                    .filter((m) => m.opcional)
                    .map((m) => (
                      <Etiqueta key={m.codigo} tom={moduloAtivo(m.codigo) ? 'sucesso' : 'neutro'}>
                        {m.nome}: {moduloAtivo(m.codigo) ? 'ativo' : 'desligado'}
                      </Etiqueta>
                    ))}
                </Flex>
              </Descriptions.Item>
            </Descriptions>
          </Secao>
        </div>
      </div>
    </Pagina>
  )
}
