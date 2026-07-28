# Requisitos Não Funcionais — Nexus

Notação: `RNF-XX` — Requisito Não Funcional.
Categorias conforme ISO/IEC 25010 e material do curso.

---

## Desempenho

| ID     | Descrição |
|--------|-----------|
| RNF-01 | O sistema deve retornar os primeiros tokens da resposta do chat em até 30 segundos para 95% das requisições em condições normais de operação com LLM externo. |
| RNF-02 | A indexação de um documento de até 10 MB deve ser concluída em até 60 segundos. |
| RNF-03 | A busca vetorial deve retornar os `top-k` chunks em menos de 2 segundos para bases com até 100.000 vetores. |

## Segurança

| ID     | Descrição |
|--------|-----------|
| RNF-04 | A chave de API do provedor LLM deve ser armazenada criptografada no banco de dados usando cifra simétrica (Fernet). |
| RNF-05 | A chave de criptografia não deve ser armazenada no banco de dados; deve ser fornecida via variável de ambiente. |
| RNF-06 | O sistema não deve expor a chave de API do LLM em nenhuma resposta de API pública. |

## Isolamento de Dados

| ID     | Descrição |
|--------|-----------|
| RNF-07 | Cada assistente deve possuir uma collection independente no Qdrant; uma consulta de um assistente não deve acessar vetores de outro. |
| RNF-08 | A exclusão de um assistente deve remover a collection associada no Qdrant, garantindo que nenhum dado residual permaneça. |

## Portabilidade e Implantação

| ID     | Descrição |
|--------|-----------|
| RNF-09 | O ambiente completo (backend, frontend, banco de dados, vetor store) deve subir localmente com um único comando (`docker compose up`) sem instalar dependências na máquina host. |
| RNF-10 | O sistema deve ser compatível com provedores LLM que implementam a interface OpenAI Chat Completions (ex.: OpenAI, Gemini via proxy, LM Studio). |

## Manutenibilidade

| ID     | Descrição |
|--------|-----------|
| RNF-11 | O backend deve seguir Clean Architecture, separando domínio, aplicação, infraestrutura e API, de modo que a troca do provedor LLM, banco de dados ou vetor store exija alterações apenas na camada de infraestrutura. |
| RNF-12 | O frontend deve seguir o padrão NgRx com estado centralizado, garantindo que toda mutação de estado seja rastreável por ação/reducer. |

## Usabilidade

| ID     | Descrição |
|--------|-----------|
| RNF-13 | O sistema deve fornecer feedback visual (indicador de carregamento) para todas as operações assíncronas com duração superior a 500 ms. |
| RNF-14 | O sistema deve exibir mensagens de erro compreensíveis ao usuário para falhas de comunicação com o LLM ou com a API. |
| RNF-15 | A interface deve ser responsiva, funcionando adequadamente em telas com largura mínima de 360 px. |
