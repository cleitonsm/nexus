# Validação manual: evolução RAG Enterprise

## Objetivo

Validar ponta a ponta, pela interface, as funcionalidades da evolução RAG Enterprise. O roteiro é
organizado por fase e cada bloco só se aplica **depois** da implementação da fase correspondente.
Em 2026-10-07 apenas o bloco da Fase 1 pode ser executado; as demais funcionalidades ainda não
existem.

## Pré-condições

- Ambiente completo em execução, incluindo Keycloak e worker (a partir das fases 4 e 5).
- Realm de desenvolvimento importado, com os usuários fictícios (senha `nexus-dev`): `admin.nexus`
  (administrador), `curadora.rh` (curadora, grupo `rh`), `usuario.rh` (usuário, grupo `rh`),
  `usuario.financeiro` (usuário, grupo `financeiro`) e `diretora` (usuária, grupos `rh` e `diretoria`).
- Só o administrador cria assistentes e define os grupos (RN-21); a curadora envia e gerencia os
  documentos dos assistentes dos grupos dela. Crie o assistente "RH" (passo 16) antes de enviar
  documentos como curadora.
- Chave do LLM configurada.
- Documentos de teste fictícios ou públicos: um manual com seções e tabela, um PDF digitalizado e
  um documento contendo um código exato (por exemplo, "NR-35").

## Fase 1 — Avaliação

1. Execute `scripts\eval.ps1 nexus-docs` (PowerShell) ou `scripts/eval.sh nexus-docs` (bash).
2. Confirme que o relatório apresenta recall@5, MRR, fidelidade e fallback correto.
3. Confirme que o relatório identifica commit, modelos e parâmetros.
4. Envie uma pergunta pelo chat, leia o cabeçalho `X-Request-ID` da resposta e localize, em
   `docker compose logs backend`, todas as linhas com esse `request_id`.
5. Confirme que todas as linhas do backend são JSON e que nenhuma contém a chave do LLM.

## Fase 2 — Recuperação semântica

6. Envie o manual de teste e aguarde a indexação.
7. Faça uma pergunta usando palavras diferentes das do documento e confirme que a resposta é correta.
8. Solicite a reindexação do assistente e, durante o processo, confirme que o chat continua respondendo.
9. Execute a avaliação e compare o recall@5 com a linha de base.

## Fase 3 — Busca híbrida, reranking e citações

10. Pergunte pelo código exato presente no documento e confirme que o trecho correto é usado.
11. Confirme que a resposta exibe as fontes com documento, seção e página.
12. Clique em uma fonte e confirme a exibição do trecho citado.
13. Faça uma pergunta de continuação que dependa da anterior e confirme que a resposta mantém o assunto.
14. Faça uma pergunta sem relação com os documentos e confirme o fallback explícito.

## Fase 4 — Autenticação e controle de acesso

15. Acesse o frontend sem sessão e confirme o redirecionamento para o Keycloak.
16. Entre como `admin.nexus`, crie o assistente "RH" e vincule-o ao grupo `rh`.
17. Entre como `usuario.financeiro` e confirme que o assistente "RH" não aparece.
18. Entre como `curadora.rh`, envie um documento ao assistente "RH" e restrinja-o ao grupo `diretoria`.
19. Entre como `usuario.rh`, faça uma pergunta respondida apenas por esse documento e confirme o fallback.
20. Entre como `usuario.rh`, crie uma conversa; entre como `curadora.rh` e confirme que a conversa não é visível.
21. Entre como `usuario.rh` e confirme que a tela de administração não está disponível.
22. Entre como `admin.nexus` e confirme, na auditoria, os eventos dos passos anteriores.

## Fase 5 — Ingestão e ciclo de vida

23. Como `curadora.rh`, envie um arquivo grande e confirme a resposta imediata com estado "pendente".
24. Acompanhe a mudança para "processando" e "indexado" sem recarregar a página.
25. Envie o mesmo arquivo novamente e confirme o aviso de duplicidade.
26. Envie o PDF digitalizado e confirme que chega ao estado "indexado".
27. Substitua um documento por nova versão e confirme que as respostas passam a refletir o novo conteúdo.
28. Exclua um documento e confirme que perguntas sobre ele resultam em fallback.
29. Abra uma conversa antiga que citava o documento excluído e confirme a marcação de documento removido.
30. Reinicie o serviço `worker` durante um processamento e confirme a conclusão sem duplicidade.

## Fase 6 — Operação e governança

