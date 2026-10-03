# Auditoria de atualizações e dos times de teste — 03/10/2026

## Coleta oficial e externa

O container `cartola-aero-data-fetcher-container` executa `data_fetcher.py`. Os intervalos definidos no código são 30 minutos normalmente e 5 minutos no dia de fechamento, recalculados ao terminar cada ciclo. Os logs do servidor confirmaram ciclos consecutivos às 08:45, 09:15, 09:45 e 10:15 de Brasília no dia da auditoria.

O coletor consulta o status de mercado, a rodada e `atletas/mercado`, persistindo os atletas oficiais em `acf_atletas`. Os status individuais são atualizados junto com os atletas; a tabela de tipos de status só precisa ser inicializada. Partidas e pontuados têm rotinas próprias no mesmo ciclo. Com mercado fechado (`status_mercado == 2`), o ciclo interrompe a atualização oficial após sincronizar os externos. Isso significa que esse serviço não é um coletor de parciais ao vivo durante os jogos.

A fonte `provaveisdocartola.com.br` é baixada antes dessa interrupção, inclusive com mercado fechado. O HTML gera um snapshot separado em `acf_provaveis_fontes`, por temporada, rodada, fonte e ID externo. Cada ciclo inativa os itens anteriores da rodada e insere/reativa os itens presentes. Não sobrescreve `acf_atletas.status_id`.

O Web App escolhe a fonte de cada time em `acw_escalacao_config.fonte_provaveis` e resolve os vínculos manuais em `acw_provaveis_mapeamentos` e `acw_provaveis_clubes_mapeamentos`. Na rodada 29/2026 havia 222 registros externos, 20 clubes mapeados e 209 jogadores mapeados. O log “0 mapeados, 222 pendentes” é produzido por valores fixos de retorno de `sync_html`, não representa a contagem real dos vínculos manuais. A tabela de snapshot pode manter `atleta_id` nulo porque o vínculo é resolvido por JOIN com a tabela de mapeamento.

## Cálculo de favoritismo e SG no servidor

O container `cartola-aero-calculador-container` executa `main.py`. Calcula `acp_peso_jogo_perfis` e `acp_peso_sg_perfis`, por perfil, temporada, rodada e clube, apenas com mercado aberto. Não recalcula os rankings personalizados dos usuários: esses são calculados pelo Web App com a configuração de cada time e salvos em `acw_rankings_teams`.

Os intervalos pretendidos são 30 minutos normalmente e 5 minutos no dia de fechamento. Foi encontrado um desvio: `datetime.now()` produz horário UTC sem fuso dentro do container, enquanto `BlockingScheduler` interpreta o `run_date` sem fuso como `America/Sao_Paulo`. Isso acrescenta três horas ao intervalo real (3h30 normalmente e 3h05 no dia de fechamento).

Evidência: a última rotina terminou às 10:23:34 UTC (07:23:34 de Brasília), e o log indicou próxima execução “10:53:34”. O agendador interpreta esse horário como Brasília, correspondendo a 13:53:34 UTC. O timestamp mais recente das tabelas de pesos correspondia à mesma execução às 10:23:34 UTC. Correção indicada: usar datetimes com fuso explícito em todos os caminhos de agendamento, preferencialmente `datetime.now(BRASILIA_TZ)`, e testar o intervalo por diferença absoluta. Este serviço foi auditado, mas não alterado neste trabalho do Web App.

## Pesos e pontuação dos clones

Os clones não tinham os seis conjuntos personalizados de pesos dos times originais. Exemplo: atacante original `FATOR_PESO_JOGO=4.9`, `FATOR_ESCALACAO=3.5`; em clones havia `10` e `10`. Também havia gravações parciais de teste contendo somente `FATOR_MEDIA`, levando os demais fatores aos defaults. Na rodada 29, os melhores laterais dos clones chegavam a 48–50 na nota calculada; o ranking original da mesma rodada estava próximo de 11.

Foram copiados os seis conjuntos completos para os cinco clones das contas `aero_tier_free_20261002`, `aero_tier_premium_20261002` e `aero_tier_pro_20261002`, usando o nome do time e os originais `Aero-MVPSB` e `Aero-RBSV` do proprietário. Os 24 rankings antigos dos clones foram invalidados. As permissões continuam valendo: o Free utiliza os defaults do plano e não aplica pesos editáveis personalizados; Premium e Pro utilizam os pesos salvos. As escolhas de perfis continuam respeitando os limites dos planos, portanto um clone com perfil diferente não deve ser comparado como se tivesse cálculo idêntico ao original.

No `Aero-MVPSB` da conta Premium de teste, foram removidas a escolha de perfis e a estratégia de escalação para verificar o guia desde o começo. Antes da alteração, configurações, pesos e rankings dos testes foram copiados para a tabela recuperável `acw_test_setup_backup_20261003`. Os times originais não foram alterados.

As fórmulas individuais de pontuação dos seis módulos não foram alteradas neste trabalho. O total da escalação é a soma das notas dos titulares e treinador mais uma nota adicional do capitão (pontuação em dobro). É um índice calculado pelos pesos, e não uma promessa de pontos reais do Cartola. O card passou a explicar esse significado. A API de edição agora valida números finitos, aceita decimais, preserva os outros pesos em atualizações parciais e invalida o ranking da posição editada.
