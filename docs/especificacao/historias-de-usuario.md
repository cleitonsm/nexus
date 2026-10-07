# Histórias de Usuário — Nexus

Notação: `HU-XX` — História de Usuário.
Formato: *Como \<perfil\>, quero \<ação\>, para \<benefício\>.*

---

## Épico 1 — Gestão de Assistentes

**HU-01**
Como usuário, quero criar um assistente com nome e descrição, para organizar bases de conhecimento de diferentes domínios ou projetos.

**HU-02**
Como usuário, quero listar os assistentes disponíveis, para saber quais domínios estão cobertos e escolher com qual conversar.

**HU-03**
Como usuário, quero excluir um assistente, para remover bases de conhecimento desatualizadas ou incorretas sem deixar dados residuais.

---

## Épico 2 — Ingestão de Documentos

**HU-04**
Como usuário, quero enviar documentos para um assistente específico, para que ele passe a responder perguntas com base nesses materiais.

**HU-05**
Como usuário, quero que o sistema processe os documentos automaticamente após o upload, para não precisar executar nenhuma etapa manual de indexação.

---

## Épico 3 — Chat Conversacional

**HU-06**
Como usuário, quero iniciar uma conversa com um assistente selecionado e fazer perguntas em linguagem natural, para obter respostas fundamentadas nos documentos daquele assistente.

**HU-07**
Como usuário, quero que o chat preserve o histórico da conversa, para que eu possa retomar interações anteriores e o assistente mantenha o contexto ao responder.

**HU-08**
Como usuário, quero que a conversa seja nomeada automaticamente, para identificar facilmente conversas passadas na lista lateral.

**HU-09**
Como usuário, quero excluir uma conversa, para manter o histórico organizado e remover sessões desnecessárias.

---

## Épico 4 — Inferência Automática de Assistente

**HU-10**
Como usuário, quero digitar uma pergunta sem precisar escolher o assistente manualmente, para que o sistema identifique automaticamente o mais adequado e já inicie o chat.

**HU-11**
Como usuário, quero ser informado quando o sistema não conseguir identificar o assistente adequado para minha pergunta, para que eu possa reformulá-la ou selecionar manualmente o assistente desejado.

---

## Épico 5 — Configuração de LLM

**HU-12**
Como administrador, quero configurar a chave de API do provedor LLM pela interface, para que o sistema consiga se comunicar com o modelo de linguagem sem expor a chave no código.

**HU-13**
Como administrador, quero testar a conectividade com o LLM após configurar a chave, para confirmar que a integração está funcionando antes de disponibilizar o sistema para uso.

---

## Épico 6 — Experiência Inicial (Onboarding)

**HU-14**
Como novo usuário, quero ver cards explicativos na tela inicial quando não houver assistentes, para entender o que o Nexus faz e como começar a usá-lo.

---

# Evolução — RAG Enterprise

As histórias abaixo descrevem a evolução planejada.

**Situação em 2026-10-07:** HU-15 e HU-16 (Épico 7) estão atendidas pela Fase 1, em validação no
ambiente Docker; o cadastro de perguntas é feito editando o arquivo do conjunto de referência. As
histórias HU-17 a HU-37 ainda não estão implementadas.
Perfis utilizados: usuário, curador, administrador e equipe técnica
(ver [`docs/negocio/publico-alvo.md`](../negocio/publico-alvo.md)).

---

## Épico 7 — Qualidade Mensurável

**HU-15**
Como curador, quero cadastrar perguntas de referência com a resposta esperada e o documento de origem, para que a qualidade do assistente possa ser medida de forma objetiva.

**HU-16**
Como equipe técnica, quero executar a avaliação com um comando e comparar o resultado com a execução anterior, para saber se uma mudança melhorou ou piorou as respostas.

---

## Épico 8 — Recuperação Semântica

**HU-17**
Como usuário, quero fazer perguntas com minhas próprias palavras, para encontrar a informação mesmo sem usar os termos exatos do documento.

**HU-18**
Como administrador, quero reindexar a base de um assistente sem interromper o uso, para adotar melhorias de recuperação sem indisponibilidade.

---

## Épico 9 — Respostas Confiáveis

**HU-19**
Como usuário, quero que perguntas com siglas, códigos e nomes próprios encontrem o trecho exato, para não depender apenas de semelhança de sentido.

**HU-20**
Como usuário, quero ver as fontes de cada resposta, com documento, seção e página, para conferir a informação no material oficial.

**HU-21**
Como usuário, quero fazer perguntas de continuação que dependem do que já foi dito, para conversar naturalmente sem repetir o contexto.

**HU-22**
Como usuário, quero ser informado com clareza quando a base não contém evidência suficiente, para não confiar em uma resposta sem fundamento.

---

## Épico 10 — Acesso Seguro

**HU-23**
Como usuário, quero entrar no Nexus com minha conta corporativa pelo Keycloak, para não precisar de outra senha.

**HU-24**
Como administrador, quero definir quais grupos podem usar cada assistente, para que cada área acesse apenas o conhecimento que lhe cabe.

**HU-25**
Como curador, quero restringir um documento a grupos específicos, para que conteúdo sensível só apareça nas respostas de quem pode vê-lo.

**HU-26**
Como administrador, quero consultar a trilha de auditoria, para saber quem perguntou, quais documentos foram usados e quem alterou a base.

**HU-27**
Como usuário, quero que minhas conversas sejam visíveis apenas para mim, para poder consultar o assistente com privacidade.

---

## Épico 11 — Gestão de Documentos

**HU-28**
Como curador, quero enviar documentos sem esperar o processamento e acompanhar o estado de cada um, para continuar trabalhando enquanto a base é atualizada.

**HU-29**
Como curador, quero excluir um documento da base, para que conteúdo desatualizado deixe de influenciar as respostas.

**HU-30**
Como curador, quero substituir um documento por uma nova versão, para manter a base atual sem deixar o assistente sem resposta durante a troca.

**HU-31**
Como curador, quero enviar PDFs digitalizados e documentos com tabelas, para aproveitar materiais que hoje não são lidos corretamente.

**HU-32**
Como curador, quero ser avisado ao enviar um arquivo que já existe na base, para evitar conteúdo duplicado.

---

## Épico 12 — Operação e Governança

**HU-33**
Como usuário, quero ver a resposta sendo escrita à medida que é gerada, para não ficar esperando sem retorno.

**HU-34**
Como usuário, quero avaliar se uma resposta foi útil, para ajudar a melhorar o assistente.

**HU-35**
Como equipe técnica, quero rastrear cada resposta por etapa do processamento, para diagnosticar lentidão e falhas.

**HU-36**
Como administrador, quero acompanhar o consumo e o custo estimado por conversa e limitar o uso por usuário, para manter os gastos com LLM sob controle.

**HU-37**
Como equipe técnica, quero restaurar a base a partir de um backup, para recuperar o serviço após uma falha.
