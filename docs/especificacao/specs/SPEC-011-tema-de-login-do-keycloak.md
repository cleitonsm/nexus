# SPEC-011 — Tema de login do Keycloak no padrão visual do Nexus

**ID**: SPEC-20261025-011
**Status**: **Aprovada** em 2026-10-25 — decisões D1 a D9 escolhidas pelo autor; código entregue em 2026-10-25, validação no Docker e e2e pendentes.
**Origem**: pedido do autor para a tela de login ter o mesmo padrão de layout do Nexus
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## Contexto e problema

O realm `nexus` não define `loginTheme`, então o login usa o tema padrão do Keycloak 26.0
(`keycloak.v2`, PatternFly 5, fundo claro). O usuário sai do Nexus, escuro, com cartões
arredondados e botões em pílula, para uma tela com outra identidade e volta depois de entrar.
O cabeçalho mostra o `displayName` do realm, "Nexus (desenvolvimento)", em texto corrido.

O Keycloak roda com a imagem oficial `quay.io/keycloak/keycloak:26.0` e só monta o arquivo do
realm. Não há onde colocar um tema.

À parte, `shell.component.html` usa `bg-gemini-bg text-gemini-text`, classes que não existem no
`tailwind.config.js`. O fundo só aparece certo porque o `body` aplica `bg-nexus-bg`.

## Decisões

| # | Escolha |
|---|---------|
| D1 | Tema próprio `nexus`, tipo `login`, com `parent=keycloak.v2`. A aparência vem de uma folha de estilos própria somada às do pai. Template do pai só é sobrescrito se um critério de aceite não puder ser atendido por CSS, e cada sobrescrita é registrada nesta SPEC. |
| D2 | O cabeçalho mostra a marca **Nexus** como na barra lateral. No realm de desenvolvimento, "desenvolvimento" aparece como **selo** discreto ao lado da marca, vindo do `displayNameHtml` do realm. Realms de outros ambientes definem o próprio `displayNameHtml` (sem selo). |
| D3 | O tema é distribuído numa **imagem derivada** (`infra/docker/keycloak.Dockerfile`, `FROM quay.io/keycloak/keycloak:26.0`, `COPY` do tema e `kc.sh build`). O `compose.yaml` passa a construir essa imagem em vez de usar a oficial. |
| D4 | O realm importado passa a ter `"loginTheme": "nexus"`. Para realms já importados, o README traz o comando `kcadm.sh` que aplica o tema sem recriar o banco. |
| D5 | Mensagens revisadas em **pt-BR e inglês** (`messages_pt_BR.properties`, `messages_en.properties`), os dois idiomas do realm. |
| D6 | Um **símbolo da marca** (SVG simples, original) aparece à esquerda de "Nexus" no cabeçalho do login e serve de favicon do login e do frontend. |
| D7 | A decisão de tema próprio e imagem derivada fica na **ADR 0012**, separada da ADR 0008. |
| D8 | `shell.component.html` troca `bg-gemini-bg text-gemini-text` por `bg-nexus-bg text-nexus-text`. |
| D9 | Contraste (decidido pelo autor na implementação): os tokens do app não atingem o AA do RNF-35 — indigo-500 com texto branco dá 4,47:1 e a borda slate-700 sobre o cartão dá 1,72:1. No login, o botão primário usa **indigo-600** `#4f46e5` (6,29:1; hover indigo-700) e a borda dos campos usa **slate-500** `#64748b` (3,75:1). O app não muda nesta SPEC. |

### Padrão visual de referência

Valores tirados do código do frontend, para o tema reproduzir:

| Elemento | No Nexus | No tema |
|----------|----------|---------|
| Fundo da página | `bg-nexus-bg` | `#0f172a` |
| Cartão | `max-w-md rounded-3xl border border-slate-800 bg-slate-900 p-6` (`app.component.html`) | largura máxima 28rem, raio 1.5rem, fundo `#0f172a` (`slate-900`, a mesma cor da página), destacado pela borda `#1e293b` e por sombra, espaçamento 1.5rem |
| Marca | `text-xl font-medium tracking-tight` | idem, fonte do sistema (sem webfont) |
| Rótulo | `text-sm text-slate-300` | `#cbd5e1`, 0.875rem |
| Campo | `rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm focus:border-indigo-400` | raio 1rem, fundo `#020617`, borda `#64748b` (D9), foco `#818cf8` com anel |
| Botão primário | `rounded-full bg-indigo-500 px-5 py-2 text-sm font-medium text-white` | pílula `#4f46e5` (D9), texto branco |
| Texto secundário | `text-slate-400` | `#94a3b8` |
| Erro | `text-rose-400` | `#fb7185` |

