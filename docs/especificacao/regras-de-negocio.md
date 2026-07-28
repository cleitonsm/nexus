# Regras de Negócio — Nexus

Notação: `RN-XX` — Regra de Negócio.

---

## Assistentes

| ID    | Regra |
|-------|-------|
| RN-01 | O nome do assistente é obrigatório e deve ter entre 1 e 255 caracteres. |
| RN-02 | Um assistente não pode ser excluído enquanto estiver sendo referenciado por uma conversa ativa na sessão do usuário; a exclusão deve ser confirmada explicitamente. |
| RN-03 | Cada assistente possui uma base de conhecimento isolada — documentos enviados a um assistente são vinculados exclusivamente a ele. |

## Inferência Automática de Assistente

| ID    | Regra |
|-------|-------|
| RN-04 | A inferência automática só é acionada quando o usuário envia uma mensagem sem ter selecionado um assistente ativo. |
| RN-05 | A inferência consulta todos os assistentes cadastrados e retorna o `assistant_id` do mais adequado ou `null` caso nenhum seja suficientemente relevante. |
| RN-06 | Quando a inferência retornar `null`, o sistema não deve enviar a mensagem ao LLM; deve exibir um aviso ao usuário e aguardar nova ação. |

## Documentos

| ID    | Regra |
|-------|-------|
| RN-07 | Formatos aceitos para upload: PDF, TXT, Markdown (.md), DOC e DOCX. Outros formatos devem ser rejeitados com mensagem de erro. |
| RN-08 | Um mesmo arquivo pode ser enviado mais de uma vez para o mesmo assistente; cada upload gera um novo conjunto de chunks independente. |

## Conversas

| ID    | Regra |
|-------|-------|
| RN-09 | Uma conversa está sempre associada a um único assistente e não pode ser transferida entre assistentes. |
| RN-10 | O nome da conversa é definido automaticamente a partir da primeira mensagem do usuário e não pode ser alterado pelo usuário no MVP. |
| RN-11 | O histórico de mensagens de uma conversa deve ser incluído no contexto enviado ao LLM para manter coerência na troca de turnos. |

## Configuração de LLM

| ID    | Regra |
|-------|-------|
| RN-12 | A chave de API deve ser configurada antes que qualquer operação de chat, inferência ou teste de LLM seja realizada; caso contrário, a operação deve ser bloqueada com mensagem orientativa. |
| RN-13 | A mesma chave de API é compartilhada globalmente por todos os assistentes no MVP (não há configuração por assistente). |
