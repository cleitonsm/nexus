# Troubleshooting

## Porta em Uso

Verifique se outro processo já usa as portas `4200`, `8000`, `5432` ou `6333`.

## Containers sem Comunicação

Confirme se os serviços usam nomes internos do Docker Compose, como `postgres` e `qdrant`, em
vez de `localhost` dentro dos containers.

## Embeddings Lentos

Modelos locais podem exigir mais CPU e memória. Para o MVP, prefira um modelo pequeno antes de
otimizar qualidade.

## Respostas sem Contexto

Verifique se o documento foi indexado na collection correta e se a pergunta está sendo executada
com o `assistant_id` esperado.
