# SPEC-015 — Barra lateral no padrão visual do Gemini

**ID**: SPEC-20261028-015
**Status**: **Implementada** em 2026-10-28 — CT-120 e CT-121 aprovados (Vitest); CT-123 aprovado pelo autor no navegador; CT-122 (E2E) ajustado, execução pendente. Histórico: **Aprovada** em 2026-10-28 — pedido do autor (Cleiton Medeiros); D1 a D6 propostas pela IA a partir das capturas do Gemini.
**Origem**: pedido do autor (2026-10-28): ícones parecidos com os do Gemini, barra recolhida com a
mesma espessura, tooltip com o nome do menu na barra recolhida, logo "N" na barra recolhida que
vira o ícone "Abrir barra lateral" ao passar o mouse, e logo com nome e botão "Fechar barra
lateral" na barra aberta.
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## Contexto e problema

1. A barra recolhida tem 80 px (`lg:w-20`) e o topo mostra um ícone de hambúrguer, sem a marca do
   Nexus.
2. Os ícones têm traço 2 e desenhos heterogêneos; o botão "Nova conversa" é uma pílula com fundo,
   desalinhada dos demais ícones ao recolher.
3. Na barra recolhida só há o atributo `title` nativo (Administração, Sair) ou nada (Nova
   conversa): não há tooltip no padrão visual.

## Decisões

| # | Escolha |
|---|---------|
| D1 | Barra recolhida com **72 px** (medida das capturas do Gemini: ícones centralizados a 36 px da borda). A aberta continua com 280 px. |
| D2 | Ícones em **traço fino** (1,75), cantos arredondados, 20 px, no estilo dos ícones do Gemini: Nova conversa = lápis sobre quadro; Assistentes = grade de quatro quadrados; Recentes = relógio; Administração = engrenagem; Sair = porta com seta; abrir/fechar barra = painel com coluna lateral. Ficam num componente único `nexus-icon`. |
| D3 | Cada item ocupa uma linha de 40 px com o ícone numa caixa fixa de 40 px; o ícone **não muda de posição** ao abrir ou recolher a barra. "Nova conversa" deixa de ser pílula com fundo e vira um item como os outros. |
| D4 | Na barra recolhida aparecem **Nova conversa, Assistentes, Recentes, Administração e Sair**. Clicar em Assistentes ou Recentes abre a barra com a seção expandida. |
| D5 | Tooltip em pílula clara (fundo `slate-200`, texto escuro), à direita do ícone, ao passar o mouse ou focar pelo teclado; some ao sair, ao clicar ou ao abrir a barra. Implementado com CDK Overlay (já instalado), para não ser cortado pela barra. |
| D6 | Topo: recolhida, mostra a logo "N"; com o mouse em cima (ou foco), a logo dá lugar ao ícone de abrir barra, com tooltip "Abrir barra lateral". Aberta, mostra a logo com o nome "Nexus" e, no canto direito, o botão de fechar com tooltip "Fechar barra lateral". No celular o hambúrguer do cabeçalho continua abrindo a barra, e o botão de fechar a fecha. |

## Requisitos funcionais

- RF-100: a barra recolhida tem 72 px e mostra os itens de D4 com os ícones de D2, alinhados como em D3.
- RF-101: na barra recolhida, cada item mostra tooltip com o nome do menu (D5); na barra aberta os itens não mostram tooltip.
- RF-102: o topo da barra segue D6, com nomes acessíveis "Abrir barra lateral" e "Fechar barra lateral".

## Critérios de aceite

```gherkin
Cenário: barra recolhida (RF-100, RF-101)
  Dado a barra lateral recolhida no desktop
  Então ela tem 72 px de largura e mostra a logo "N"
  Quando passo o mouse sobre "Nova conversa"
  Então vejo o tooltip "Nova conversa" à direita do ícone

Cenário: abrir pela logo (RF-102)
  Dado a barra recolhida
  Quando passo o mouse sobre a logo
  Então ela vira o ícone de abrir barra com o tooltip "Abrir barra lateral"
  Quando clico
  Então a barra abre com a logo, o nome "Nexus" e o botão "Fechar barra lateral" à direita

Cenário: barra aberta não mostra tooltip nos itens (RF-101)
  Dado a barra aberta
  Quando passo o mouse sobre "Nova conversa"
  Então nenhum tooltip aparece
```

## Design da solução

- `shared/icons/nexus-icon.component.ts`: componente standalone `nexus-icon` com entrada `name`
  e `size`; também desenha a logo (`name="logo"`, a mesma do `favicon.svg`).
- `shared/tooltip/tooltip.directive.ts`: diretiva `[nexusTooltip]` com `nexusTooltipDisabled`;
  posições e regras puras em `shared/tooltip/tooltip.ts`.
- `shell/sidebar.ts`: rótulos do topo e regra de quando o tooltip de item fica ativo.
- `ShellComponent`: método `openSection` (D4). Sem mudança no store.

## Impacto arquitetural

Somente frontend. Nenhuma dependência, action, rota ou contrato de API novo.

## Estratégia de testes

| ID | Verifica | Nível |
|----|----------|-------|
| CT-120 | Rótulos do topo e tooltip ativo só com a barra recolhida (RF-101, RF-102) | Vitest |
| CT-121 | Posições do tooltip: direita, com alternativa abaixo | Vitest |
| CT-122 | E2E de navegação usa "Abrir barra lateral" e encontra os itens recolhidos | E2E (Playwright) |
| CT-123 | Visual: largura de 72 px, troca da logo no hover, tooltips | Manual (navegador) |

## Riscos

- Telas menores que 1024 px continuam com a barra sobreposta de 280 px; o comportamento
  recolhido só existe no desktop, como hoje.
