import { useState } from 'react'
import { App, Button, ColorPicker, Form, Input, Skeleton } from 'antd'
import { DisconnectOutlined, ExportOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useTratarErro } from '../data/api/useTratarErro.js'
import { tiposLoja } from '../data/dominio.js'
import { caminhoSite } from '../layout/caminhos.js'
import { CONTRASTE_MINIMO, contrasteComBranco, contrasteTexto, lerHex } from '../utils/cores.js'
import EstadoVazio from './base/EstadoVazio.jsx'
import UltimaAlteracao from './UltimaAlteracao.jsx'
import './cores-site.css'

// Exemplo de serviço da miniatura, como o site mostra no passo "Horário"
const EXEMPLO = {
  clinica: { servico: 'Limpeza', duracao: 60, frase: 'Agende sua consulta online, em poucos passos.' },
  barbearia: { servico: 'Corte de cabelo', duracao: 30, frase: 'Marque seu horário online, em poucos passos.' },
  escola: { servico: 'Aula experimental', duracao: 50, frase: 'Agende sua aula online, em poucos passos.' },
}

const CAMPOS = [
  { nome: 'corTopo', rotulo: 'Cor do topo', ajuda: 'Fundo do cabeçalho, atrás do nome da loja.' },
  { nome: 'corDestaque', rotulo: 'Cor de destaque', ajuda: 'Botões, dia e horário escolhidos, links e passos.' },
]

const formatoValido = (_, texto) =>
  !texto?.trim() || lerHex(texto) ? Promise.resolve() : Promise.reject(new Error('Informe a cor no formato #RRGGBB.'))

// Só avisa: a API decide (GER-02), então o botão de salvar continua valendo
const contrasteSuficiente = (_, texto) => {
  const razao = contrasteComBranco(texto)
  if (razao === null || razao >= CONTRASTE_MINIMO) return Promise.resolve()
  return Promise.reject(
    new Error(`Cor muito clara: o texto branco fica difícil de ler (contraste ${contrasteTexto(razao)}, mínimo 4,5:1). Escolha uma cor mais escura.`),
  )
}

/**
 * Cores do site do consumidor (SIT-13, SIT-14): painel da loja (Configurações) e SUPERADMIN (aba Site).
 * estado: o retorno de useCoresSite() ou useCoresSiteLoja(lojaId) ({ cores, carregando, erro, recarregar, salvar }).
 * As cores escolhidas aparecem só dentro da miniatura do site; o resto segue a identidade do painel (DIR-002).
 */
export default function CoresSite({ estado, nomeLoja, slug, somenteLeitura = false, aoNaoEncontrado }) {
  const { cores, carregando, erro, recarregar, salvar } = estado

  if (carregando) return <CoresSiteCarregando />
  if (!cores) {
    return (
      <EstadoVazio
        compacto
        icone={<DisconnectOutlined />}
        titulo="Não foi possível carregar as cores do site"
        descricao={erro?.mensagem}
        acao={<Button onClick={recarregar}>Tentar de novo</Button>}
      />
    )
  }

  return (
    <FormularioCores
      cores={cores}
      nomeLoja={nomeLoja}
      slug={slug}
      somenteLeitura={somenteLeitura}
      salvar={salvar}
      aoNaoEncontrado={aoNaoEncontrado}
    />
  )
}

