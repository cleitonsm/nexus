# ADR 0008: Keycloak como Provedor de Identidade e Modelo de Permissões

## Status

Aceita em 2026-10-07, com a aprovação da SPEC-004. Implementada; ainda não executada no ambiente
Docker. Complementa a [ADR 0003](0003-qdrant-por-assistente.md) e encerra a limitação
registrada na [ADR 0005](0005-api-key-global-criptografada.md).

## Contexto

O MVP não possui autenticação. A ADR 0005 aceitou esse risco apenas em rede controlada, e a gestão
de riscos (R5) definiu que qualquer uso além do ambiente local exige mitigação. Um RAG corporativo
precisa identificar o usuário, limitar o conhecimento acessível a cada um e registrar o uso.

## Decisão

1. Usar **sempre o Keycloak** como provedor de identidade, em todos os ambientes. O Nexus não
   armazena senhas nem mantém cadastro próprio de usuários.
2. Autenticar por OpenID Connect: Authorization Code com PKCE no frontend; a API valida o token de
   acesso (assinatura por JWKS, emissor, audiência e expiração).
3. Papéis de realm: `nexus-admin`, `nexus-curador` e `nexus-usuario`.
4. Controle de acesso em dois níveis:
   - **por assistente**, por vínculo entre assistente e grupos do Keycloak, com negação por padrão;
   - **por documento**, por grupos autorizados gravados no payload dos chunks e aplicados como
     filtro obrigatório na busca.
5. Manter a collection por assistente (ADR 0003) como fronteira de isolamento; o filtro de payload
   apenas restringe dentro do assistente.
6. Colocar as regras de acesso no domínio (`AccessPolicy`); a validação do token fica atrás da
   porta `TokenVerifier`.
7. Tornar cada conversa privada de quem a criou.
8. Registrar trilha de auditoria somente de inclusão.
9. Restringir ao administrador as rotas de configuração da chave do LLM.

## Consequências

- O ambiente Docker ganha o serviço `keycloak`, com realm de desenvolvimento importado na subida.
- Todos os casos de uso passam a receber o usuário autenticado.
- A limitação da ADR 0005 (endpoint administrativo sem autenticação) deixa de existir.
- Os dados do MVP precisam de migração: assistentes sem grupo ficam visíveis só a administradores
  e conversas antigas ficam sem dono.
- A indisponibilidade do Keycloak impede novos logins.
- Uma falha no filtro de acesso expõe conteúdo entre grupos; por isso há testes de integração
  recorrentes para esse comportamento.

## Alternativas Consideradas

- **Autenticação própria no Nexus:** descartada; implicaria armazenar senhas e reimplementar
  funções que o Keycloak já oferece.
- **Outros provedores de identidade:** descartados por decisão do projeto de padronizar no Keycloak.
- **Collection por grupo de acesso:** descartada por multiplicar collections e duplicar documentos
  compartilhados entre grupos.
- **Filtro de acesso aplicado após a busca:** descartado por reduzir a quantidade de resultados
  úteis e por depender de o código da aplicação nunca esquecer o filtro.
