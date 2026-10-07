// Site de agendamento: melhorias opcionais. Sem este arquivo, todas as páginas funcionam (SIT-09).
(function () {
  'use strict'

  var SVG = 'http://www.w3.org/2000/svg'
  var preferencia = function (consulta) {
    return !!(window.matchMedia && window.matchMedia(consulta).matches)
  }
  var comMouse = preferencia('(hover: hover) and (pointer: fine)')
  var semMovimento = preferencia('(prefers-reduced-motion: reduce)')

  // Faixas que rolam de lado (profissionais e dias): a opção marcada aparece no meio
  document.querySelectorAll('[data-faixa]').forEach(function (faixa) {
    var marcado = faixa.querySelector('[aria-current]')
    if (marcado) {
      var item = marcado.parentElement
      faixa.scrollLeft = item.offsetLeft - (faixa.clientWidth - item.offsetWidth) / 2
    }
    if (comMouse) colocarSetas(faixa)
  })

  // Com mouse, setas para rolar a faixa (no toque, o dedo já rola). Só atalho: os links seguem no Tab.
  function colocarSetas(faixa) {
    var caixa = document.createElement('div')
    caixa.className = 'faixa-caixa'
    faixa.parentNode.insertBefore(caixa, faixa)
    caixa.appendChild(faixa)
    var anterior = seta('seta-anterior', 'Anteriores', 'M15 5l-7 7 7 7')
    var proxima = seta('seta-proxima', 'Próximos', 'M9 5l7 7-7 7')
    caixa.appendChild(anterior)
    caixa.appendChild(proxima)

    function rolar(sentido) {
      faixa.scrollBy({ left: sentido * faixa.clientWidth * 0.8, behavior: semMovimento ? 'auto' : 'smooth' })
    }
    function atualizar() {
      var fim = faixa.scrollWidth - faixa.clientWidth
      anterior.hidden = faixa.scrollLeft <= 1
      proxima.hidden = faixa.scrollLeft >= fim - 1
    }
    anterior.addEventListener('click', function () { rolar(-1) })
    proxima.addEventListener('click', function () { rolar(1) })
    faixa.addEventListener('scroll', atualizar, { passive: true })
    window.addEventListener('resize', atualizar)
    atualizar()
  }

  function seta(classe, titulo, caminho) {
    var botao = document.createElement('button')
    botao.type = 'button'
    botao.className = 'seta-faixa ' + classe
    botao.title = titulo
    botao.tabIndex = -1
    botao.setAttribute('aria-hidden', 'true')
    var desenho = document.createElementNS(SVG, 'svg')
    desenho.setAttribute('class', 'icone')
    desenho.setAttribute('viewBox', '0 0 24 24')
    var traco = document.createElementNS(SVG, 'path')
    traco.setAttribute('d', caminho)
    desenho.appendChild(traco)
    botao.appendChild(desenho)
    return botao
  }

  // Senha: botão "Mostrar"/"Ocultar" dentro do campo
  document.querySelectorAll('input[type="password"]').forEach(function (campo) {
    var caixa = document.createElement('div')
    caixa.className = 'senha-caixa'
    campo.parentNode.insertBefore(caixa, campo)
    caixa.appendChild(campo)
    var botao = document.createElement('button')
    botao.type = 'button'
    botao.className = 'mostrar-senha'
    botao.setAttribute('aria-controls', campo.id)
    caixa.appendChild(botao)
    function mostrar(visivel) {
      campo.type = visivel ? 'text' : 'password'
      botao.textContent = visivel ? 'Ocultar' : 'Mostrar'
      botao.setAttribute('aria-label', visivel ? 'Ocultar senha' : 'Mostrar senha')
    }
    botao.addEventListener('click', function () {
      mostrar(campo.type === 'password')
      campo.focus()
    })
    if (campo.form) {
      campo.form.addEventListener('submit', function () { mostrar(false) })
    }
    mostrar(false)
  })

  // Formulários: um envio só (o botão fica desabilitado depois do clique)
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
