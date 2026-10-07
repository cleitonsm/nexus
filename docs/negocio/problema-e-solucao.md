# Problema e Solução

## Problema

O conhecimento organizacional normalmente fica espalhado em arquivos, canais de conversa,
pastas compartilhadas e memória de especialistas. Isso gera respostas inconsistentes,
retrabalho e dificuldade para integrar novas pessoas aos processos.

## Solução

O Nexus usa RAG para buscar trechos relevantes em documentos oficiais antes de gerar uma
resposta. A resposta deve ser construída a partir do contexto recuperado, reduzindo respostas
genéricas e aumentando a rastreabilidade.

## Princípios

- Documentos oficiais são a fonte primária de conhecimento.
- Cada assistente possui uma base de conhecimento isolada.
- Conversas devem preservar histórico sem contaminar a recuperação entre assistentes.
- A arquitetura deve permitir trocar provedores de LLM sem afetar o domínio.

## Evolução RAG Enterprise

### Problemas que o MVP ainda não resolve

- O colaborador precisa usar as mesmas palavras do documento para encontrar a resposta.
- Não há como conferir de onde a resposta veio.
- Todo conteúdo fica disponível a qualquer pessoa com acesso à rede.
- Um documento desatualizado continua influenciando as respostas.
- Não se sabe se o assistente está respondendo bem, nem quanto custa.

### Solução Planejada

Recuperação por significado combinada com busca por termos exatos, reordenação dos resultados,
respostas com fontes, login pelo Keycloak com permissões por assistente e por documento, gestão do
ciclo de vida dos documentos e medição contínua de qualidade.

### Princípios Acrescentados

- Toda resposta fundamentada indica suas fontes.
- Cada pessoa só recebe conhecimento que pode acessar; a restrição é aplicada no servidor.
- Nada é considerado melhoria sem medida que a comprove.
- O conteúdo dos documentos não sai do ambiente na vetorização, na busca nem no reranking.
- O que está nos documentos é informação, nunca instrução para o assistente.
