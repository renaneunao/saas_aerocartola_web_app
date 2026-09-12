# TODO — Revisão da rodada, cruzamento, escalação e experiência mobile

Escopo solicitado em 12/09/2026. A implementação deve preservar as tabelas ACF e os registros existentes. A tabela `acw_player_availability`, quando necessária, deve ser criada/alterada somente de forma idempotente.

## Ordem de execução

### Dados, filtros e análise

- [x] **01 — Filtro inicial de prováveis no cruzamento**
  - Marcar inicialmente atletas prováveis (`status_id = 7`), incluindo regras `cravado` do usuário.
  - Excluir da lista inicial os atletas `poupar` e nulos (`status_id = 6`).
  - Manter a possibilidade de limpar/aplicar filtros sem alterar o banco ACF.

- [x] **02 — Histórico progressivo**
  - Exibir inicialmente somente as cinco rodadas mais recentes com dados.
  - Adicionar controle explícito “Mostrar mais”/“Mostrar histórico completo”.
  - Ao expandir, exibir todo o histórico no layout de três colunas já definido.

- [x] **03 — Confronto com escudos aceso/apagado**
  - Substituir o texto simples dos times no cruzamento pelo componente casa × fora.
  - Destacar o time do atleta e reduzir opacidade/grayscale do adversário.
  - Reutilizar o padrão visual das tabelas de posição, incluindo casa acima e fora abaixo.

- [x] **04 — Previsão calculada do jogador**
  - Reutilizar os cálculos/contratos JavaScript específicos de cada posição.
  - Mostrar a previsão na análise do jogador e identificar a posição usada.
  - Garantir que os pesos, scouts cedidos e mando usados sejam os da rodada atual.

- [x] **05 — Seleção de times sem rolagem**
  - Exibir os 20 clubes em duas linhas de 10.
  - Manter seleção por ícone, estado selecionado e adaptação para telas menores.
  - Remover a dependência da barra horizontal nesse filtro.

- [x] **06 — Análise comparativa em linha**
  - Transformar a área de jogadores em uma lista filtrável, sem exigir escolha prévia de nome.
  - Permitir filtros por time, posição, scout, média, expectativa e preço.
  - Expandir o jogador clicado no container inferior com foto, métricas, histórico, mando e cedidos.
  - Oferecer comparação com outro atleta da mesma posição.
  - Na comparação, destacar o melhor de cada métrica em verde e o pior em vermelho.

- [x] **07 — Texto intuitivo de rodada**
  - Substituir rótulos `R27`, `R28` etc. por `Rodada 27`, `Rodada 28` nas áreas solicitadas.
  - Preservar abreviações somente onde forem necessárias para uma tabela compacta.

### Escalação ideal

- [x] **08 — Linhas corretas no campinho**
  - Separar visualmente laterais e zagueiros.
  - Manter zagueiros no centro e laterais abertos nas formações que os utilizam.
  - Validar todas as formações suportadas sem sobreposição de cards.

- [x] **09 — Marcar “não joga” no card**
  - Disponibilizar a ação no hover/foco do jogador titular ou reserva.
  - Persistir a regra da rodada e recalcular imediatamente.
  - Remover o atleta poupado dos cálculos e das escolhas seguintes.

- [x] **10 — Auditoria mobile completa**
  - Revisar rankings, módulos, dashboard, perfis, disponibilidade, cruzamento e escalação.
  - Impedir empilhamento ilegível de células e overflow horizontal acidental.
  - Usar escalas compactas, tabelas roláveis quando necessário e controles tocáveis.

- [x] **11 — Rankings sem destaque cromático no top 3**
  - Remover fundos especiais das três primeiras linhas das tabelas de posição.
  - Trocar coroa/medalha/prêmio por números estilizados 1, 2 e 3.
  - Aplicar o mesmo padrão em todos os módulos.

- [x] **12 — Botões no padrão Aero**
  - Padronizar “Detalhes” nas páginas de posição.
  - Padronizar “Escalar todos os times” da sidebar.
  - Revisar estados hover, disabled, foco e versão mobile sem azul destoante.

- [x] **13 — Terminal de escalação em lote**
  - Recriar o painel de logs dentro do sistema visual Aero.
  - Mostrar apenas etapas úteis ao usuário, com status claro por time.
  - Corrigir percentual, contagem e progresso quando houver múltiplos times.
  - Preservar feedback de sucesso, falha e conclusão parcial.

- [x] **14 — Cards de jogadores da escalação**
  - Aumentar e arredondar as fotos.
  - Exibir preço e previsão em cards internos.
  - Exibir time e favoritismo como badges externas.
  - Para defesa, incluir percentual de chance de saldo usando os pesos SG do time.
  - Recalcular badges CAP/LUXO após troca de formação ou jogador.

### Dashboard, disponibilidade e composição geral

- [x] **15 — Dashboard com índices de confronto**
  - Mostrar abaixo de cada confronto o índice de saldo e o índice de favoritismo.
  - Usar os perfis de peso de jogo escolhidos pelo usuário e a rodada atual.
  - Identificar claramente qual índice pertence a casa e qual pertence a fora.

- [x] **16 — Dashboard coeso com as tabelas**
  - Auditar tabelas disponíveis e selecionar resumos úteis da rodada.
  - Corrigir o card de favorito para carregar e mostrar sua foto.
  - Manter intactos os cards de rankings, escalações e perfis já aprovados.

- [x] **17 — Filtros na disponibilidade**
  - Reutilizar filtros de posição, time, status e busca usados no cruzamento.
  - Iniciar mostrando prováveis, inclusive cravados pelo usuário.
  - Excluir nulos da ação de cravar e manter poupar/cravar por rodada e time.

- [x] **18 — Ocupação horizontal global**
  - Fazer as telas ocuparem toda a largura disponível após a sidebar.
  - Remover limites centrais excessivamente estreitos sem prejudicar leitura.
  - Validar desktop, tablet e celular em conjunto com a auditoria do item 10.

## Critérios de encerramento

- [ ] Cada item acima implementado e validado individualmente.
- [ ] Nenhum `DELETE`, `DROP` ou recriação destrutiva de tabelas/registros existentes.
- [ ] Sintaxe Python/JavaScript e todos os templates validados.
- [ ] Smoke tests dos endpoints de cruzamento, disponibilidade e escalação.
- [ ] Build e deploy aprovados pelo GitHub Actions.
- [ ] Container no `ssh oracle` saudável após o deploy.
