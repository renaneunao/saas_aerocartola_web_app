# Container 3 - API Service

API REST para o sistema SaaS Cartola FC. Este serviço fornece endpoints para autenticação, gerenciamento de usuários, credenciais do Cartola, dados de atletas, perfis de pesos e escalação.

## Funcionalidades

- **Autenticação**: Login e registro de usuários com JWT
- **Credenciais do Cartola**: Gerenciamento de tokens de acesso por usuário
- **Dados de Atletas**: Endpoints para buscar atletas filtrados por posição
- **Perfis**: Busca de perfis de peso de jogo e peso SG pré-calculados
- **Rankings**: Salvamento e recuperação de rankings calculados pelos usuários
- **Configurações de Pesos**: Gerenciamento de configurações personalizadas de pesos por usuário
- **Escalação**: Cálculo e envio de escalações para o Cartola FC

## Tecnologias

- FastAPI
- PostgreSQL
- JWT para autenticação
- Docker

## Configuração

### Variáveis de Ambiente

```bash
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=cartola_manager
SECRET_KEY=seu-secret-key-aqui
CORS_ORIGINS=*
```

### Executar Localmente

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar aplicação
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Executar com Docker

```bash
# Build da imagem
docker build -t saas-cartola-api-service .

# Executar container
docker run -p 8000:8000 \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PASSWORD=password \
  -e SECRET_KEY=seu-secret-key \
  saas-cartola-api-service
```

## Endpoints Principais

### Autenticação
- `POST /api/auth/register` - Registrar novo usuário
- `POST /api/auth/login` - Fazer login
- `GET /api/auth/me` - Obter informações do usuário atual

### Credenciais do Cartola
- `GET /api/cartola-credentials` - Buscar credenciais
- `POST /api/cartola-credentials` - Criar/atualizar credenciais
- `DELETE /api/cartola-credentials` - Remover credenciais

### Atletas
- `GET /api/atletas?posicao_id={id}&rodada={r}` - Buscar atletas

### Perfis
- `GET /api/perfis/peso-jogo` - Listar perfis de peso de jogo
- `GET /api/perfis/peso-jogo/{perfil_id}` - Obter pesos de jogo de um perfil
- `GET /api/perfis/peso-sg` - Listar perfis de peso SG
- `GET /api/perfis/peso-sg/{perfil_id}` - Obter pesos SG de um perfil

### Rankings e Configurações
- `POST /api/rankings/configurations` - Salvar configuração de pesos
- `GET /api/rankings/configurations` - Listar configurações
- `POST /api/rankings/save` - Salvar ranking calculado
- `GET /api/rankings` - Buscar rankings salvos

### Escalação
- `POST /api/escalacao/calcular` - Calcular escalação ideal
- `POST /api/escalacao/enviar` - Enviar escalação para Cartola

## Estrutura do Projeto

```
app/
├── __init__.py
├── main.py              # Aplicação FastAPI principal
├── database.py          # Conexão e inicialização do banco
└── routers/
    ├── __init__.py
    ├── auth.py          # Autenticação
    ├── users.py         # Usuários
    ├── cartola_credentials.py  # Credenciais do Cartola
    ├── atletas.py       # Dados de atletas
    ├── perfis.py        # Perfis de pesos
    ├── rankings.py      # Rankings e configurações
    └── escalacao.py     # Escalação
```

## Documentação da API

Quando a aplicação estiver rodando, acesse:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

