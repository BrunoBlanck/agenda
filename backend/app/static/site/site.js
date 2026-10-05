// Site de agendamento: melhorias opcionais. Sem este arquivo, todas as páginas funcionam (SIT-09).
(function () {
  'use strict'

  // Passo 2: trocar o profissional já atualiza os horários (o botão "Atualizar" some)
  document.querySelectorAll('form[data-auto]').forEach(function (form) {
    var lista = form.querySelector('select')
    var botao = form.querySelector('[data-atualizar]')
    if (!lista) return
    if (botao) botao.hidden = true
    lista.addEventListener('change', function () {
      form.submit()
    })
  })

  // Faixa de dias: rola até o dia marcado
  var faixa = document.querySelector('[data-dias]')
  var marcado = faixa && faixa.querySelector('[aria-current]')
  if (marcado) {
    var item = marcado.parentElement
    faixa.scrollLeft = item.offsetLeft - (faixa.clientWidth - item.offsetWidth) / 2
  }

  // Passo 3: um envio só (o botão fica desabilitado depois do clique)
  document.querySelectorAll('form[data-enviar]').forEach(function (form) {
    form.addEventListener('submit', function (evento) {
      if (form.getAttribute('data-enviado')) {
        evento.preventDefault()
        return
      }
      form.setAttribute('data-enviado', 'sim')
      var botao = form.querySelector('button[type="submit"]')
      if (botao) {
        botao.setAttribute('data-texto', botao.textContent)
        botao.disabled = true
        botao.textContent = botao.getAttribute('data-enviando') || botao.textContent
      }
    })
  })

  // Voltar pelo histórico (cache de página do navegador): o botão de envio volta a funcionar
  window.addEventListener('pageshow', function (evento) {
    if (!evento.persisted) return
    document.querySelectorAll('form[data-enviar]').forEach(function (form) {
      form.removeAttribute('data-enviado')
      var botao = form.querySelector('button[type="submit"]')
      if (botao) {
        botao.disabled = false
        if (botao.getAttribute('data-texto')) botao.textContent = botao.getAttribute('data-texto')
      }
    })
  })

  // Erros do formulário: leva o foco ao resumo dos erros
  var erros = document.getElementById('resumo-erros')
  if (erros) erros.focus()
})()
