# Keycloak do Nexus com o tema de login proprio (SPEC-011, ADR 0012).
# Mesma versao fixada antes no compose.yaml; o tema fica dentro da imagem.

FROM quay.io/keycloak/keycloak:26.0 AS builder

# Opcoes de build usadas pelo "start --optimized" fora do ambiente local. O
# "start-dev" do compose.yaml ignora a otimizacao e funciona igual.
ENV KC_DB=postgres
ENV KC_HEALTH_ENABLED=true

COPY --chown=keycloak:keycloak infra/keycloak/themes/nexus /opt/keycloak/themes/nexus
RUN /opt/keycloak/bin/kc.sh build

FROM quay.io/keycloak/keycloak:26.0

COPY --from=builder /opt/keycloak/ /opt/keycloak/
