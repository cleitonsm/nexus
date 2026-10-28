# SPEC-008 — Configuração do LLM na administração (provedor, modelo e URL)

**ID**: SPEC-20261014-008
**Status**: **Substituída** pela [SPEC-013](SPEC-013-chaves-de-llm-e-parametros-por-assistente.md) em 2026-10-28 — a chave global, o `llm_connection`, as rotas `/admin/api-key*` e `/admin/llm-settings` e o modal saíram; a migração `0010` copiou a configuração para a credencial "Padrão" e a `0011` removeu as linhas antigas. Antes: **Implementada** em 2026-10-25 — validada na campanha final (`validacao-final-rc8` e `rc9`; [RESUMO](../../qa/relatorios/2026-10-24-rc8/RESUMO-validacao-final.md)). Histórico: Aprovada em 2026-10-14 (escopo, URL livre para administrador e aviso de avaliação escolhidos pelo autor); código entregue, validação no Docker pendente.
**Origem**: teste rápido no Docker (E1) — chave de teste do Gemini recusada com 401 porque o destino continuava sendo `api.openai.com`; a tela só gravava a chave
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## Contexto e problema

A tela de administração grava só a chave global do LLM (RF-47, ADR 0005). O endereço e o nome do
modelo vêm exclusivamente das variáveis `LLM_API_URL` e `LLM_MODEL` do `.env`. Quem informa uma chave
de outro provedor (por exemplo, Gemini) não vê para onde ela é enviada, o teste responde 502 com
401 do provedor errado e a correção exige editar o `.env` e recriar os serviços. Também não existe
como saber, pela tela, qual modelo está em uso.

## Decisões

| # | Escolha |
|---|---------|
| D1 | A tela permite escolher o **provedor** (`OpenAI`, `Gemini` ou `Personalizado`), informar o **modelo** (texto livre) e, em `Personalizado`, a **URL**. Nos dois primeiros a URL vem do provedor e não é editável. |
| D2 | A configuração fica em `app_settings` (chave `llm_connection`, JSON com `provider`, `model`, `api_url`); **sem migração**. Precedência: valor gravado pela tela; sem ele, o ambiente (`LLM_MODEL`, `LLM_API_URL`). |
| D3 | URL livre apenas para o administrador (RF-47). Regras: esquema `https` (`http` só com `APP_ENV=local`), sem usuário/senha, sem parâmetros de consulta e sem fragmento (para a chave nunca ser colocada na URL). |
| D4 | A chave continua separada (ADR 0005) e **não é associada ao provedor**: trocar o provedor mantém a chave gravada; a tela avisa para salvar a chave do novo provedor. |
| D5 | Trocar o modelo ou o provedor não bloqueia nada. O relatório de avaliação já registra o modelo (SPEC-001); a tela avisa que a troca invalida a comparação com a linha de base. |
| D6 | O preço por 1K tokens continua vindo de `LLM_PRICE_*` (fora do escopo); o modelo gravado passa a ser o rótulo do consumo, e a tela avisa que o custo estimado usa os preços do ambiente. |
| D7 | Presets de URL: `OpenAI` = `https://api.openai.com/v1/chat/completions`; `Gemini` = `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` (endpoint de compatibilidade com o formato OpenAI). |

## Requisitos funcionais

- RF-68: o administrador consulta a configuração efetiva do LLM (provedor, modelo, URL, se a chave está configurada e se o valor vem da tela ou do ambiente).
- RF-69: o administrador altera provedor, modelo e URL; a mudança vale a partir da próxima pergunta e do próximo teste, sem reiniciar serviços. Valores inválidos respondem 422 e nada é gravado.
- RF-70: chat (incluindo streaming), teste da chave, registro de consumo e comando de avaliação usam a mesma configuração efetiva.
- RF-71: a alteração gera evento de auditoria com o valor anterior e o novo (provedor, modelo e URL), nunca a chave; quem não é administrador recebe 403 e a tentativa é auditada.
- RF-72: a tela de administração mostra os campos, a origem do valor, o aviso de chave por provedor (D4), o aviso de avaliação (D5) e o aviso de preços (D6).

