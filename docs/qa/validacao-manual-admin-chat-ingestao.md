# Validacao manual: administracao, chat e ingestao

## Objetivo

Validar ponta a ponta o fluxo de configuracao da API key global, ingestao de documentos em formatos suportados e uso de historico de conversa no chat.

## Pre-condicoes

- Backend e frontend em execucao.
- Qdrant e PostgreSQL acessiveis.
- Variaveis de ambiente configuradas, incluindo `NEXUS_SECRETS_KEY`, `LLM_MODEL` e `LLM_API_URL`.

## Roteiro de validacao

1. Acesse a tela administrativa e confirme que o status inicial da API key aparece como "nao configurada".
2. Salve uma API key valida pela tela administrativa.
3. Confirme que a tela mostra apenas status "configurada" e nunca exibe o valor da chave.
4. Crie um assistente na tela de assistentes.
5. Envie documentos para o assistente nos formatos `.txt`, `.md`, `.pdf`, `.docx` e `.doc` (quando utilitario de extracao estiver disponivel no ambiente).
6. Abra a tela de chat, selecione o assistente e crie uma nova conversa.
7. Envie uma primeira pergunta relacionada ao documento ingerido e verifique resposta com contexto.
8. Envie uma segunda pergunta dependente da primeira e valide continuidade pelo historico.
9. Crie uma segunda conversa para o mesmo assistente e envie pergunta diferente.
10. Alterne entre as duas conversas e confirme carregamento correto do historico por conversa.
11. Tente enviar chat sem API key configurada e valide retorno de erro controlado.
12. Verifique no banco que a chave global foi persistida criptografada e sem valor em texto puro.

## Resultado esperado

- Chave global nunca retornada em endpoints e UI.
- Historico de conversa consistente por assistente e por conversa.
- Ingestao funcionando para formatos suportados.
- Chat utiliza contexto de RAG e historico anterior quando disponiveis.
