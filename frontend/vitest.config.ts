import { defineConfig } from 'vitest/config';

// FE-01: specs de lógica pura, reducers, effects e pipes rodam no Node. O setup
// carrega o compilador JIT do Angular, exigido por qualquer arquivo que importe
// decorators (@Injectable, @Pipe). Componentes com TestBed ficam para o E2E (V-D3).
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.spec.ts'],
    setupFiles: ['src/test-setup.ts'],
    restoreMocks: true,
    reporters: ['default'],
  },
});
