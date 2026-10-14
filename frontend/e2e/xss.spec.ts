/**
 * FE-04 (parte com DOM real) / RF-60: markup malicioso numa resposta nao
 * executa script nem navega por `javascript:`. O Angular real so sanitiza em
 * navegador; a especificacao com sanitizador simulado esta em
 * `src/app/shared/pipes/markdown.pipe.spec.ts`.
 *
 * O teste intercepta a resposta do chat e injeta o markup, sem depender do LLM.
 */
import { expect, test } from "@playwright/test";

import { login } from "./helpers";

const MALICIOUS =
  'Resposta <img src=x onerror="window.__xss=1"> <script>window.__xss=1</script> ' +
  "[clique](javascript:window.__xss=1)";

test("markup malicioso na resposta nao executa nem vira link perigoso", async ({ page }) => {
  await login(page, "admin.nexus");
  await page.addInitScript(() => {
    (window as unknown as { __xss?: number }).__xss = 0;
  });
  const message = {
    id: "m-xss",
    conversation_id: "c-xss",
    role: "assistant",
    content: MALICIOUS,
    created_at: new Date().toISOString(),
    citations: []
  };
  await page.route("**/api/conversations/*", (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({
      json: {
        id: "c-xss",
        assistant_id: "a",
        created_at: message.created_at,
        updated_at: message.created_at,
        messages: [message]
      }
    });
  });
  await page.goto("/chat");
  const html = await page.content();
  expect(html).not.toContain("<script>window.__xss");
  expect(html).not.toContain('onerror="window.__xss');
  expect(html).not.toContain('href="javascript:');
  expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBe(0);
});
