# Checklist manual do teste rapido (E1) - 2026-10-14, commit 4584080

Marque cada item e anote o que aconteceu quando falhar. Usuarios do realm: senha `nexus-dev`.

- [ ] Abrir http://localhost:4200 e entrar como `admin.nexus` (vai ao Keycloak e volta)
- [ ] Criar um assistente e vincular o grupo `rh` em "Assistentes"
- [ ] Entrar como `curadora.rh` e enviar um PDF com texto: Pendente -> Processando -> Indexado sem recarregar a pagina
- [ ] Enviar o mesmo arquivo de novo: aviso de duplicidade
- [ ] Entrar como `usuario.rh` e perguntar algo do documento: texto aparece em partes, com fontes [n] ao final
- [ ] Abrir uma fonte e conferir o trecho
- [ ] Marcar a resposta como "nao util" com comentario; como `curadora.rh`, ver em "Avaliacoes"
- [ ] Entrar como `usuario.financeiro`: o assistente de RH nao aparece
- [ ] Como `admin.nexus`, abrir "Consumo e limites" e "Auditoria"
- [ ] `docker compose restart` e conferir que a conversa continua la

Observacoes:

