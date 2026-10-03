import { useState } from 'react'
import { App, Button, Descriptions, Flex, Form } from 'antd'
import { DisconnectOutlined, EyeOutlined } from '@ant-design/icons'
import { useAcesso } from '../data/useAcesso.js'
import { useConfigLoja } from '../data/useConfigLoja.js'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { modulos } from '../data/acesso.js'
import { tiposLoja } from '../data/dominio.js'
import Pagina from '../components/base/Pagina.jsx'
import Secao from '../components/base/Secao.jsx'
import Etiqueta from '../components/base/Etiqueta.jsx'
import EstadoVazio from '../components/base/EstadoVazio.jsx'
import CarregandoPagina from '../components/base/CarregandoPagina.jsx'
import { EtiquetaLoja } from '../components/Etiquetas.jsx'
import { CamposEmpresa, CamposEndereco } from '../components/CamposLoja.jsx'
import UltimaAlteracao from '../components/UltimaAlteracao.jsx'
import EnvioLogo from '../components/EnvioLogo.jsx'

const titulo = 'Dados da loja'
const descricao = 'Aparecem no site de agendamento e nos avisos enviados aos clientes.'

// Configurações > Dados da loja (estrutura.md, 2.18)
export default function ConfigLoja() {
  const { pode } = useAcesso()
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const [form] = Form.useForm()
  const config = useConfigLoja()
  const [salvando, setSalvando] = useState(false)
  const [gravacoes, setGravacoes] = useState(0)
  const somenteLeitura = !pode('config_loja', 'escrita')
  const dados = config.dados

  const salvar = async (valores) => {
    setSalvando(true)
    try {
      await config.salvar(valores)
      setGravacoes((n) => n + 1)
      message.success('Dados da loja salvos.')
    } catch (e) {
      tratarErro(e, { form })
    } finally {
      setSalvando(false)
    }
  }

  if (config.carregando) return <CarregandoPagina />

  if (!dados) {
    return (
      <Pagina titulo={titulo} descricao={descricao}>
        <Secao>
          <EstadoVazio
            icone={<DisconnectOutlined />}
            titulo="Não foi possível carregar os dados da loja"
            descricao={config.erro?.mensagem}
            acao={<Button onClick={config.recarregar}>Tentar de novo</Button>}
          />
        </Secao>
      </Pagina>
    )
  }

  const opcionais = modulos.filter((m) => m.opcional)

  return (
    <Pagina
      titulo={titulo}
      descricao={descricao}
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
          <Form
            // Depois de salvar, o formulário volta a mostrar o que ficou gravado (CNPJ e CEP formatados pela API).
            // Enviar ou remover a logo não recria o formulário (não perde o que está sendo digitado).
            key={gravacoes}
            form={form}
            layout="vertical"
            initialValues={dados}
            disabled={somenteLeitura || salvando}
            onFinish={salvar}
          >
            <CamposEmpresa />
            <h3 className="grupo-formulario">Endereço</h3>
            <CamposEndereco somenteLeitura={somenteLeitura} />
            <div className="rodape-formulario">
              <UltimaAlteracao item={dados} />
              {!somenteLeitura && (
                <Button type="primary" htmlType="submit" loading={salvando}>
                  Salvar dados
                </Button>
              )}
            </div>
          </Form>
        </Secao>

        <div className="pilha">
          <Secao titulo="Logo" descricao="Aparece no menu e no site da loja.">
            <EnvioLogo
              logoUrl={dados.logoUrl}
              nome={dados.nomeFantasia}
              podeAlterar={!somenteLeitura}
              enviar={config.enviarLogo}
              remover={config.removerLogo}
            />
          </Secao>

          <Secao titulo="Definido pela plataforma" descricao="Para alterar, fale com o suporte.">
            <Descriptions column={1} size="small" colon={false}>
              <Descriptions.Item label="Tipo">{tiposLoja[dados.tipo]?.nome ?? dados.tipo ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="Endereço do site">/{dados.slug}</Descriptions.Item>
              <Descriptions.Item label="Plano">{dados.planoNome ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="Situação">
                <EtiquetaLoja status={dados.status} />
              </Descriptions.Item>
              <Descriptions.Item label="Fuso horário">{dados.fusoHorario ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="Módulos">
                <Flex gap={4} wrap>
                  {opcionais.map((m) => {
                    const ativo = !!dados.modulos[m.codigo]
                    return (
                      <Etiqueta key={m.codigo} tom={ativo ? 'sucesso' : 'neutro'}>
                        {m.nome}: {ativo ? 'ativo' : 'desligado'}
                      </Etiqueta>
                    )
                  })}
                </Flex>
              </Descriptions.Item>
            </Descriptions>
          </Secao>
        </div>
      </div>
    </Pagina>
  )
}
