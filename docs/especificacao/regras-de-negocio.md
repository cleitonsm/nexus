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

---

# Evolução — RAG Enterprise

As regras passam a valer conforme cada fase for entregue.

**Situação em 2026-10-07:** RN-14 e RN-15 já são aplicadas pelo comando de avaliação da Fase 1 (a
regressão acima da tolerância encerra o comando com erro, e itens sem `validated_by` são
rejeitados). As regras RN-16 a RN-33 ainda não estão implementadas.

Regras do MVP revisadas por esta evolução:

- **RN-08** é substituída pela RN-26 (arquivo idêntico não é duplicado).
- **RN-11** é refinada pela RN-19 (histórico limitado por orçamento de tokens).
- **RN-12** e **RN-13** permanecem válidas; a configuração passa a exigir o papel administrador (RN-21).

## Avaliação e Qualidade

| ID    | Regra |
|-------|-------|
| RN-14 | Uma mudança que afete recuperação ou geração só pode ser aceita com avaliação registrada e sem regressão acima da tolerância definida. |
| RN-15 | O conjunto de referência só pode conter perguntas e respostas validadas por um curador do assistente. |

## Recuperação e Resposta

| ID    | Regra |
|-------|-------|
| RN-16 | A troca do modelo de embedding exige a reindexação completa da base antes que consultas sejam atendidas com o novo modelo. |
| RN-17 | Somente trechos com nota igual ou superior à nota mínima de relevância podem compor o contexto; sem trechos qualificados, o sistema responde com o fallback e não chama o LLM. |
| RN-18 | Toda resposta gerada a partir de contexto deve conter ao menos uma citação válida; uma resposta sem citação válida é substituída pelo fallback. |
| RN-19 | O histórico enviado ao LLM é limitado ao orçamento de tokens, preservando sempre as mensagens mais recentes. |

## Acesso e Auditoria

| ID    | Regra |
|-------|-------|
| RN-20 | Nenhuma funcionalidade é acessível sem autenticação pelo Keycloak; não existe cadastro local de usuários nem de senhas no Nexus. |
| RN-21 | Papéis: o administrador gerencia assistentes, permissões e a configuração do LLM; o curador gerencia documentos e o conjunto de referência dos assistentes a que tem acesso e, desde a SPEC-017 (D1), altera o nome, a descrição e o prompt inicial desses assistentes (criar, excluir e vincular grupos continua só com o administrador); o usuário conversa com os assistentes a que tem acesso. Desde a SPEC-018 (ADR 0014), todo usuário com papel usa o "Resumidor de documentos", assistente de sistema, e envia a ele documentos pessoais, visíveis só a quem enviou e só na própria conversa. |
| RN-22 | Um assistente sem grupo vinculado é visível apenas a administradores (negação por padrão). |
| RN-23 | Um documento restrito só pode compor o contexto de usuários pertencentes aos grupos autorizados; a restrição de documento nunca amplia o acesso além do definido para o assistente. |
| RN-24 | O conteúdo de uma conversa é privado de quem a criou; administradores consultam apenas os registros de auditoria. |
| RN-25 | Eventos de auditoria não podem ser alterados nem excluídos pela aplicação. |

## Documentos

| ID    | Regra |
|-------|-------|
| RN-26 | O envio de um arquivo idêntico (mesmo `content_hash`) a um documento já existente no mesmo assistente não cria novo documento; o sistema informa o documento existente. |
| RN-27 | Um documento só participa das buscas quando está no estado indexado. |
| RN-28 | Na substituição, a versão anterior permanece ativa até a nova versão estar indexada; em caso de falha, a versão anterior é mantida. |
| RN-29 | A exclusão de um documento remove seus vetores e o arquivo original e gera evento de auditoria; mensagens antigas preservam a citação, marcada como documento removido. |
| RN-30 | O tamanho máximo de upload é de 25 MB; após três tentativas de processamento sem sucesso, o documento passa ao estado falhou. |

## Operação e Governança

| ID    | Regra |
|-------|-------|
| RN-31 | O conteúdo recuperado dos documentos é tratado como dado; instruções presentes nesse conteúdo nunca são obedecidas pelo assistente. |
| RN-32 | Ao exceder o limite de uso, o usuário fica impedido de enviar novas perguntas até o início da janela seguinte, com mensagem orientativa. |
| RN-33 | Uma resposta avaliada como não útil torna-se candidata ao conjunto de referência somente após validação de um curador. |

## SPEC-018 — Resumidor de documentos

As regras completas estão na [SPEC-018](specs/SPEC-018-resumidor-de-documentos.md); aqui fica o resumo.

| ID | Regra |
|-------|-------|
| RN-55 | O assistente de sistema (`system_kind`) não é excluído nem tem perfil, recuperação, grupos ou base alterados (409 `system_assistant_readonly`); o administrador troca só credencial e modelo. |
| RN-56 | O resumidor é visível a todo usuário com papel e fica fora da escolha automática de assistente. |
| RN-57 | O resumidor é fixo e ocupa uma das 4 vagas do acesso rápido (3 à escolha do usuário); é o padrão de quem não personalizou e o recuo de quem perdeu o padrão. |
| RN-58 | O documento pessoal pertence ao dono e à conversa; um por conversa; nem o administrador o lê. |
| RN-59 | Na collection do resumidor, toda busca filtra também dono e conversa; sem eles, a busca é recusada antes de consultar. |
| RN-60 | Limites: 40.000 tokens contados pelo tokenizador local, 25 MB, formatos da ingestão, 30 dias de retenção, 10 documentos por dia. |
| RN-61 | A mensagem na conversa do resumidor vai para finalidade, progresso, resumo gravado, resumo sob medida (mini-resumos) ou pergunta pontual (RAG). |
| RN-62 a RN-64 | Resumo em pt-BR no modelo fixo, de 300 a 1.000 palavras, com citação por parte; lotes de 4 a 8 mil tokens; falha no resumo não derruba as perguntas. |
| RN-65 | O uso do resumo entra no custo do usuário e fica fora dos limites de perguntas. |
| RN-66 e RN-67 | Prompts versionados no código; o documento vai ao LLM sempre como dado; auditoria sem conteúdo. |
