# Sincronização de Pesos - Módulos de Posições

## Problema Identificado

Quando o usuário abria um módulo de posição (goleiro, lateral, zagueiro, meia, atacante), a tabela carregava com pesos padrão hardcoded no JavaScript, que eram diferentes dos pesos salvos pelo usuário ou dos pesos padrão definidos no `app.py`.

Havia **TRÊS** locais com pesos padrão que estavam desalinhados:
1. **Template HTML** (função `modulo_individual` no `app.py` - linhas 1089-1142) - ❌ DESATUALIZADOS
2. **API de dados** (`app.py` - linhas 1728-1755) - ✅ CORRETOS
3. **JavaScript** (arquivos `calculo_*.js`) - ✅ JÁ ESTAVAM CORRETOS

## Solução Implementada

### 1. Sincronização dos Pesos Padrão no Template

Atualizei os pesos padrão na função `modulo_individual` (app.py, linhas 1089-1116) para serem **idênticos** aos pesos da API:

#### Goleiro:
- FATOR_MEDIA: 0.2
- FATOR_FF: 4.5
- FATOR_FD: 6.5
- FATOR_SG: 1.5
- FATOR_PESO_JOGO: 1.5
- FATOR_GOL_ADVERSARIO: 2.0

#### Lateral:
- FATOR_MEDIA: 3.0
- FATOR_DS: 8.0
- FATOR_SG: 2.0
- FATOR_ESCALACAO: 10.0
- FATOR_FF: 2.0
- FATOR_FS: 1.0
- FATOR_FD: 2.0
- FATOR_G: 4.0
- FATOR_A: 4.0
- FATOR_PESO_JOGO: 1.0

#### Zagueiro:
- FATOR_MEDIA: 1.5
- FATOR_DS: 4.5
- FATOR_SG: 4.0
- FATOR_ESCALACAO: 5.0
- FATOR_PESO_JOGO: 5.0

#### Meia:
- FATOR_MEDIA: 1.0
- FATOR_DS: 3.6
- FATOR_FF: 0.7
- FATOR_FS: 0.8
- FATOR_FD: 0.9
- FATOR_G: 2.5
- FATOR_A: 2.0
- FATOR_ESCALACAO: 10.0
- FATOR_PESO_JOGO: 9.5

#### Atacante:
- FATOR_MEDIA: 2.5
- FATOR_DS: 2.0
- FATOR_FF: 1.2
- FATOR_FS: 1.3
- FATOR_FD: 1.3
- FATOR_G: 2.5
- FATOR_A: 2.5
- FATOR_ESCALACAO: 10.0
- FATOR_PESO_JOGO: 10.0

#### Treinador:
- FATOR_PESO_JOGO: 1.0

## Como Funciona Agora

### Fluxo de Carregamento de Pesos:

1. **Usuário abre um módulo** (ex: `/modulos/goleiro`)
   
2. **Servidor renderiza o template** (`modulo_individual`)
   - Busca pesos salvos no banco de dados (`acw_posicao_weights`)
   - Se não houver, usa pesos padrão sincronizados
   - Passa `pesos_atuais` para o template

3. **Template HTML exibe inputs** com os valores corretos
   - Os inputs mostram os pesos salvos OU padrão do app.py

4. **JavaScript carrega automaticamente**
   - Faz fetch para `/api/modulos/<posição>/dados`
   - API retorna:
     - Dados dos atletas
     - **Pesos** (salvos ou padrão)
     - Outras configurações

5. **JavaScript calcula rankings**
   - Cria instância da classe de cálculo com `data.pesos`
   - Se `data.pesos` existir, usa esses pesos
   - Se não existir (fallback), usa pesos hardcoded no JS (que agora são iguais!)

## Resultado Final

✅ **Todos os três locais agora usam os MESMOS pesos padrão**
✅ **Inputs do formulário mostram valores corretos**
✅ **Cálculos JavaScript usam pesos corretos desde o início**
✅ **Pesos salvos pelo usuário são respeitados**
✅ **Pesos padrão são consistentes em todo o sistema**

## Prioridade de Pesos

A ordem de prioridade para os pesos é:

1. **Pesos salvos pelo usuário** (tabela `acw_posicao_weights`)
2. **Pesos padrão** (definidos no `app.py` e sincronizados com JS)

## Arquivos Modificados

- ✅ `/workspace/app.py` - Linhas 1089-1116 (função `modulo_individual`)

## Arquivos Verificados (já estavam corretos)

- ✅ `/workspace/static/js/calculo_goleiro.js`
- ✅ `/workspace/static/js/calculo_lateral.js`
- ✅ `/workspace/static/js/calculo_zagueiro.js`
- ✅ `/workspace/static/js/calculo_meia.js`
- ✅ `/workspace/static/js/calculo_atacante.js`
- ✅ `/workspace/templates/modulo_goleiro.html`
- ✅ `/workspace/templates/modulo_lateral.html`
- ✅ `/workspace/templates/modulo_meia.html`
- ✅ (e outros templates de módulos)

## Testando

Para testar se está funcionando:

1. Abra qualquer módulo de posição (ex: `/modulos/goleiro`)
2. Verifique os valores nos inputs do formulário
3. A tabela deve carregar automaticamente com os mesmos pesos
4. Salve novos pesos se desejar
5. Recarregue a página - deve usar os pesos salvos
6. Delete os pesos salvos - deve voltar aos padrão do app.py

---

**Data**: 2025-11-05
**Status**: ✅ Concluído