31. Envie uma pergunta e confirme que a resposta aparece progressivamente.
32. Avalie uma resposta como "não útil" com comentário e, como `curadora.rh`, confirme que ela aparece para revisão.
33. Localize o rastreamento da resposta pelo identificador e confira a duração de cada etapa.
34. Como `admin.nexus`, consulte o consumo e o custo estimado por conversa.
35. Exceda o limite de uso e confirme a mensagem com o momento em que será possível perguntar de novo.
36. Indexe um documento com uma instrução maliciosa e confirme que o assistente não a segue.
37. Execute o backup, recrie o ambiente do zero, execute a restauração e repita os passos 7 e 11.

## SPEC-016 — Acesso rápido a assistentes na tela inicial (CT-130)

Pré-condição: `usuario.rh` com acesso a pelo menos cinco assistentes (vincule o grupo `rh` como
`admin.nexus`) e sem acesso rápido gravado. Faça as capturas a 1280 px e a 360 px.

38. Entre como `usuario.rh` e confirme quatro cartões na tela inicial, o primeiro marcado (anel e ✓)
    e com o selo "Padrão".
39. Clique em "Personalizar acesso rápido": o contador mostra "4 de 4" e o quinto assistente fica
    desabilitado. Navegue pelo modal só com o teclado (Tab, espaço, Esc).
40. Desmarque dois, marque o quinto, escolha-o como padrão e salve. Confirme o padrão em primeiro,
    marcado e com o selo, e os outros na ordem em que foram marcados.
41. Recarregue a página e entre em outro navegador: a escolha e o padrão marcado se mantêm.
42. Selecione outro cartão e clique em "Nova conversa": o padrão volta a ser o assistente ativo.
43. Entre como `usuario.financeiro` e confirme que ele não vê a escolha de `usuario.rh`.
44. Como `admin.nexus`, retire o grupo `rh` do assistente padrão de `usuario.rh`; como
    `usuario.rh`, confirme que ele sumiu do acesso rápido e que o próximo virou o padrão.
45. A 360 px, confirme que os cartões e o modal cabem na tela sem rolagem horizontal.

## SPEC-017 — Edição de nome, descrição e prompt do assistente (CT-138)

Pré-condição: um assistente de teste com o grupo `rh`, documentos indexados e prompt preenchido, e
outro sem grupo. Anote o prompt original para restaurá-lo no fim. Faça as capturas a 1280 px e a
360 px.

46. Como `admin.nexus`, abra "Documentos e permissões" com o assistente de teste ativo: o card
    "Dados do assistente" aparece no topo, com os valores atuais e os contadores "n / 80", "n / 500"
    e "n / 4000". "Salvar" e "Descartar" ficam desabilitados.
47. Altere o nome e confirme que "Salvar" é habilitado. Clique em "Descartar": os valores voltam e os
    botões são desabilitados de novo.
48. Digite o nome de outro assistente existente: aparece o aviso de nome repetido, sem bloquear.
49. Apague o prompt: aparece "Sem prompt, o assistente usa a instrução padrão do sistema." Cole um
    texto com mais de 4000 caracteres: o contador fica vermelho e "Salvar" é desabilitado.
50. Grave um nome e um prompt novos ("Responda em tópicos."). Sem recarregar, o nome novo aparece na
    barra lateral, no título da página e, na tela inicial, no cartão do acesso rápido.
51. Abra uma conversa já existente com o assistente e faça uma pergunta: a resposta segue o prompt
    novo e ainda traz as citações `[n]`. As respostas anteriores não mudam.
52. Em `/admin/audit`, confirme o evento "Assistente alterado" com os campos alterados, o nome antes e
    depois, e o tamanho e o hash do prompt, sem o texto dele.
53. Como `curadora.rh`, confirme o card no assistente de teste e a sua ausência no assistente sem
    grupo; salve uma alteração da descrição e confirme o evento com a curadora como autora.
54. Como `usuario.rh`, confirme que `/assistants` leva ao chat, que a escolha automática de assistente
    continua funcionando e que a lista de assistentes (`GET /api/assistants`, pelas ferramentas do
    navegador) traz `initial_prompt` nulo.
55. Navegue pelo card só com o teclado (Tab até os campos e os botões). A 360 px, confirme que o card
    cabe na tela sem rolagem horizontal. Restaure o prompt original.

## Resultado esperado

- Respostas fundamentadas exibem fontes; perguntas fora do escopo resultam em fallback.
- Nenhum usuário recebe conteúdo de assistente ou documento fora dos seus grupos.
- Documentos são processados em segundo plano e podem ser excluídos e substituídos.
- Cada resposta é rastreável e seu custo estimado é consultável.
- Chaves, tokens e conteúdo integral de documentos não aparecem em logs nem em rastreamentos.
- Cada usuário vê na tela inicial o próprio acesso rápido, com o padrão sempre marcado (SPEC-016).
- Administrador e curador do assistente alteram nome, descrição e prompt sem perder grupos,
  documentos nem índice; o prompt novo vale na próxima pergunta e não aparece para o usuário comum
  (SPEC-017).
