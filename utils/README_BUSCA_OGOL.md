# Busca de URLs do Ogol - Múltiplas APIs

## Estratégias Implementadas

O script `buscar_urls_ogol_multiplas_apis.py` usa múltiplas estratégias para encontrar URLs de fotos do ogol:

### 1. DuckDuckGo Search (PRINCIPAL - Gratuita)
- **Biblioteca**: `duckduckgo-search`
- **Vantagens**: 
  - Gratuita, sem necessidade de chave API
  - Não tem rate limiting rígido
  - Funciona bem para buscas específicas
- **Como usar**: Já está configurado, funciona automaticamente

### 2. Bing Search API (Opcional - Requer chave)
- **Vantagens**: API oficial da Microsoft
- **Limitações**: Requer chave API (gratuita até certo limite)
- **Como configurar**: Adicione no `.env`:
  ```
  BING_SEARCH_API_KEY=sua_chave_aqui
  ```
- **Obter chave**: https://portal.azure.com -> Criar recurso "Bing Search v7"

### 3. SerpAPI (Opcional - Requer chave)
- **Vantagens**: API profissional, muito confiável
- **Limitações**: Serviço pago (mas tem trial gratuito)
- **Como configurar**: Adicione no `.env`:
  ```
  SERPAPI_KEY=sua_chave_aqui
  ```
- **Obter chave**: https://serpapi.com/

### 4. Playwright (Fallback)
- Usado apenas se todas as APIs falharem
- Acessa Bing ou DuckDuckGo via browser automatizado

## Como Usar

```bash
python utils/buscar_urls_ogol_multiplas_apis.py
```

O script:
1. Lista todos os atletas sem foto
2. Para cada atleta, tenta encontrar a URL do ogol usando as estratégias acima
3. Extrai a URL da foto da página do ogol
4. Salva tudo em `utils/urls_ogol_atletas.json`
5. Salva progresso em `utils/progresso_urls_ogol.json` (pode interromper e retomar)

## Resultado

O arquivo `urls_ogol_atletas.json` terá o formato:
```json
{
  "140726": {
    "atleta_id": 140726,
    "nome": "David Martins",
    "clube": "BAH",
    "url_foto": "https://www.ogol.com.br/img/jogadores/...",
    "data_busca": "2025-01-21T..."
  },
  ...
}
```

## Próximos Passos

Depois de ter o arquivo com todas as URLs, você pode:
1. Usar o RPA existente para baixar as fotos
2. Ou criar um script que processa o JSON e baixa todas as fotos automaticamente

