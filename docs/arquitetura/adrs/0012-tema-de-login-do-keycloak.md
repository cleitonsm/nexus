# ADR 0012: Tema de login próprio e imagem derivada do Keycloak

## Status

Aceita em 2026-10-25, com a aprovação da SPEC-011. Implementação pendente. Complementa a
[ADR 0008](0008-keycloak-e-modelo-de-permissoes.md).

## Contexto

O Keycloak (ADR 0008) é a única porta de entrada do Nexus, mas usa o tema padrão `keycloak.v2`,
claro e com outra identidade visual. O usuário troca de aparência ao entrar e ao sair. O serviço
roda com a imagem oficial e só recebe o arquivo do realm, sem lugar para um tema.

## Decisão

1. Criar o tema `nexus`, tipo `login`, com `parent=keycloak.v2`, versionado em
   `infra/keycloak/themes/nexus/`. A aparência vem de uma folha de estilos própria somada às do
   pai; templates FreeMarker do pai só são sobrescritos quando o CSS não basta, e cada
   sobrescrita é registrada na SPEC que a pedir.
2. Distribuir o tema numa imagem derivada da oficial (`infra/docker/keycloak.Dockerfile`, com
   `kc.sh build`), construída pelo `compose.yaml` e reutilizável fora do ambiente local.
3. Definir `loginTheme: nexus` no realm de desenvolvimento.
4. Reproduzir os tokens visuais do `tailwind.config.js` como variáveis CSS do tema, com os mesmos
   nomes, sem dependência de build entre frontend e Keycloak.

## Consequências

- O login tem o mesmo padrão visual do frontend, e os ids do formulário (`username`, `password`,
  `kc-login`) continuam os do Keycloak, preservando o e2e.
- O Keycloak deixa de ser uma imagem pronta: o `docker compose up --build` ganha uma etapa, e cada
  ajuste no tema exige reconstruir o serviço.
- Todo upgrade da imagem base exige repassar a verificação visual e o e2e do login, porque o tema
  depende do HTML e das variáveis do PatternFly do pai.
- Os tokens visuais ficam em dois lugares (Tailwind e CSS do tema); mudar a paleta exige alterar
  os dois.
- Realms já importados precisam receber `loginTheme` pelo console ou por `kcadm.sh`.

## Alternativas Consideradas

- **Herdar `base` e reescrever os templates com o CSS do Tailwind:** controle total, mas cada
  upgrade do Keycloak exige revisar o FreeMarker; descartada por custo de manutenção.
- **Keycloakify:** temas em React empacotados como JAR; descartada por acrescentar uma toolchain
  React a um projeto Angular para uma única tela.
- **Volume com o tema na imagem oficial:** iteração mais rápida no desenvolvimento, mas exige
  replicar a montagem em cada ambiente e não permite `kc.sh build`; descartada em favor de um
  artefato único.
