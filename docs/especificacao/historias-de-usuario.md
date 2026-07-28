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
