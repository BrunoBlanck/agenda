import { useState } from 'react'
import { App, Button, Flex, Form } from 'antd'
import PainelLateral from './PainelLateral.jsx'

// O conteúdo do painel é recriado a cada abertura: ao montar, o foco vai para o primeiro campo
// (logo depois do foco automático do próprio Drawer, sem esperar a animação). Fora do componente
// para a referência ser estável e não rodar de novo a cada renderização.
const focarPrimeiroCampo = (el) => {
  if (!el) return
  const espera = setTimeout(() => el.querySelector('input:not([disabled]), textarea:not([disabled])')?.focus({ preventScroll: true }))
  return () => clearTimeout(espera)
}

// Formulário no painel lateral padrão: a tela continua visível atrás, com a origem destacada.
// Abre sempre com valoresIniciais (o formulário é recriado a cada abertura), Enter envia e
// onSalvar recebe os valores já validados.
// nome, icone, cor: o registro em edição no cabeçalho (sem nome = registro novo).
// extra(fechar): ações no cabeçalho; fechar(depois) respeita o aviso de alterações não salvas.
// children também pode ser uma função (fechar) => campos, para atalhos dentro do formulário.
// rodape: informação à esquerda do rodapé (ex.: última alteração). somenteLeitura: só o botão Fechar.
// Fechar (X, Esc, clique fora ou Cancelar) com alterações pendentes pede confirmação antes de descartar.
export default function PainelFormulario({
  titulo,
  nome,
  icone,
  cor,
  open,
  form,
  valoresIniciais,
  onCancelar,
  onSalvar,
  textoSalvar = 'Salvar',
  somenteLeitura = false,
  largura,
  rodape,
  extra,
  children,
  onValuesChange,
  ...propsForm
}) {
  const { modal } = App.useApp()
  const [alterado, setAlterado] = useState(false)
  // Cada abertura começa sem alterações (calculado na renderização, sem depender do fim da animação)
  const [abertoAntes, setAbertoAntes] = useState(open)
  if (open !== abertoAntes) {
    setAbertoAntes(open)
    if (open) setAlterado(false)
  }

  // depois: o que fazer em seguida (ex.: abrir outra tela), só se o painel de fato fechar
  const fechar = (depois) => {
    const sair = () => {
      onCancelar()
      if (typeof depois === 'function') depois()
    }
    if (!alterado) return sair()
    modal.confirm({
      title: 'Descartar alterações?',
      content: 'O que você mudou aqui ainda não foi salvo.',
      okText: 'Descartar',
      okButtonProps: { danger: true },
      cancelText: 'Continuar editando',
      focusable: { autoFocusButton: 'cancel' },
      onOk: sair,
    })
  }

  return (
    <PainelLateral
      titulo={titulo}
      nome={nome}
      semNome="Preencha os dados abaixo"
      icone={icone}
      cor={cor}
      open={open}
      onClose={() => fechar()}
      largura={largura}
      rootClassName="painel-formulario"
      extra={extra?.(fechar)}
      rodape={
        <Flex align="center" justify="space-between" gap={12} wrap>
          <div className="painel-formulario-info">
            {alterado ? (
              <span className="painel-formulario-pendente" role="status">
                Alterações não salvas
              </span>
            ) : (
              rodape
            )}
          </div>
          <Flex gap={8} className="painel-formulario-acoes">
            {somenteLeitura ? (
              <Button onClick={onCancelar}>Fechar</Button>
            ) : (
              <>
                <Button onClick={() => fechar()}>Cancelar</Button>
                <Button type="primary" onClick={() => form.submit()}>
                  {textoSalvar}
                </Button>
              </>
            )}
          </Flex>
        </Flex>
      }
    >
      <div ref={focarPrimeiroCampo}>
        <Form
          form={form}
          layout="vertical"
          preserve={false}
          initialValues={valoresIniciais}
          disabled={somenteLeitura}
          onFinish={onSalvar}
          onValuesChange={(...args) => {
            setAlterado(true)
            onValuesChange?.(...args)
          }}
          scrollToFirstError
          {...propsForm}
        >
          {typeof children === 'function' ? children(fechar) : children}
          {/* Enter em qualquer campo envia */}
          <button type="submit" hidden aria-hidden="true" tabIndex={-1} />
        </Form>
      </div>
    </PainelLateral>
  )
}