Os tokens viram variáveis CSS (`--nexus-bg`, `--nexus-accent`, …) com os mesmos nomes do
`tailwind.config.js`, mapeadas para as variáveis do PatternFly 5 sempre que possível, para
depender menos de seletores internos do Keycloak.

### Telas cobertas

Com `registrationAllowed` e `resetPasswordAllowed` desligados e sem OTP configurado, o fluxo do
realm passa por: `login` (inclusive credencial inválida e conta bloqueada por força bruta),
`login-page-expired`, `logout-confirm`, `info` e `error`. Todas usam o `template.ftl` do `keycloak.v2` (as quatro últimas vêm do tema `base`, que o
`keycloak.v2` não redefine, mas importam o mesmo `template.ftl`), então a mesma folha de estilos
as cobre.

## Requisitos funcionais

- RF-79: as telas do Keycloak no realm `nexus` usam o tema `nexus`, com fundo, cartão, campos,
  botões e alertas no padrão visual do frontend (D1).
- RF-80: o cabeçalho do login mostra o símbolo e a marca Nexus; no realm de desenvolvimento,
  também o selo "desenvolvimento" (D2, D6).
- RF-81: os textos do login aparecem em pt-BR por padrão e em inglês quando o usuário escolhe
  `en` no seletor de idioma (D5).

## Requisitos não funcionais

- RNF-34: o formulário de login mantém os ids `username`, `password` e `kc-login`, dos quais
  dependem o e2e (`frontend/e2e/helpers.ts`) e leitores de tela.
- RNF-35: contraste mínimo WCAG 2.1 AA (4,5:1 em texto, 3:1 em bordas de campo e foco) e foco
  visível pelo teclado em todos os controles.
- RNF-36: a tela funciona de 360 px de largura até desktop, sem rolagem horizontal.
- Nenhuma dependência nova no frontend, no backend nem no realm além do tema; nenhum recurso
  carregado de fora da imagem (sem CDN nem webfont).

## Critérios de aceite

```gherkin
Cenário: aparência do login (RF-79, RF-80)
  Dado o realm de desenvolvimento importado
  Quando um usuário abre o Nexus sem sessão
  Então o Keycloak mostra o fundo #0f172a, um cartão escuro arredondado, campos escuros e o botão Entrar em pílula indigo-600
  E o cabeçalho mostra o símbolo, "Nexus" e o selo "desenvolvimento"

Cenário: credencial inválida (RF-79)
  Dado a tela de login
  Quando o usuário informa uma senha errada
  Então a mensagem de erro aparece em rosa dentro do cartão, sem quebrar o layout

Cenário: idioma (RF-81)
  Dado a tela de login em pt-BR
  Quando o usuário escolhe English no seletor de idioma
  Então os rótulos, o botão e as mensagens aparecem em inglês, no mesmo layout

Cenário: e2e existente (RNF-34)
  Quando a suíte e2e do frontend roda contra a stack com o tema
  Então o login por #username, #password e #kc-login funciona como antes

Cenário: celular (RNF-36)
  Dado uma janela de 360 px de largura
  Então o cartão ocupa a largura com margem lateral e nada rola na horizontal

Cenário: teclado (RNF-35)
  Quando o usuário percorre a tela com Tab
  Então cada campo, o botão de mostrar senha, o seletor de idioma e o botão Entrar exibem foco visível

Cenário: realm sem selo (D2)
  Dado um realm cujo displayNameHtml não contém o selo
  Então o cabeçalho mostra só o símbolo e "Nexus"

Cenário: realm já importado (D4)
  Dado um ambiente cujo realm foi importado antes desta SPEC
  Quando o administrador roda o comando kcadm do README
  Então o login passa a usar o tema nexus sem recriar o banco
```

## Design da solução

**Estrutura do tema.**

```
infra/keycloak/themes/nexus/login/
├── theme.properties
├── resources/css/nexus.css
├── resources/img/nexus-mark.svg
├── resources/img/favicon.ico   (o template do pai referencia img/favicon.ico)
└── messages/
    ├── messages_pt_BR.properties
    └── messages_en.properties
```

- `theme.properties`: `parent=keycloak.v2`. A chave `styles` do filho substitui a do pai, então
  ela repete o `css/styles.css` do `keycloak.v2` (conferido na tag 26.0.17) e acrescenta
  `css/nexus.css` no fim; `stylesCommon` (PatternFly 5) e `meta` continuam herdados.
