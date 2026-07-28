# Requisitos Funcionais — Nexus

Origem: análise das entrevistas, documentos de negócio e codebase do MVP.
Notação: `RF-XX` — Requisito Funcional.

---

## Módulo: Assistentes

| ID    | Descrição |
|-------|-----------|
| RF-01 | O sistema deve permitir criar um assistente informando nome, descrição opcional e prompt inicial opcional. |
| RF-02 | O sistema deve listar todos os assistentes cadastrados. |
| RF-03 | O sistema deve permitir excluir um assistente, removendo também sua base de documentos e histórico de conversas associados. |
| RF-04 | O sistema deve permitir selecionar um assistente ativo para iniciar ou retomar conversas. |
| RF-05 | O sistema deve inferir automaticamente o assistente mais adequado para responder a uma pergunta quando nenhum assistente estiver selecionado, utilizando um fluxo LangGraph de classificação via LLM. |

## Módulo: Documentos / Base de Conhecimento

| ID    | Descrição |
|-------|-----------|
| RF-06 | O sistema deve permitir o upload de documentos (PDF, TXT, MD, DOC, DOCX) vinculados a um assistente específico. |
| RF-07 | O sistema deve extrair, fragmentar (chunking) e indexar automaticamente o conteúdo dos documentos enviados na base vetorial do assistente correspondente. |
| RF-08 | O sistema deve garantir que a base de conhecimento de cada assistente seja isolada das demais, impedindo mistura de contextos. |

## Módulo: Conversas e Chat

| ID    | Descrição |
|-------|-----------|
| RF-09 | O sistema deve permitir criar uma nova conversa associada a um assistente. |
| RF-10 | O sistema deve enviar uma mensagem do usuário, recuperar os trechos mais relevantes da base vetorial do assistente e gerar uma resposta contextualizada. |
| RF-11 | O sistema deve persistir o histórico completo de mensagens de cada conversa. |
| RF-12 | O sistema deve nomear a conversa automaticamente a partir do conteúdo da primeira mensagem do usuário. |
| RF-13 | O sistema deve permitir listar as conversas de um assistente. |
| RF-14 | O sistema deve permitir carregar e exibir as mensagens de uma conversa previamente salva. |
| RF-15 | O sistema deve permitir excluir uma conversa e seu histórico de mensagens. |

## Módulo: Configuração de LLM

| ID    | Descrição |
|-------|-----------|
| RF-16 | O sistema deve permitir configurar e persistir de forma criptografada a chave de API do provedor LLM global. |
| RF-17 | O sistema deve exibir o status atual da chave de API (configurada / não configurada). |
| RF-18 | O sistema deve permitir testar a conectividade com o provedor LLM usando a chave cadastrada, retornando resultado e prévia da resposta. |

## Módulo: Interface (Frontend)

| ID    | Descrição |
|-------|-----------|
| RF-19 | O sistema deve exibir cards de boas-vindas na tela inicial quando não houver assistentes cadastrados, com atalho para criação do primeiro assistente. |
| RF-20 | O sistema deve exibir os três assistentes mais recentes como cards de seleção rápida na tela inicial quando houver assistentes cadastrados. |
| RF-21 | O sistema deve exibir uma tela de chat com área de mensagens, campo de entrada e botão de envio. |
| RF-22 | O sistema deve exibir um indicador de carregamento (spinner) enquanto a inferência automática de assistente estiver em andamento. |
| RF-23 | O sistema deve exibir um popup de aviso quando não for possível inferir o assistente adequado, orientando o usuário a reformular a pergunta ou selecionar manualmente um assistente. |
