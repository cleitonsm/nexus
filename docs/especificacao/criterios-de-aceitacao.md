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

---

# Evolução — RAG Enterprise

Critérios das histórias HU-15 a HU-37. Os critérios de HU-15 e HU-16 já são verificados por testes
automatizados da Fase 1, exceto o bloqueio na integração contínua, previsto para a Fase 6; as
demais funcionalidades ainda não estão implementadas. Os mesmos critérios aparecem em formato Gherkin nas especificações SDD em
[`specs/`](specs/README.md).

---

## HU-15 — Conjunto de referência

| Dado | Quando | Então |
|------|--------|-------|
| Um assistente piloto possui documentos indexados | O curador registra uma pergunta com resposta esperada e documento de origem | O item passa a integrar o conjunto de referência do assistente |
| Um item é registrado sem documento de origem | A avaliação é executada | O item é rejeitado na validação do conjunto e apontado no relatório |

---

## HU-16 — Executar avaliação

| Dado | Quando | Então |
|------|--------|-------|
| O conjunto de referência de um assistente existe | A equipe técnica executa o comando de avaliação | O relatório apresenta recall@5, MRR, fidelidade e taxa de fallback correto, com commit e parâmetros utilizados |
| Existe um relatório de execução anterior | Uma nova avaliação é concluída | O relatório mostra a diferença de cada métrica em relação à execução anterior |
| Uma métrica regride além da tolerância | A avaliação roda na integração contínua | A verificação falha e a mudança é bloqueada |

---

## HU-17 — Perguntar com as próprias palavras

| Dado | Quando | Então |
|------|--------|-------|
| Um documento indexado contém a frase "o reembolso é feito em até 10 dias úteis" | O usuário pergunta "quanto tempo demora para devolverem meu dinheiro?" | O trecho sobre reembolso está entre os cinco primeiros recuperados |
| O conjunto de referência do assistente piloto está disponível | A avaliação é executada após a troca do modelo de embedding | O recall@5 é igual ou superior a 0,80 |

---

## HU-18 — Reindexar sem interrupção

| Dado | Quando | Então |
|------|--------|-------|
| Um assistente possui base indexada e usuários conversando | O administrador inicia a reindexação | As consultas continuam sendo respondidas com a base vigente até a conclusão |
| A reindexação foi concluída com sucesso | O alias é trocado para a nova collection | As consultas passam a usar a nova base e a collection antiga é removida |
| A reindexação falha no meio do processo | O sistema registra a falha | A base vigente permanece inalterada e a collection parcial é descartada |

---

## HU-19 — Termos exatos

| Dado | Quando | Então |
|------|--------|-------|
| Um documento indexado menciona o código "NR-35" em um único trecho | O usuário pergunta "o que diz a NR-35?" | O trecho que contém "NR-35" está entre os cinco primeiros após o reranking |

---

## HU-20 — Fontes da resposta

| Dado | Quando | Então |
|------|--------|-------|
| Uma resposta foi gerada a partir de trechos recuperados | A resposta é exibida no chat | As fontes aparecem com nome do documento, seção e página |
| As fontes de uma resposta estão visíveis | O usuário clica em uma fonte | O trecho citado é exibido |
| O LLM devolve uma resposta sem nenhuma citação válida | O sistema valida a resposta | A resposta é substituída pelo fallback (RN-18) |

---

## HU-21 — Perguntas de continuação

| Dado | Quando | Então |
|------|--------|-------|
| O usuário perguntou sobre a política de férias e recebeu resposta | O usuário pergunta "e para estagiários?" | A busca é feita com uma consulta reescrita que inclui o tema férias |

---

## HU-22 — Ausência de evidência

| Dado | Quando | Então |
|------|--------|-------|
| A base do assistente não trata do assunto perguntado | O usuário envia a pergunta | O sistema responde com o fallback explícito e não chama o LLM |
| O conjunto de perguntas fora do escopo está disponível | A avaliação é executada | Pelo menos 90% dessas perguntas resultam em fallback |

---

## HU-23 — Login pelo Keycloak

| Dado | Quando | Então |
|------|--------|-------|
| O usuário não está autenticado | Ele acessa qualquer rota do frontend | É redirecionado para a tela de login do Keycloak |
| O usuário autenticou-se com sucesso no Keycloak | Ele retorna ao Nexus | A interface é exibida com seu nome e apenas as funcionalidades do seu papel |
| Uma requisição chega à API sem token ou com token expirado | A API processa a requisição | A resposta é 401 e nenhum dado é retornado |

---

## HU-24 — Acesso por assistente

| Dado | Quando | Então |
|------|--------|-------|
| O assistente "RH" está vinculado ao grupo "rh" | Um usuário do grupo "financeiro" lista os assistentes | O assistente "RH" não aparece |
| O assistente "RH" está vinculado ao grupo "rh" | Um usuário do grupo "financeiro" chama diretamente a API de chat do assistente "RH" | A resposta é 403 e o evento é registrado na auditoria |
| Um assistente foi criado sem grupo vinculado | Um usuário comum lista os assistentes | O assistente não aparece; apenas administradores o veem |

---

## HU-25 — Documento restrito

