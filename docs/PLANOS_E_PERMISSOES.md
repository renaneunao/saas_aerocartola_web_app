# Planos do Aero Cartola

Esta é a matriz de produto para a experiência do aplicativo. A chave interna
`avancado` permanece por compatibilidade com banco e Stripe; o nome exibido é
**Premium**. Preços, meios de pagamento e impostos são decisões separadas.

| Recurso | Gratuito | Premium | Pro |
| --- | --- | --- | --- |
| Times vinculados | 1 | 2 | Sem limite de plano |
| Dashboard, rankings, scouts, comparações e detalhes | Completos | Completos | Completos |
| Perfis prontos de peso de jogo e SG | 2 de cada | 5 de cada | Até 15 de jogo e 10 de SG |
| Escalação rápida do próprio time | Sim | Sim | Sim |
| Campinho, troca manual, capitão, reservas e envio | Sim | Sim | Sim |
| Editar pesos de cálculo por posição | Não; usa padrões | Sim | Sim |
| Hack do goleiro e fechar defesa | Não | Não | Sim |
| Reordenar prioridades | Não | Não | Sim |
| Escalar vários times em lote | Não | Não | Sim |

O gratuito é um fluxo útil de ponta a ponta: vincular um time, analisar todos
os dados, escolher um perfil pronto, obter uma sugestão, corrigir atletas no
campo e enviar a escalação. Não se deve borrar rankings nem esconder scouts.
As restrições pagas são personalização, estratégia especial e escala. A
escolha de formação, capitão, reserva de luxo e atletas do próprio time é
básica e não deve exigir assinatura.

## Regras técnicas

- A API, e não apenas o botão, deve verificar escrita de pesos, opções Pro e
  limite de times. Falhas devem retornar 403 sem persistir alterações.
- O número de perfis mede a posição do perfil na lista ordenada da rodada,
  não o ID bruto. O mesmo critério vale para exibir e para salvar.
- Perfil já selecionado que deixou de existir na rodada deve oferecer uma
  escolha válida, sem travar o formulário. Não se escolhe um perfil bloqueado
  automaticamente.
- Os testes dos tiers usam contas próprias e clones dos times autorizados.
  O envio usa uma resposta simulada da API Cartola para preservar a escalação
  dos times originais.
- Testar desktop e celular para cada plano: acesso às páginas, perfis,
  cálculo, edição e envio, além de tentar chamar diretamente as APIs
  bloqueadas. Verificar que dados não vazam entre contas.

## Pendências comerciais

Não ativar cobrança em produção até validar checkout, webhooks, cancelamento,
reembolsos e atualização automática do plano. A página de assinatura precisa
refletir esta matriz; preços atuais são apenas os que já constam no produto.

## Validação executada em 3 de outubro de 2026

As contas temporárias de teste foram criadas no app e receberam apenas cópias
dos dois times autorizados. No fluxo de escalação, as chamadas ao endpoint de
envio foram substituídas no navegador por respostas simuladas. Nenhum time
original foi enviado ao Cartola.

| Plano | Verificações no app de produção |
| --- | --- |
| Gratuito | Limites de 2 perfis de jogo e 2 de SG; cálculo da escalação ideal; edição e recálculo do capitão; envio simulado; pesos editáveis, opções Pro e segundo vínculo recusados pela API com 403; tela de pesos bloqueada e ranking visível. |
| Premium | Limites de 5 perfis de jogo e 5 de SG; escalação ideal acessível; edição de pesos aceita; hack do goleiro, fechar defesa, reordenar prioridades e terceiro vínculo recusados com 403. |
| Pro | 15 perfis de jogo e 10 de SG; opções de hack, defesa e prioridades aceitas; dois times selecionáveis; envio individual simulado e “Escalar todos” concluiu os dois clones com 2/2 sucessos simulados. |

As telas de escalação ideal, módulos e cruzamento abriram na janela móvel de
390 px sem exceder a largura do viewport. O teste encontrou e corrigiu um
desalinhamento na projeção: o cálculo inicial agora dobra a pontuação do
capitão, como já acontecia ao trocar o capitão manualmente. O caso foi
adicionado à suíte de testes.

Commits publicados: `fe692b4` (planos e permissões) e `9a0931d` (projeção do
capitão). Os dois workflows de build e deploy terminaram com sucesso; o
container de produção está na revisão `9a0931d3cfdf28738fd8a0ba5bba80a626224fab`.
