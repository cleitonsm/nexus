# Validação manual: evolução RAG Enterprise

## Objetivo

Validar ponta a ponta, pela interface, as funcionalidades da evolução RAG Enterprise. O roteiro é
organizado por fase e cada bloco só se aplica **depois** da implementação da fase correspondente.
Em 2026-10-07 apenas o bloco da Fase 1 pode ser executado; as demais funcionalidades ainda não
existem.

## Pré-condições

- Ambiente completo em execução, incluindo Keycloak e worker (a partir das fases 4 e 5).
- Realm de desenvolvimento importado, com os usuários fictícios: `ana` (administradora), `carlos`
  (curador, grupo `rh`), `bia` (usuária, grupo `rh`) e `davi` (usuário, grupo `financeiro`).
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
16. Entre como `ana`, crie o assistente "RH" e vincule-o ao grupo `rh`.
17. Entre como `davi` e confirme que o assistente "RH" não aparece.
18. Entre como `carlos`, envie um documento ao assistente "RH" e restrinja-o ao grupo `diretoria`.
19. Entre como `bia`, faça uma pergunta respondida apenas por esse documento e confirme o fallback.
20. Entre como `bia`, crie uma conversa; entre como `carlos` e confirme que a conversa não é visível.
21. Entre como `bia` e confirme que a tela de administração não está disponível.
22. Entre como `ana` e confirme, na auditoria, os eventos dos passos anteriores.

## Fase 5 — Ingestão e ciclo de vida

23. Como `carlos`, envie um arquivo grande e confirme a resposta imediata com estado "pendente".
24. Acompanhe a mudança para "processando" e "indexado" sem recarregar a página.
25. Envie o mesmo arquivo novamente e confirme o aviso de duplicidade.
26. Envie o PDF digitalizado e confirme que chega ao estado "indexado".
27. Substitua um documento por nova versão e confirme que as respostas passam a refletir o novo conteúdo.
28. Exclua um documento e confirme que perguntas sobre ele resultam em fallback.
29. Abra uma conversa antiga que citava o documento excluído e confirme a marcação de documento removido.
30. Reinicie o serviço `worker` durante um processamento e confirme a conclusão sem duplicidade.

## Fase 6 — Operação e governança

31. Envie uma pergunta e confirme que a resposta aparece progressivamente.
32. Avalie uma resposta como "não útil" com comentário e, como `carlos`, confirme que ela aparece para revisão.
33. Localize o rastreamento da resposta pelo identificador e confira a duração de cada etapa.
34. Como `ana`, consulte o consumo e o custo estimado por conversa.
35. Exceda o limite de uso e confirme a mensagem com o momento em que será possível perguntar de novo.
36. Indexe um documento com uma instrução maliciosa e confirme que o assistente não a segue.
37. Execute o backup, recrie o ambiente do zero, execute a restauração e repita os passos 7 e 11.

## Resultado esperado

- Respostas fundamentadas exibem fontes; perguntas fora do escopo resultam em fallback.
- Nenhum usuário recebe conteúdo de assistente ou documento fora dos seus grupos.
- Documentos são processados em segundo plano e podem ser excluídos e substituídos.
- Cada resposta é rastreável e seu custo estimado é consultável.
- Chaves, tokens e conteúdo integral de documentos não aparecem em logs nem em rastreamentos.
