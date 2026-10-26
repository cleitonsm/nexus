# Ponta a ponta (FE-07)

Playwright com o Chromium (V-D4a). `@playwright/test` é dependência de desenvolvimento do
`package.json`; o navegador é baixado à parte:

```powershell
cd frontend
npm install
npx playwright install chromium
npx playwright test
```

Com a pilha do Compose no ar e saudável (`docker compose up -d --build --wait`) e o realm de
desenvolvimento (usuários `admin.nexus`, `curadora.rh`, `usuario.rh`, `usuario.financeiro`, senha
`nexus-dev`). Variáveis: `NEXUS_URL` (padrão `http://localhost:4200`), `NEXUS_TEST_PASSWORD`,
`CHROMIUM_PATH`. Logo depois de recriar o `keycloak`, espere ele ficar saudável: com ele ainda
subindo, os primeiros testes estouram o tempo na página de login.

Automatizado aqui: **E1** (login por papel, rotas conforme o papel, logout), a parte do **FE-04**
que exige DOM real (sem script, `onerror` ou `javascript:` na resposta), a navegação da SPEC-010
e o tema de login da SPEC-011. **E2 a E11** seguem os roteiros manuais em `docs/qa`, com captura de
tela — o plano admite roteiro manual (V-D4b) para o que não foi automatizado.

| Arquivo | Casos | Situação |
|---------|-------|----------|
| `access.spec.ts` | E1, CT-32, CT-86 | Aprovado em 2026-10-26 na pilha local |
| `login-theme.spec.ts` | CT-87, CT-88, RNF-36 | Aprovado em 2026-10-26 na pilha local |
| `navigation.spec.ts` | CT-81 a CT-84 (SPEC-010) | Escrito, ainda não executado |
| `xss.spec.ts` | FE-04 | Escrito, ainda não executado |

Os seletores do Keycloak (`#username`, `#password`, `#kc-login`) vêm do tema `nexus` (SPEC-011,
herda os ids do `keycloak.v2`) e o botão `Sair` (atributo `title`) de `shell.component.html`.
O navegador do Playwright envia `Accept-Language: en-US`; os testes que dependem do idioma fixam
`locale` (ver `login-theme.spec.ts`).
