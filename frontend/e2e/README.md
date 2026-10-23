# Ponta a ponta (FE-07)

Playwright com o Chromium (V-D4a). A dependência é de desenvolvimento e **ainda não está no
`package.json`** (o `package-lock.json` precisa ser atualizado onde há acesso ao registro npm):

```powershell
cd frontend
npm install --save-dev @playwright/test
npx playwright test            # usa o Chromium baixado: npx playwright install chromium
```

Com a pilha do Compose no ar (`docker compose up -d`) e o realm de desenvolvimento
(usuários `admin.nexus`, `curadora.rh`, `usuario.rh`, `usuario.financeiro`, senha `nexus-dev`).
Variáveis: `NEXUS_URL` (padrão `http://localhost:4200`), `NEXUS_TEST_PASSWORD`, `CHROMIUM_PATH`.

Automatizado aqui: **E1** (login por papel, rotas conforme o papel, logout) e a parte do **FE-04**
que exige DOM real (sem script, `onerror` ou `javascript:` na resposta). **E2 a E11** seguem os
roteiros manuais em `docs/qa`, com captura de tela — o plano admite roteiro manual (V-D4b) para o
que não foi automatizado.

Status: escrito, **não executado** (sem navegador e sem registro npm onde foi escrito). Os seletores
do Keycloak (`#username`, `#password`, `#kc-login`) e o botão `Sair` (atributo `title`) vêm do tema
padrão e de `shell.component.html`; se algum falhar na primeira execução, ajuste em `helpers.ts`.