- `nexus.css`: variáveis da tabela acima; sobrescritas do fundo, do cartão, do cabeçalho (símbolo
  por `background-image` em pseudo-elemento), dos campos, do botão primário, dos alertas, do
  seletor de idioma e do botão de mostrar senha; regra para o selo (`.nexus-badge`).
- Favicon: o arquivo do filho com o mesmo caminho do pai substitui o original.

**Cabeçalho e selo (D2).** No `nexus-realm.json`:

```json
"displayName": "Nexus (desenvolvimento)",
"displayNameHtml": "<span class=\"nexus-brand\">Nexus</span> <span class=\"nexus-badge\">desenvolvimento</span>"
```

O `keycloak.v2` exibe o `displayNameHtml` no cabeçalho depois de passá-lo pelo sanitizador do
Keycloak (`KeycloakSanitizerPolicy`), que aceita `span` com `class` de letras, dígitos, hífen e
sublinhado: `nexus-brand` e `nexus-badge` passam. Se uma versão futura deixar de aceitar, a
alternativa é sobrescrever só o trecho do cabeçalho no `template.ftl` e ler o selo de uma
propriedade do tema.

**Mensagens (D5).** Só as chaves que mudam: título da página ("Entrar no Nexus" / "Sign in to
Nexus"), rótulo do usuário ("Usuário ou e-mail" / "Username or email"), botão ("Entrar" /
"Sign in") e as mensagens de credencial inválida e conta bloqueada. O restante vem do pai.

**Imagem derivada (D3).** `infra/docker/keycloak.Dockerfile`:

```dockerfile
FROM quay.io/keycloak/keycloak:26.0 AS builder
COPY infra/keycloak/themes/nexus /opt/keycloak/themes/nexus
RUN /opt/keycloak/bin/kc.sh build

FROM quay.io/keycloak/keycloak:26.0
COPY --from=builder /opt/keycloak/ /opt/keycloak/
```

No `compose.yaml`, o serviço `keycloak` troca `image:` por `build:` (contexto na raiz, como os
outros Dockerfiles do projeto) e mantém `start-dev --import-realm`, as variáveis e o volume do
realm. Mudança no tema exige `docker compose up -d --build keycloak`. Em produção a mesma imagem
sobe com `start --optimized`, fora do escopo desta SPEC.

**Símbolo (D6).** SVG original e geométrico em `#6366f1`, legível a 16 px, guardado no tema e
copiado para `frontend/public/` como favicon do app, com o `<link rel="icon">` em
`frontend/src/index.html`.

**Shell (D8).** Troca de duas classes na primeira linha de `shell.component.html`.

## Impacto arquitetural

Infraestrutura e apresentação: `infra/keycloak/themes/` (novo), `infra/docker/keycloak.Dockerfile`
(novo), `compose.yaml`, `infra/keycloak/nexus-realm.json`, `frontend/public/`,
`frontend/src/index.html` e `frontend/src/app/shell/shell.component.html`. Sem impacto no domínio,
nos casos de uso, na API, no banco, no Qdrant, na `AccessPolicy` nem no fluxo OIDC (PKCE, emissor,
audiência). Nova ADR 0012 (D7).

## Estratégia de testes

| ID | Verifica | Nível |
|----|----------|-------|
| CT-85 | A imagem derivada constrói e o Keycloak sobe saudável (healthcheck do Compose) com o tema listado em Realm settings → Themes | Manual (Docker) |
| CT-86 | Login, logout e acesso negado da suíte e2e existente passam com o tema (`helpers.ts`, `access.spec.ts`) | E2E (Playwright) |
| CT-87 | Novo `frontend/e2e/login-theme.spec.ts`: a página de login carrega `nexus.css`, o cabeçalho tem "Nexus" e o selo, o botão `#kc-login` tem `border-radius` de pílula e cor `rgb(99, 102, 241)` | E2E (Playwright) |
| CT-88 | Senha errada mostra o alerta dentro do cartão; troca para `en` mostra "Sign in" | E2E (Playwright) |
| CT-89 | Capturas a 360 px e 1280 px de `login`, erro de credencial, `logout-confirm` e `error`, comparadas lado a lado com a tela do Nexus; contraste conferido com ferramenta AA | Manual (visual) |
| CT-90 | Após D8, o fundo do shell continua `#0f172a` com o `body` sem classe de fundo | Manual (visual) |

## Riscos e dependências

- **Seletores do PatternFly mudam entre versões do Keycloak.** Mitigação: variáveis CSS do
  PatternFly primeiro, seletores próprios do Keycloak (`#kc-*`, `.kc*`) depois; a imagem continua
  fixada em `26.0`, e todo upgrade repassa o CT-87 e o CT-89.
