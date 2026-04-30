# Serviços

## Backend

API FastAPI responsável por expor casos de uso do Nexus e integrar persistência, RAG e LLM.

## Frontend

Aplicação Angular para criação de assistentes, upload de documentos e chat.

## PostgreSQL

Banco relacional para assistentes, documentos, conversas e mensagens.

## Qdrant

Vector store para chunks vetorizados. No MVP, cada assistente possui uma collection própria.

## LLM Provider

Adapter configurável para geração de respostas. A arquitetura deve permitir trocar provider sem
alterar casos de uso.

## Embedding Local

Componente responsável por transformar chunks em vetores usando modelo executado localmente.
