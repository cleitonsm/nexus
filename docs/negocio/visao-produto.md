# Visão do Produto

## Contexto

Empresas acumulam conhecimento em documentos, manuais, políticas, atas, wikis e arquivos
operacionais. Mesmo quando esse conteúdo existe, encontrar a informação correta costuma ser
lento e depende de pessoas específicas.

O Nexus propõe uma camada conversacional sobre documentos oficiais. Cada assistente representa
uma área, projeto ou domínio de conhecimento e responde com base no material associado a ele.

## Proposta de Valor

- Reduzir o tempo para encontrar respostas confiáveis.
- Diminuir dependência de conhecimento informal ou disperso.
- Separar bases de conhecimento por assistente, evitando mistura entre contextos.
- Permitir evolução incremental para fluxos de curadoria, governança e auditoria.

## Resultado Esperado no MVP

O MVP deve demonstrar que um usuário consegue criar um assistente, alimentar sua base com
documentos e conversar com ele recebendo respostas ancoradas no conteúdo recuperado.

## Evolução RAG Enterprise

Com o MVP validado, a visão do produto avança de "demonstrar que funciona" para "poder ser adotado
por uma organização". A evolução acrescenta à proposta de valor os itens abaixo; o terceiro
(qualidade medida) já começou a ser entregue, e os demais estão planejados:

- **Respostas verificáveis**: cada resposta indica documento, seção e página de origem.
- **Conhecimento protegido**: cada pessoa acessa apenas os assistentes e documentos permitidos aos
  seus grupos, com login corporativo pelo Keycloak.
- **Qualidade medida**: a precisão das respostas é acompanhada por indicadores, não por impressão.
- **Base viva**: curadores atualizam, substituem e removem documentos sem interromper o uso.
- **Operação sustentável**: custo, desempenho e uso são visíveis, e há trilha de auditoria.

A evolução realiza o que a proposta de valor original já antecipava como "fluxos de curadoria,
governança e auditoria". A privacidade dos documentos na vetorização é preservada: embeddings
continuam locais.

### Resultado Esperado da Evolução

Uma organização deve conseguir disponibilizar o Nexus a áreas diferentes, com a garantia de que
cada pessoa recebe respostas fundamentadas, com fontes, e apenas a partir do conteúdo que pode ver.

Detalhes em [`escopo-rag-enterprise.md`](escopo-rag-enterprise.md).