| Dado | Quando | Então |
|------|--------|-------|
| Um documento do assistente está restrito ao grupo "diretoria" | Um usuário fora desse grupo faz uma pergunta cuja resposta só existe nesse documento | Nenhum trecho do documento é recuperado e o sistema responde com o fallback |
| O mesmo documento restrito | Um usuário do grupo "diretoria" faz a mesma pergunta | A resposta usa o documento e o cita como fonte |

---

## HU-26 — Trilha de auditoria

| Dado | Quando | Então |
|------|--------|-------|
| Um usuário fez uma pergunta | O administrador consulta a auditoria | O evento mostra usuário, assistente, data e documentos recuperados, sem o texto integral dos documentos |
| Um evento de auditoria existe | Qualquer usuário tenta alterá-lo ou excluí-lo pela API | A operação não é oferecida e a tentativa é rejeitada |

---

## HU-27 — Conversas privadas

| Dado | Quando | Então |
|------|--------|-------|
| O usuário A possui uma conversa | O usuário B solicita essa conversa pelo identificador | A resposta é 404 e o conteúdo não é exposto |

---

## HU-28 — Upload assíncrono e estado

| Dado | Quando | Então |
|------|--------|-------|
| Um assistente está selecionado | O curador envia um PDF de 20 MB | A API responde em até 2 segundos com o documento no estado "pendente" |
| Um documento está em processamento | O worker conclui a indexação | O estado muda para "indexado" na interface sem recarregar a página |
| O processamento falha três vezes | O worker registra a última falha | O estado muda para "falhou" e o motivo é exibido |
| O worker é reiniciado durante o processamento | O worker volta a executar | O documento é processado uma única vez, sem chunks duplicados |

---

## HU-29 — Excluir documento

| Dado | Quando | Então |
|------|--------|-------|
| Um documento indexado é a única fonte sobre um assunto | O curador exclui o documento e um usuário pergunta sobre o assunto | O sistema responde com o fallback |
| Uma resposta antiga citava o documento excluído | O usuário abre a conversa antiga | A citação aparece marcada como documento removido |

---

## HU-30 — Substituir documento

| Dado | Quando | Então |
|------|--------|-------|
| Um documento indexado está sendo substituído | A nova versão ainda está em processamento | As respostas continuam usando a versão anterior |
| A nova versão foi indexada | Um usuário faz uma pergunta | Apenas trechos da nova versão são recuperados |

---

## HU-31 — PDFs digitalizados e tabelas

| Dado | Quando | Então |
|------|--------|-------|
| Um PDF contém apenas imagens de páginas digitalizadas | O curador o envia | O texto é extraído por OCR e o documento chega ao estado "indexado" |
| Um documento contém uma tabela de valores | Um usuário pergunta por um valor da tabela | O trecho recuperado preserva a linha e o cabeçalho correspondentes |

---

## HU-32 — Arquivo duplicado

| Dado | Quando | Então |
|------|--------|-------|
| Um arquivo já foi indexado no assistente | O curador envia o mesmo arquivo novamente | O sistema informa o documento existente e não cria novos chunks |

---

## HU-33 — Resposta em streaming

| Dado | Quando | Então |
|------|--------|-------|
| O usuário enviou uma pergunta com contexto disponível | O LLM começa a gerar a resposta | O texto aparece progressivamente no chat e as fontes são exibidas ao final |

---

## HU-34 — Avaliar resposta

| Dado | Quando | Então |
|------|--------|-------|
| Uma resposta está exibida no chat | O usuário marca "não útil" e escreve um comentário | A avaliação é gravada e fica disponível ao curador como candidata ao conjunto de referência |

---

## HU-35 — Rastrear resposta

| Dado | Quando | Então |
|------|--------|-------|
| Uma resposta foi gerada | A equipe técnica busca pelo identificador da requisição | O rastreamento mostra a duração de cada etapa do grafo e a chamada ao LLM |

---

## HU-36 — Custo e limite de uso

| Dado | Quando | Então |
|------|--------|-------|
| Conversas foram realizadas no período | O administrador consulta o consumo | São exibidos tokens e custo estimado por conversa e por usuário |
| O usuário atingiu o limite de uso da janela | Ele envia nova pergunta | A resposta é 429 com mensagem informando quando poderá perguntar novamente |

---

## HU-37 — Restaurar backup

| Dado | Quando | Então |
|------|--------|-------|
| Existe um backup do PostgreSQL e um snapshot do Qdrant do dia anterior | A equipe técnica executa o procedimento de restauração em ambiente limpo | Assistentes, documentos, conversas e buscas voltam a funcionar com os dados do backup |

---

## Critério de Aceite de Integração (RAG Enterprise)

| Dado | Quando | Então |
|------|--------|-------|
| Dois usuários de grupos distintos e um assistente com um documento restrito a um dos grupos | Ambos fazem a mesma pergunta | Apenas o usuário autorizado recebe resposta com a citação do documento; o outro recebe o fallback |
| Um documento foi enviado, indexado em segundo plano e depois excluído | Um usuário pergunta sobre seu conteúdo antes e depois da exclusão | Antes, a resposta cita o documento; depois, o sistema responde com o fallback |
| O ambiente foi recriado com `docker compose up` | Um usuário autentica-se pelo Keycloak e retoma uma conversa | O histórico, as citações e as permissões permanecem como antes |
| A avaliação de qualidade foi executada na versão final | O relatório é gerado | Recall@5, fidelidade e taxa de fallback correto atendem RNF-19, RNF-20 e RNF-21 |
