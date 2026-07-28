# Critérios de Aceitação — Nexus

Formato Dado–Quando–Então (Given–When–Then / BDD).
Cada bloco referencia a história de usuário correspondente.

---

## HU-01 — Criar assistente

| Dado | Quando | Então |
|------|--------|-------|
| O modal de criação está aberto | O usuário preenche o nome e confirma | O assistente é criado, aparece na lista e seu card é exibido na tela inicial |
| O modal de criação está aberto | O usuário tenta confirmar sem preencher o nome | O sistema exibe mensagem de erro e não cria o assistente |

---

## HU-04 — Enviar documentos

| Dado | Quando | Então |
|------|--------|-------|
| Um assistente está selecionado | O usuário envia um PDF de até 10 MB | O sistema confirma o recebimento e inicia o processamento em segundo plano |
| Um assistente está selecionado | O usuário tenta enviar um arquivo .exe | O sistema rejeita o arquivo e exibe mensagem de formato não suportado |

---

## HU-06 — Chat com assistente

| Dado | Quando | Então |
|------|--------|-------|
| Um assistente com documentos indexados está selecionado | O usuário envia uma pergunta | O sistema retorna uma resposta baseada nos trechos recuperados da base daquele assistente |
| Dois assistentes com bases distintas estão cadastrados | O usuário conversa com o Assistente A | A resposta não contém informações pertencentes apenas à base do Assistente B |

---

## HU-07 — Histórico de conversa

| Dado | Quando | Então |
|------|--------|-------|
| Uma conversa com mensagens existe | O usuário reinicia a aplicação e abre a conversa | Todas as mensagens anteriores são exibidas na ordem correta |
| Uma conversa ativa tem 5 mensagens | O usuário envia a 6ª mensagem | O histórico completo (incluindo as 5 anteriores) é enviado como contexto ao LLM |

---

## HU-08 — Nomeação automática de conversa

| Dado | Quando | Então |
|------|--------|-------|
| Uma nova conversa é criada e não tem nome | O usuário envia a primeira mensagem | O sistema define o nome da conversa com base no conteúdo dessa mensagem |
| Uma conversa já possui nome definido | O usuário envia mensagens adicionais | O nome da conversa permanece inalterado |

---

## HU-10 — Inferência automática de assistente

| Dado | Quando | Então |
|------|--------|-------|
| Nenhum assistente está selecionado e há assistentes cadastrados | O usuário digita uma pergunta e clica em Enviar | O sistema exibe o spinner de inferência, identifica o assistente mais adequado, seleciona-o e envia a mensagem |
| A inferência é concluída com sucesso | O sistema encontra um assistente relevante | O chat é aberto com o assistente inferido e a resposta é exibida |

---

## HU-11 — Falha na inferência

| Dado | Quando | Então |
|------|--------|-------|
| Nenhum assistente está selecionado | O sistema não consegue identificar um assistente relevante para a pergunta | O popup de aviso é exibido com orientação para reformular a pergunta ou selecionar manualmente |
| O popup de aviso está visível | O usuário clica em "Reformular pergunta" | O popup é fechado e o campo de texto retorna o foco ao usuário |
| O popup de aviso está visível | O usuário clica em "Ver assistentes" | O modal de criação de assistente é aberto |

---

## HU-12 — Configurar chave de API

| Dado | Quando | Então |
|------|--------|-------|
| A chave de API não está configurada | O usuário acessa o painel de administração, insere a chave e salva | O sistema armazena a chave criptografada e exibe o status "Configurada" |
| A chave já está configurada | O usuário tenta iniciar um chat | O sistema permite o envio da mensagem normalmente |
| A chave não está configurada | O usuário tenta iniciar um chat | O sistema bloqueia o envio e exibe mensagem orientando a configurar a chave |

---

## HU-13 — Testar conectividade com LLM

| Dado | Quando | Então |
|------|--------|-------|
| A chave de API está configurada | O usuário clica em "Testar LLM" | O sistema envia uma requisição de teste e exibe o resultado (sucesso + prévia da resposta ou falha + mensagem de erro) |
| A chave de API está incorreta | O usuário clica em "Testar LLM" | O sistema exibe mensagem de falha com indicação do erro retornado pelo provedor |

---

## Critério de Aceite de Integração (MVP)

| Dado | Quando | Então |
|------|--------|-------|
| Dois assistentes com documentos distintos estão indexados | Uma pergunta relevante apenas para o Assistente A é enviada ao Assistente A | A resposta cita exclusivamente conteúdo da base do Assistente A |
| O ambiente foi reiniciado (containers recriados) | O usuário acessa uma conversa anterior | O histórico completo está disponível e o assistente responde com base no mesmo contexto de antes |
