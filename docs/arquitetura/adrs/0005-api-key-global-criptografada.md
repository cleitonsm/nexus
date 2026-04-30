# ADR 0005: API Key Global Criptografada no Backend

## Status

Aceita.

## Contexto

O MVP precisa consumir um provedor de LLM externo. Sem camada de autenticacao administrativa no
produto atual, expor ou trafegar o segredo por endpoints de leitura aumenta risco de vazamento.
Tambem precisamos manter rastreabilidade da configuracao sem armazenar a chave em texto puro.

## Decisão

Manter uma API key global do sistema, armazenada apenas em formato criptografado no PostgreSQL.

- A chave e salva no backend e nunca retornada por endpoint apos gravacao.
- A UI administrativa consulta apenas estado (`configurada`/`nao configurada`).
- A criptografia usa algoritmo simetrico autenticado via `cryptography` (Fernet).
- A chave-mestra vem da variavel de ambiente `NEXUS_SECRETS_KEY`.
- A descriptografia ocorre somente em memoria no momento da chamada ao gateway de LLM.

## Rotação e Operação

- A rotacao da API key do provedor ocorre por sobrescrita da configuracao global no endpoint
  administrativo.
- A rotacao da `NEXUS_SECRETS_KEY` exige recriptografar os segredos persistidos, pois ciphertext
  antigo nao sera mais legivel com a nova chave-mestra.
- Ambientes devem fornecer `NEXUS_SECRETS_KEY` via secret manager ou `.env` local nao versionado.

## Consequências

- Ganha-se reducao de risco por nao armazenar segredo em texto puro nem retornar valor pela API.
- Sem autenticacao administrativa nesta fase, o endpoint de configuracao deve ficar restrito ao
  ambiente controlado (rede interna/dev) ate a entrada de auth.
- O backend passa a depender de configuracao valida de `NEXUS_SECRETS_KEY`; sem ela, a gravacao e
  uso da API key devem falhar de forma explicita.