function FormularioCores({ cores, nomeLoja, slug, somenteLeitura, salvar, aoNaoEncontrado }) {
  const { message } = App.useApp()
  const tratarErro = useTratarErro()
  const [form] = Form.useForm()
  const [salvando, setSalvando] = useState(false)
  const iniciais = { corTopo: cores.corTopo ?? '', corDestaque: cores.corDestaque ?? '' }
  const digitado = {
    corTopo: Form.useWatch('corTopo', form) ?? iniciais.corTopo,
    corDestaque: Form.useWatch('corDestaque', form) ?? iniciais.corDestaque,
  }
  const nomeTipo = tiposLoja[cores.tipo]?.nome ?? 'o tipo da loja'
  const bloqueado = somenteLeitura || salvando

  const enviar = async (valores) => {
    setSalvando(true)
    try {
      const paraApi = (texto) => (texto?.trim() ? (lerHex(texto) ?? texto.trim()) : null)
      const salvas = await salvar({ corTopo: paraApi(valores.corTopo), corDestaque: paraApi(valores.corDestaque) })
      form.setFieldsValue({ corTopo: salvas.corTopo ?? '', corDestaque: salvas.corDestaque ?? '' })
      message.success('Cores do site salvas.')
    } catch (e) {
      tratarErro(e, { form, aoNaoEncontrado })
      // A recusa da API (ex.: contraste) substitui o aviso da tela no mesmo campo, sem repetir a frase
      const recusados = form.getFieldsError().filter((f) => f.errors.length)
      if (recusados.length) form.setFields(recusados.map((f) => ({ name: f.name, warnings: [] })))
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Form className="cores-site-area" form={form} name="coresSite" layout="vertical" initialValues={iniciais} disabled={bloqueado} onFinish={enviar}>
      <div className="cores-site">
        <div className="cores-site-campos">
          <p className="texto-ajuda">Campo em branco usa a cor padrão de {nomeTipo}.</p>
          {CAMPOS.map((c) => (
            <Form.Item
              key={c.nome}
              name={c.nome}
              label={c.rotulo}
              extra={c.ajuda}
              validateTrigger={['onChange', 'onBlur']}
              rules={[
                { validator: formatoValido, validateTrigger: 'onBlur' },
                { validator: contrasteSuficiente, warningOnly: true },
              ]}
            >
              <CampoCor rotulo={c.rotulo} padrao={cores.padrao[c.nome]} nomeTipo={nomeTipo} bloqueado={bloqueado} somenteLeitura={somenteLeitura} />
            </Form.Item>
          ))}
        </div>

        <div className="cores-site-previa">
          <div className="cores-site-previa-cabecalho">
            <h3 className="grupo-formulario">Pré-visualização</h3>
            {slug && (
              <a href={caminhoSite(slug)} target="_blank" rel="noopener">
                Ver site <ExportOutlined aria-hidden="true" />
                <span className="sr-only"> (abre em outra aba)</span>
              </a>
            )}
          </div>
          <PreviaSite
            nomeLoja={nomeLoja}
            tipo={cores.tipo}
            corTopo={lerHex(digitado.corTopo) ?? cores.padrao.corTopo}
            corDestaque={lerHex(digitado.corDestaque) ?? cores.padrao.corDestaque}
          />
        </div>
      </div>

      <div className="rodape-formulario">
        <UltimaAlteracao item={cores} />
        {!somenteLeitura && (
          <Button type="primary" htmlType="submit" loading={salvando} disabled={false}>
            Salvar cores
          </Button>
        )}
      </div>
    </Form>
  )
}

// Amostra (abre o seletor) + código hex, sincronizados. value '' = cor padrão do tipo.
function CampoCor({ id, value = '', onChange, onBlur, rotulo, padrao, nomeTipo, bloqueado, somenteLeitura }) {
  const vazio = !value.trim()
  const amostra = lerHex(value) ?? padrao

  return (
    <div className="campo-cor">
      <ColorPicker
        value={amostra}
        format="hex"
        disabledAlpha
        disabledFormat
        disabled={bloqueado}
        onChange={(cor) => onChange?.(cor.toHexString())}
      >
        <button
          type="button"
          className={vazio ? 'campo-cor-amostra padrao' : 'campo-cor-amostra'}
          style={{ '--amostra': amostra }}
          disabled={bloqueado}
          aria-label={`${rotulo}: escolher na paleta`}
        />
      </ColorPicker>
      <Input
        id={id}
        className="campo-cor-hex"
        value={value}
        placeholder={padrao}
        maxLength={7}
        spellCheck={false}
        autoComplete="off"
        onChange={(e) => onChange?.(e.target.value.trim())}
        onBlur={() => {
          // Ao sair do campo, completa o "#" e passa para minúsculas; depois o Form valida o formato
          const hex = lerHex(value)
          if (hex && hex !== value) onChange?.(hex)
          onBlur?.()
        }}
      />
      {vazio ? (
        <span className="texto-apoio">Padrão de {nomeTipo}</span>
      ) : (
        !somenteLeitura && (
          <Button type="link" size="small" className="campo-cor-padrao" onClick={() => onChange?.('')}>
            Voltar ao padrão
          </Button>
        )
      )}
    </div>
  )
}

// Miniatura estática do passo "Horário" do site (backend/app/templates/site/horarios.html)
function PreviaSite({ nomeLoja, tipo, corTopo, corDestaque }) {
  const exemplo = EXEMPLO[tipo] ?? EXEMPLO.clinica
  const hoje = dayjs()
  const dias = [0, 1, 2].map((n) => {
    const dia = hoje.add(n, 'day')
    const semana = dia.format('ddd').replace('.', '')
    return { chave: n, semana: n === 0 ? 'Hoje' : semana[0].toUpperCase() + semana.slice(1), data: dia.format('DD/MM') }
  })

  return (
    <div
      className="previa-site"
      style={{ '--previa-topo': corTopo, '--previa-destaque': corDestaque }}
      role="img"
      aria-label="Miniatura do site de agendamento com as cores escolhidas"
    >
      <div className="previa-site-topo">
        <strong className="previa-site-nome">{nomeLoja || 'Nome da loja'}</strong>
        <span className="previa-site-frase">{exemplo.frase}</span>
      </div>
      <div className="previa-site-cartao">
        <ol className="previa-site-passos">
          <li className="feito">
            <span>1</span>Serviço
          </li>
          <li className="atual">
            <span>2</span>Horário
          </li>
          <li>
            <span>3</span>Seus dados
          </li>
        </ol>
        <p className="previa-site-titulo">
          {exemplo.servico} · {exemplo.duracao} min
        </p>
        <div className="previa-site-dias">
          {dias.map((d) => (
            <span key={d.chave} className={d.chave === 1 ? 'previa-site-dia atual' : 'previa-site-dia'}>
              <small>{d.semana}</small>
              <strong>{d.data}</strong>
            </span>
          ))}
        </div>
        <div className="previa-site-horarios">
          <span className="previa-site-horario">08:30</span>
          <span className="previa-site-horario atual">09:00</span>
          <span className="previa-site-horario">10:30</span>
        </div>
        <span className="previa-site-botao">Pedir agendamento</span>
      </div>
    </div>
  )
}

function CoresSiteCarregando() {
  return (
    <div className="cores-site-area" aria-busy="true" aria-label="Carregando as cores do site">
      <div className="cores-site">
        <div className="cores-site-campos">
          {CAMPOS.map((c) => (
            <div key={c.nome} className="cores-site-fantasma-campo">
              <Skeleton.Input active size="small" />
              <div className="campo-cor">
                <Skeleton.Button active shape="square" />
                <Skeleton.Input active />
              </div>
            </div>
          ))}
        </div>
        <Skeleton.Node active className="cores-site-fantasma-previa">
          <span />
        </Skeleton.Node>
      </div>
    </div>
  )
}
