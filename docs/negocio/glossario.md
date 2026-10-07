# Glossário

- **Assistente**: entidade conversacional com escopo, documentos e histórico próprios.
- **RAG**: técnica que recupera contexto externo antes de gerar uma resposta.
- **Chunk**: trecho de documento preparado para busca vetorial.
- **Embedding**: representação numérica de texto usada em busca semântica.
- **Collection**: agrupamento de vetores no Qdrant. No Nexus, cada assistente deve ter sua
  própria collection.
- **LLM**: modelo de linguagem usado para gerar a resposta final.
- **LangGraph**: biblioteca para modelar fluxos conversacionais com etapas explícitas.
- **Fonte oficial**: documento enviado e aceito como base de conhecimento de um assistente.

## Termos da Evolução RAG Enterprise

- **Embedding semântico**: vetor produzido por um modelo de linguagem, que aproxima textos de
  mesmo sentido mesmo quando usam palavras diferentes.
- **Vetor esparso (BM25)**: representação baseada na frequência de termos, usada para encontrar
  correspondências exatas, como siglas e códigos.
- **Busca híbrida**: combinação da busca por significado com a busca por termos exatos.
- **RRF (Reciprocal Rank Fusion)**: técnica que une os resultados de duas buscas pela posição de
  cada item.
- **Reranking**: segunda etapa de ordenação, em que um modelo compara a pergunta com cada trecho
  candidato e atribui uma nota de relevância.
- **Nota mínima de relevância**: valor abaixo do qual um trecho é descartado; sem trechos acima
  dela, o assistente responde com o fallback.
- **Fallback**: resposta explícita de que a base não contém evidência suficiente.
- **Citação**: referência ao documento, à seção e à página que sustentam uma resposta.
- **Reescrita da pergunta**: transformação de uma pergunta de continuação em uma consulta completa,
  usando o histórico da conversa.
- **Chunking estrutural**: divisão do documento respeitando títulos, parágrafos e tabelas.
- **Reindexação**: reconstrução dos vetores de uma base após mudança de modelo ou de chunking.
- **Alias**: nome estável que aponta para a versão vigente de uma collection no Qdrant.
- **Conjunto de referência**: perguntas com resposta esperada e documento de origem, validadas por
  um curador e usadas para medir a qualidade.
- **Recall@k**: proporção de perguntas em que o trecho correto aparece entre os k primeiros resultados.
- **MRR**: média do inverso da posição do primeiro trecho correto.
- **Fidelidade**: grau em que a resposta é sustentada pelo contexto recuperado.
- **Keycloak**: provedor de identidade usado pelo Nexus para autenticar usuários.
- **OIDC (OpenID Connect)**: protocolo de autenticação utilizado entre o Nexus e o Keycloak.
- **Papel**: função do usuário no Nexus — administrador, curador ou usuário.
- **Grupo**: conjunto de usuários no Keycloak, usado para definir quem acessa cada assistente e
  cada documento.
- **Curador**: responsável por manter os documentos e o conjunto de referência de um assistente.
- **Trilha de auditoria**: registro, que não pode ser alterado, de quem acessou, perguntou ou
  modificou a base.
- **Worker de ingestão**: processo que trata os documentos em segundo plano.
- **OCR**: reconhecimento de texto em imagens, usado para ler documentos digitalizados.
- **Injeção de prompt**: tentativa de fazer o assistente obedecer a instruções escondidas em um documento.
- **SDD (Spec-Driven Development)**: prática de aprovar a especificação antes de escrever o código.
- **Linha de base**: medida de qualidade registrada antes de uma mudança, usada como referência
  para comparar o resultado depois dela.
- **Tolerância de regressão**: queda máxima aceita em um indicador entre duas avaliações; acima
  dela a mudança é reprovada.
- **Log estruturado**: registro de eventos do sistema em formato padronizado, que permite filtrar
  por campos.
- **Identificador de requisição**: código único atribuído a cada chamada, usado para acompanhar
  uma pergunta por todas as etapas do processamento.
