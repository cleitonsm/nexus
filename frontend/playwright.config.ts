import { defineConfig } from "@playwright/test";

// FE-07 (V-D4a): ponta a ponta com o Chromium. Dependencia de desenvolvimento
// `@playwright/test` (ver e2e/README.md); a pilha do Compose precisa estar no ar.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "../docs/qa/relatorios/e2e-html" }]],
  use: {
    baseURL: process.env["NEXUS_URL"] ?? "http://localhost:4200",
    screenshot: "on",
    trace: "retain-on-failure",
    launchOptions: { executablePath: process.env["CHROMIUM_PATH"] || undefined }
  }
});
