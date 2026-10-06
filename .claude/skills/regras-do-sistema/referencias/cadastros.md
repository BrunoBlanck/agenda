# Cadastros da loja

Fonte: `estrutura.md` 2.3, 2.4, 2.7 a 2.12, 2.15, 2.16, 2.18 a 2.21 e 6.1.

## Clientes (`CLI-*`)
- **CLI-01** Nome (só o primeiro, como a loja chama o cliente) e sobrenome **separados e obrigatórios**, em todo cadastro (painel e site). Listas e buscas usam o nome completo; mensagens ao cliente usam só o nome.
- **CLI-02** Telefone obrigatório; CPF opcional e único na loja quando preenchido; e-mail e nascimento opcionais; observações livres (alergias, preferências).
- **CLI-03** `canais` (lista): `loja`, `whatsapp`, `site`. Quem vem do site entra com `site`; telefone já existente na loja reaproveita o cadastro e só ganha o canal `site`.
- **CLI-04** Cliente com agendamentos **não é excluído** (409): inative.
- **CLI-05** CPF, telefone e e-mail são dados pessoais (LGPD): não aparecem em log, nem em respostas públicas.
- **CLI-06** No painel (tela Clientes), ver os códigos de confirmação pendentes do site e remover o acesso de um cliente ao site exigem **escrita** em *Clientes* (SIT-16 a SIT-20).

## Funcionários e cargos (`FUN-*`)
- **FUN-01** Funcionário é também o usuário do painel. E-mail obrigatório e único na loja (login); CPF único na loja quando preenchido.
- **FUN-02** Senha obrigatória no cadastro (mín. 8), opcional na edição (troca a senha).
- **FUN-03** Inativo não faz login, não aparece para novos agendamentos e não registra ponto; o histórico fica.
- **FUN-04** Funcionário **não é excluído**, só inativado. Não se inativa o último Administrador ativo (ACE-20). Atribuição de perfil segue ACE-19.
- **FUN-05** `cor_agenda` no formato `#rrggbb`. Cargo é **informativo** (quem define acesso é o perfil). Cargo com funcionários não é excluído (409).
- **FUN-06** Quem criou: `criado_por_funcionario` (na loja) ou `criado_por_superadmin` (suporte), no máximo um.

## Serviços (`SER-*`) — módulo Serviços
- **SER-01** Nome único na loja; duração em minutos `> 0`; preço não negativo (opcional).
- **SER-02** Serviço **ativo** precisa de **pelo menos um** profissional vinculado.
- **SER-03** Vínculos editados na tela de Serviços (os de locais também na tela de Locais, LOC-06): profissionais (`servico_funcionarios`), locais (`servico_locais`, só com módulo Locais) e materiais por atendimento (`servico_materiais`, quantidade `> 0`, só com módulo Materiais).
- **SER-04** Serviço sem locais vinculados = qualquer local ativo (AGE-12).

## Locais (`LOC-*`) — módulo Locais
- **LOC-01** Nome único na loja; `tipo` `presencial` ou `online`; `link_padrao` só em local online.
- **LOC-02** Local **não é excluído**, só inativado; inativo não aparece para novos agendamentos nem no site.
- **LOC-03** Cada link que pode ser usado ao mesmo tempo que outro é um local separado (o conflito é por local).
- **LOC-04** Rótulos (`rotulo_local`, `rotulo_local_plural`, padrão "Local"/"Locais") ficam em `loja_configuracoes`, editados na tela de Locais com escrita em *Locais*. Mudam os textos do **painel** (menu, títulos, campos).
- **LOC-05** A lista de locais traz a contagem de próximos agendamentos; a lista em si vem de `/agendamentos?local_id=`.
- **LOC-06** Na tela de Locais, quem tem **escrita em Locais** escolhe os serviços vinculados ao local (`servico_ids` em `POST/PUT /locais`, ausente = não mexe; só com módulo **Serviços** ativo; opções em `GET /locais/opcoes`). O vínculo **restringe o serviço, não o local** (SER-04 continua): serviço sem vínculo pode usar este local. Vincular serviço que aceitava qualquer local o restringe aos marcados; tirar o último local o libera para qualquer um. A tela avisa nos dois casos; agendamentos já marcados não mudam.

## Materiais e estoque (`MAT-*`) — módulo Materiais
- **MAT-01** Nome único na loja; unidade obrigatória; categoria opcional; estoque mínimo não negativo.
- **MAT-02** `quantidade_atual` **nunca é alterada diretamente**: só por uma movimentação (`entrada`, `saida_atendimento`, `ajuste`, `perda`) na mesma transação (trigger).
- **MAT-03** Sinais: entrada `> 0`; saída de atendimento e perda `< 0` (perda é informada positiva e gravada negativa); ajuste aceita os dois. `motivo` obrigatório em `ajuste` e `perda`. `saida_atendimento` exige `agendamento_id` e não é lançada à mão.
- **MAT-04** Movimentação não é alterada nem excluída: corrige-se com um `ajuste`.
- **MAT-05** O cadastro aceita `quantidade_inicial` (vira `entrada`); a edição não mexe no estoque.
- **MAT-06** `quantidade_atual < estoque_minimo` = **"Repor"** (tela Materiais e Início). Estoque pode ficar negativo (provisório, ABE-01).
- **MAT-07** Módulo desligado: sem consumo nem baixa ao concluir atendimentos.
- **MAT-08** Categoria com materiais e material usado em serviço não são excluídos (409).

## Controle de Tempo (`PON-*`) — módulo Controle de Tempo
- **PON-01** Registro de entrada/saída por funcionário. **Um registro em aberto** (sem saída) por funcionário (índice único parcial).
- **PON-02** Hora de entrada/saída é a do **servidor** (GER-17).
- **PON-03** Correções e lançamentos manuais só com escrita em *Ponto da equipe*, com **justificativa** obrigatória (`origem = manual`), nunca no futuro, gravando `editado_por`.
- **PON-04** Horas trabalhadas = `saida - entrada`, calculadas na consulta; data exibida no fuso da loja.
- **PON-05** Funcionário inativo não registra ponto.

## Dados da loja (`CFG-*`) — Configurações
- **CFG-01** A loja edita (escrita em *Dados da loja*): logo, nome fantasia (obrigatório), razão social (obrigatória), telefone, e-mail (formato válido), endereço (CEP preenche o resto) e CNPJ (opcional, dígitos validados, único entre lojas, gravado com máscara). CEP com máscara, UF em maiúsculas.
- **CFG-02** **Só o superadmin** altera `tipo`, `slug`, `plano_id`, `status`, `fuso_horario` e módulos.
- **CFG-03** Logo: PNG, JPEG ou WebP até 2 MB (tipo conferido pelos bytes do arquivo; SVG proibido), com nome aleatório numa pasta por loja (`ARQUIVOS_DIR`); trocar ou remover apaga o arquivo anterior depois de gravar. Envio: `PUT configuracoes/loja/logo` (loja, escrita em `config_loja`) e `PUT superadmin/lojas/{id}/logo`; servida em `GET /api/arquivos/logos/...` (pública).
- **CFG-04** Configurações novas que não são dados cadastrais vão para `loja_configuracoes`, não para `lojas`; se precisarem de acesso separado, cria-se um recurso novo.