- **Sanitização do `displayNameHtml`** pode remover o `class` do selo; a alternativa está no
  design.
- **Realms já importados** não recebem `loginTheme` nem `displayNameHtml` do JSON; o README traz
  os comandos `kcadm.sh` (`update realms/nexus -s loginTheme=nexus` e o `displayNameHtml`).
- **Tempo de build**: a imagem derivada acrescenta uma etapa ao `docker compose up --build`
  (o `kc.sh build` leva dezenas de segundos na primeira vez).
- **Iteração no tema** fica mais lenta que com volume, porque cada ajuste reconstrói a imagem.

## Decisões pendentes

Nenhuma.

## Documentação a atualizar

- `infra/keycloak/README.md`: seção "Tema de login" (onde fica, como editar e reconstruir, comandos
  para realm existente).
- `docs/infraestrutura/docker-local.md` e `docs/infraestrutura/servicos.md`: Keycloak passa a ser
  imagem construída.
- `docs/especificacao/specs/README.md`: linha da SPEC-011.
- `frontend/e2e/README.md`: menção ao tema `nexus` como origem dos seletores do login.

## Próximos passos (fora do escopo)

- Tema `account` e e-mails do Keycloak no mesmo padrão.
- Subida de produção com `start --optimized` e cache de tema ligado.

## Entrega (2026-10-25)

| Item | Situação |
|------|----------|
| Tema | `infra/keycloak/themes/nexus/login/`: `theme.properties`, `nexus.css`, `nexus-mark.svg`, `favicon.ico` e mensagens pt-BR e en; nenhum template sobrescrito (D1) |
| Imagem e realm | `infra/docker/keycloak.Dockerfile`; `compose.yaml` constrói a imagem; `nexus-realm.json` com `loginTheme` e `displayNameHtml`; o CI confere o tema |
| Frontend | D8 em `shell.component.html`; `favicon.svg` e `favicon.ico` em `frontend/public`, referenciados no `index.html` |
| Defeito encontrado na validação | O `index.html` não tinha `<base href="/">`: abrir uma rota com dois níveis (`/admin/audit`) carregava `/admin/main-*.js`, o Nginx devolvia o `index.html` e o app não iniciava. Isso fazia o CT-86 (`access.spec.ts`) falhar para curador, usuário e sem sessão. Corrigido com `<base href="/">` e favicons com caminho absoluto |
| CT-85 | Aprovado em 2026-10-26 na máquina do autor: imagem construída, Keycloak saudável, `loginTheme=nexus` no realm |
| CT-86 | Aprovado em 2026-10-26: `access.spec.ts` com 5 de 5, depois da correção do `base href` |
| CT-87 e RNF-36 | Aprovados em 2026-10-26 contra a pilha real |
| Ajustes após a pilha real | A imagem `keycloak:26.0` em uso difere da tag 26.0.17: o rótulo fica em `div.pf-v5-c-form__label` e o erro de credencial vai para `#input-error-password`. O CSS passou a cobrir as duas classes, zera as margens que o PatternFly dá ao botão (estava 8 px à direita dos campos), esconde o grupo "lembrar-me" e o rodapé vazios (só espaços ou comentário, então `:empty` não bastava) e afasta o rótulo do campo. Conferido sobre o HTML e o PatternFly servidos pela pilha real, extraídos do trace do Playwright. O CT-88 aceita o erro em qualquer dos dois campos |
| CT-88 (idioma) | O realm do ambiente do autor foi importado só com `pt-BR`; o seletor só aparece com dois idiomas. Comando para incluir `en` no `infra/keycloak/README.md` |
| CT-86 a CT-88 | `frontend/e2e/login-theme.spec.ts` (CT-87, CT-88 e RNF-36); `helpers.ts` não muda, porque os ids do formulário continuam os do `keycloak.v2` |
| CT-89 | Prévia: o HTML que o `keycloak.v2` 26.0.17 gera para `login`, credencial inválida, inglês, `logout-confirm` e `error`, com o `nexus.css`, renderizado no Chromium a 1280 px e 360 px, sem rolagem horizontal. Feita sem o CSS do PatternFly (registro npm inacessível), então a conferência na pilha real continua pendente |
| CT-90 | Pendente: depende do build do frontend (registro npm inacessível) |
| Contraste (RNF-35) | Medido: rótulos 12,0:1, texto secundário 7,0:1, erro 6,6:1, links 9,0:1, botão 6,3:1, borda dos campos 3,8:1, foco 6,8:1 |
