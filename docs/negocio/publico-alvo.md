# Público-Alvo

## Usuários Primários

- Colaboradores que precisam consultar procedimentos, políticas e documentos internos.
- Times de negócio que mantêm bases de conhecimento por área ou projeto.
- Gestores que desejam reduzir dependência de especialistas para dúvidas recorrentes.

## Usuários Administrativos

- Responsáveis por criar assistentes e definir seu escopo.
- Curadores de conhecimento que adicionam documentos e validam respostas.
- Equipes técnicas que operam a infraestrutura local e monitoram integrações.

## Recorte do MVP

O MVP prioriza usuários internos em um ambiente controlado. Autenticação corporativa,
permissões avançadas e auditoria detalhada ficam para ciclos posteriores.

## Evolução RAG Enterprise

A evolução **planejada** formaliza os perfis, que passam a ser papéis atribuídos no Keycloak.

| Perfil | Quem é | O que faz no Nexus |
|--------|--------|--------------------|
| Usuário | Colaborador que consulta procedimentos, políticas e documentos | Conversa com os assistentes dos seus grupos, consulta as fontes e avalia as respostas |
| Curador | Responsável pelo conhecimento de uma área | Envia, substitui, restringe e remove documentos; mantém o conjunto de referência; analisa respostas avaliadas como não úteis |
| Administrador | Responsável pela plataforma | Cria assistentes, define grupos com acesso, configura o LLM, consulta auditoria e consumo |
| Equipe técnica | Quem opera o ambiente | Executa a avaliação, acompanha rastreamentos e métricas, faz backup e restauração |

### Novas Partes Interessadas

- **Segurança da informação e conformidade**: interessadas no controle de acesso, na trilha de
  auditoria e no destino dos dados enviados ao provedor de LLM.
- **Gestores das áreas**: decidem quais grupos acessam cada assistente e quais documentos são restritos.

### Recorte da Evolução

O que o MVP deixava para ciclos posteriores — autenticação corporativa, permissões e auditoria —
passa a fazer parte do escopo. Continuam fora: múltiplas organizações no mesmo ambiente e
integração com outros provedores de identidade.
