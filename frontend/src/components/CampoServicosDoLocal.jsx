import { Alert, Button, Form, Select } from 'antd'
import { useOpcoesLocal } from '../data/useLocais.js'
import { listaEmTexto } from '../utils/formatos.js'

const ROTULO = 'Serviços que acontecem aqui'

const rotuloServico = (s) => (s.ativo === false ? `${s.nome} (inativo)` : s.nome)

// Opções do Select: as da API + as já vinculadas ao local que não vieram nelas (ex.: serviço excluído no
// meio do caminho), com o nome que veio no próprio local. Sem opções (só leitura), só as vinculadas.
function montarOpcoes(opcoes, vinculados) {
  const porId = new Map()
  for (const s of opcoes ?? []) porId.set(s.id, { value: s.id, label: rotuloServico(s) })
  for (const s of vinculados) if (!porId.has(s.id)) porId.set(s.id, { value: s.id, label: rotuloServico(s) })
  return [...porId.values()].sort((a, b) => a.label.localeCompare(b.label, 'pt-BR'))
}

const nomesEmDestaque = (nomes) => <strong>{listaEmTexto(nomes)}</strong>

// LOC-06: o vínculo restringe o serviço, não o local. Avisa o efeito antes de salvar (não bloqueia).
function AvisosVinculo({ restringe, liberta, singular }) {
  const local = singular.toLowerCase()
  return (
    <>
      {restringe.length > 0 && (
        <Alert
          type="warning"
          showIcon
          role="status"
          className="alerta-formulario"
          title={
            restringe.length === 1 ? (
              <>
                O serviço {nomesEmDestaque(restringe)} hoje aceita qualquer {local}. Ao salvar, passa a ser agendado só onde
                estiver vinculado.
              </>
            ) : (
              <>
                Os serviços {nomesEmDestaque(restringe)} hoje aceitam qualquer {local}. Ao salvar, passam a ser agendados só
                onde estiverem vinculados.
              </>
            )
          }
        />
      )}
      {liberta.length > 0 && (
        <Alert
          type="warning"
          showIcon
          role="status"
          className="alerta-formulario"
          title={
            liberta.length === 1 ? (
              <>
                O serviço {nomesEmDestaque(liberta)} só está vinculado aqui. Ao salvar, volta a aceitar qualquer {local}.
              </>
            ) : (
              <>
                Os serviços {nomesEmDestaque(liberta)} só estão vinculados aqui. Ao salvar, voltam a aceitar qualquer {local}.
              </>
            )
          }
        />
      )}
    </>
  )
}

// Campo "Serviços que acontecem aqui" do formulário de local (LOC-06). Só aparece com o módulo Serviços ligado.
// registro: o local aberto ({} = novo), com servicoIds e servicos ({id, nome, ativo}) já salvos.
// singular: como a loja chama um local ("Consultório", "Sala").
// O campo só entra nos valores enviados (servicoIds) quando as opções carregaram: carregando ou com erro,
// ele aparece travado com os vínculos atuais e o local é salvo sem mexer neles.
export default function CampoServicosDoLocal({ registro, somenteLeitura, singular }) {
  const opcoes = useOpcoesLocal({ ativo: !somenteLeitura })
  const vinculados = registro.servicos ?? []
  const salvosIds = registro.servicoIds ?? vinculados.map((s) => s.id)
  const marcadosIds = Form.useWatch('servicoIds') ?? salvosIds
  const ajuda = `Serviço sem vínculo pode ser agendado em qualquer ${singular.toLowerCase()}, inclusive aqui.`

  // Só leitura: mostra os vínculos atuais (o formulário inteiro já vem desabilitado)
  if (somenteLeitura) {
    return (
      <Form.Item name="servicoIds" label={ROTULO}>
        <Select mode="multiple" options={montarOpcoes(null, vinculados)} placeholder="Nenhum serviço vinculado" />
      </Form.Item>
    )
  }

  // Sem nome no Form.Item: o valor não vai para o envio (não apaga vínculos por falta de opções)
  if (opcoes.erro || opcoes.carregando) {
    return (
      <Form.Item
        label={ROTULO}
        extra={
          opcoes.erro ? (
            <span>
              Não foi possível carregar os serviços. Ao salvar, os vínculos atuais ficam como estão.{' '}
              <Button type="link" size="small" onClick={opcoes.recarregar}>
                Tentar de novo
              </Button>
            </span>
          ) : (
            ajuda
          )
        }
      >
        <Select
          mode="multiple"
          disabled
          loading={opcoes.carregando}
          aria-label={ROTULO}
          value={salvosIds}
          options={montarOpcoes(null, vinculados)}
          placeholder={opcoes.carregando ? 'Carregando serviços' : 'Nenhum serviço vinculado'}
        />
      </Form.Item>
    )
  }

  // null depois de carregar = módulo Serviços desligado no servidor
  if (opcoes.servicos === null) return null

  const porId = new Map(opcoes.servicos.map((s) => [s.id, s]))
  const salvos = new Set(salvosIds)
  const marcados = new Set(marcadosIds)
  const nomeDe = (id) => porId.get(id).nome
  // Marcado agora e hoje sem nenhum local: passa a ficar restrito aos locais vinculados
  const restringe = marcadosIds.filter((id) => !salvos.has(id) && porId.get(id)?.locaisVinculados === 0).map(nomeDe)
  // Desmarcado e este era o único local dele: volta a aceitar qualquer local
  const liberta = salvosIds.filter((id) => !marcados.has(id) && porId.get(id)?.locaisVinculados === 1).map(nomeDe)
  const semServicos = opcoes.servicos.length === 0

  return (
    <>
      <Form.Item name="servicoIds" label={ROTULO} extra={ajuda}>
        <Select
          mode="multiple"
          allowClear
          optionFilterProp="label"
          options={montarOpcoes(opcoes.servicos, vinculados)}
          placeholder={semServicos ? 'Nenhum serviço cadastrado' : 'Escolha os serviços'}
          notFoundContent={semServicos ? 'Nenhum serviço cadastrado' : 'Nenhum serviço com esse nome'}
        />
      </Form.Item>
      <AvisosVinculo restringe={restringe} liberta={liberta} singular={singular} />
    </>
  )
}
