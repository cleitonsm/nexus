# Escopo do MVP

## Dentro do Escopo

- Cadastro simples de assistentes.
- Upload de documentos para um assistente específico.
- Extração, chunking, embedding local e indexação em Qdrant.
- Chat com recuperação de contexto por assistente.
- Histórico de conversas persistido em PostgreSQL.
- Interface web para selecionar assistente, enviar documentos e conversar.
- Execução local via Docker.

## Fora do Escopo Inicial

- Autenticação corporativa e controle granular de permissões.
- Multi-tenant completo.
- Painéis analíticos de uso.
- Curadoria humana avançada e aprovação formal de respostas.
- Fine-tuning de modelos.
- Deploy em nuvem ou infraestrutura produtiva.

## Critérios de Aceite

- Dois assistentes com documentos diferentes não misturam resultados de busca.
- Uma pergunta respondida pelo chat deve usar conteúdo recuperado do assistente ativo.
- O histórico de uma conversa deve permanecer disponível após reiniciar a API.
- O ambiente deve subir localmente com Docker sem instalar dependências de backend ou frontend
  na máquina host.
