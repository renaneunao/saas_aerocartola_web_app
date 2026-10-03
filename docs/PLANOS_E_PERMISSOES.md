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