## Critérios de aceite

```gherkin
Cenário: Gemini pela tela (RF-69, RF-70)
  Dado a chave do Gemini gravada e o ambiente apontando para a OpenAI
  Quando o administrador escolhe "Gemini" e informa o modelo
  Então o teste da chave e o chat passam a chamar o endpoint do Gemini com esse modelo

Cenário: sem configuração gravada (RF-68)
  Dado que nada foi gravado pela tela
  Quando o administrador consulta a configuração
  Então vê os valores do ambiente com a origem "ambiente"

Cenário: URL insegura ou com chave (RF-69, D3)
  Quando a URL personalizada usa http fora do ambiente local, tem usuário/senha, parâmetros ou fragmento
  Então a resposta é 422 e a configuração anterior é mantida

Cenário: modelo inválido (RF-69)
  Quando o modelo é vazio, tem espaços ou passa de 200 caracteres
  Então a resposta é 422

Cenário: não administrador (RF-71)
  Quando um curador ou usuário tenta consultar ou alterar
  Então a resposta é 403 e a tentativa é auditada

Cenário: auditoria (RF-71)
  Quando o administrador troca de OpenAI para Gemini
  Então o evento "llm_settings.changed" guarda provedor, modelo e URL anteriores e novos, sem a chave
```

## Impacto arquitetural

Domínio: `LLMProvider`, `LLMConnection` (validação) e a porta `LLMConnectionRepository`. Aplicação:
`GetLLMConnectionUseCase`, `UpdateLLMConnectionUseCase` e `resolve_llm_connection` (gravado >
ambiente). Infraestrutura: `PostgresLLMConnectionRepository` em `app_settings`;
`composition.llm_connection_defaults()`. API: `GET` e `PUT /admin/llm-settings`; `dependencies.py`
passa a resolver a conexão por requisição; `POST /admin/api-key/test` usa a mesma resolução. CLI:
`evaluate` usa a mesma resolução. Frontend: formulário na tela de administração, com ações, efeito,
reducer e seletores NgRx. Auditoria: ação `llm_settings.changed`. Variáveis novas: nenhuma;
`LLM_MODEL` e `LLM_API_URL` passam a ser apenas o padrão.

## Estratégia de testes

| ID | Verifica | Nível |
|----|----------|-------|
| CT-63 | `LLMConnection` aceita presets e URL personalizada válida; recusa modelo vazio, com espaço ou longo, URL sem `https`, com usuário/senha, parâmetros ou fragmento | Unitário |
| CT-64 | Resolução: sem gravado devolve o ambiente (provedor inferido pela URL); com gravado, o gravado vence | Unitário |
| CT-65 | Consulta e alteração exigem administrador; negativa é auditada | Unitário |
| CT-66 | Alteração grava, audita anterior e novo sem a chave e vale na resolução seguinte | Unitário |
| CT-67 | Preset fixa a URL do provedor mesmo que o cliente envie outra; `http` só com ambiente local | Unitário |
| CT-68 | Rotas `GET` e `PUT /admin/llm-settings` (200, 422, 403) | Integração (Docker) |
| CT-69 | Reducer, seletores e formulário da tela (estado carregado, salvo, erro) | Vitest |
| CT-70 | Gemini real: teste da chave responde `ok` com a chave de teste do autor | Manual (campanha) |

## Riscos

- Trocar o provedor mantém a chave anterior (D4): ela seria enviada ao novo endereço até a chave ser trocada. Mitigação: aviso na tela, auditoria da troca e restrição ao administrador.
- URL personalizada aponta qualquer destino HTTPS. Aceito por D3, restrito ao administrador e auditado.
- O endpoint de compatibilidade do Gemini está em beta no provedor; o `stream_options` não é documentado separadamente. A validação real é o CT-70.
