// Hook UserPromptSubmit: quando a mensagem do usuário parece uma ordem permanente
// ("em todas as telas", "sempre", "padronize"...), lembra o modelo de registrá-la como diretriz.
// Nunca bloqueia a mensagem: em qualquer erro, sai em silêncio.

const SINAIS = [
  /\bem tod[oa]s? (as|os) /,
  /\btod[oa]s? (as|os) (telas?|rotas?|endpoints?|formul[aá]rios?|tabelas?|p[aá]ginas?|listas?|componentes?|servi[cç]os?)\b/,
  /\b(toda|todo) (tela|rota|endpoint|formul[aá]rio|tabela|p[aá]gina|lista|componente|vez que)\b/,
  /\bsempre\b/,
  /\bnunca mais\b/,
  /\bpadroniz/,
  /\ba partir de agora\b/,
  /\bdaqui (pra|para) frente\b/,
  /\bde agora em diante\b/,
  /\bn[aã]o (fa[cç]a|use|quero) mais\b/,
]

let entrada = ''
process.stdin.setEncoding('utf8')
process.stdin.on('data', (parte) => (entrada += parte))
process.stdin.on('end', () => {
  try {
    const texto = String(JSON.parse(entrada).prompt ?? '').toLowerCase()
    if (!SINAIS.some((sinal) => sinal.test(texto))) return
    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'UserPromptSubmit',
          additionalContext:
            'Lembrete do projeto: esta mensagem pode conter uma ordem permanente do usuário. ' +
            'Se ela vale além da tarefa atual (todas as telas/rotas, sempre, nunca mais, padronizar), ' +
            'registre-a como diretriz em .claude/diretrizes/ seguindo a skill `diretrizes` ANTES de executar, ' +
            'confira conflitos com as diretrizes ativas e planeje a aplicação no código que já existe. ' +
            'Se for só um ajuste pontual, ignore este lembrete. Na dúvida, pergunte ao usuário em uma linha.',
        },
      }),
    )
  } catch {
    // entrada inesperada: não atrapalha a mensagem do usuário
  }
})
