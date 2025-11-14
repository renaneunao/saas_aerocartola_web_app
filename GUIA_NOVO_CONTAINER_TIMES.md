# Guia de Implementação - Servidor de Recepção de Times

Este documento descreve como configurar e implementar o novo servidor Flask que receberá payloads de times dos usuários via extensão do navegador.

## Visão Geral

O novo servidor Flask será responsável por:
- Receber requisições POST com payloads contendo tokens do Cartola
- Associar os times aos usuários na tabela `acw_teams`
- Validar e processar os dados recebidos
- Conectar-se ao banco de dados PostgreSQL existente

## Estrutura da Tabela `acw_teams`

A tabela que armazena os times associados aos usuários possui a seguinte estrutura:

```sql
CREATE TABLE IF NOT EXISTS acw_teams (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    id_token TEXT,
    team_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES acw_users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_teams_user_id ON acw_teams(user_id);
```

### Descrição dos Campos

- **id**: Chave primária auto-incrementável (gerada automaticamente)
- **user_id**: ID do usuário na tabela `acw_users` (obrigatório, vem do payload)
- **access_token**: Token de acesso do Cartola (obrigatório, vem do payload)
- **refresh_token**: Token de refresh do Cartola que contém os IDs dos times (obrigatório, vem do payload)
- **id_token**: Token de identificação do Cartola (opcional, vem do payload)
- **team_name**: Nome do time do Cartola (opcional, pode ser obtido via API depois)
- **created_at**: Timestamp de criação (gerado automaticamente)
- **updated_at**: Timestamp de última atualização (gerado automaticamente)

## Credenciais do Banco de Dados

O servidor precisa se conectar ao mesmo banco PostgreSQL usado pela aplicação principal. As credenciais são configuradas via variáveis de ambiente:

### Variáveis de Ambiente Necessárias

```env
POSTGRES_HOST=postgres                    # Host do PostgreSQL (ou IP do servidor)
POSTGRES_PORT=5432                        # Porta do PostgreSQL (padrão: 5432)
POSTGRES_USER=postgres                    # Usuário do banco de dados
POSTGRES_PASSWORD=sua_senha_aqui          # Senha do banco de dados
POSTGRES_DB=cartola_manager               # Nome do banco de dados
```

**⚠️ IMPORTANTE**: Use as mesmas credenciais do projeto principal para acessar o mesmo banco de dados.

## Docker Compose

Crie um arquivo `docker-compose.yml` para o novo container:

```yaml
version: '3.8'

services:
  times-receiver:
    build:
      context: .
      dockerfile: Dockerfile
    image: renaneunao/saas-cartola-times-receiver:latest
    container_name: cartola-aero-times-receiver-container
    restart: unless-stopped
    env_file:
      - .env
    environment:
      POSTGRES_HOST: ${POSTGRES_HOST}
      POSTGRES_PORT: ${POSTGRES_PORT:-5432}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
      FLASK_ENV: ${FLASK_ENV:-production}
      SECRET_KEY: ${SECRET_KEY:-change-me-to-a-secure-random-value-in-production}
    ports:
      - "5001:5000"  # Porta diferente da web-app (5000)
    volumes:
      - ./logs:/app/logs
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - infra_network
    depends_on:
      - postgres  # Se o postgres estiver no mesmo compose, caso contrário remover

networks:
  infra_network:
    external: true  # Usa a mesma rede da aplicação principal
```

**Nota**: Se o PostgreSQL estiver em outro container/compose, remova o `depends_on` e certifique-se de que ambos os containers estejam na mesma rede `infra_network`.

## Arquivo .env

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```env
# PostgreSQL Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=sua_senha_aqui
POSTGRES_DB=cartola_manager

# Flask Configuration
FLASK_ENV=production
SECRET_KEY=gerar-uma-chave-secreta-aleatoria-aqui

# Server Configuration (opcional)
FLASK_PORT=5000
```

**⚠️ SEGURANÇA**: 
- Nunca commite o arquivo `.env` no repositório
- Use uma chave secreta forte e aleatória para `SECRET_KEY`
- Mantenha as credenciais do banco seguras

## Estrutura do Payload Esperado

O endpoint receberá requisições POST com o seguinte formato JSON:

### Payload Completo

```json
{
    "user_id": 123,
    "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "team_name": "Meu Time FC"
}
```

### Campos do Payload

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `user_id` | integer | ✅ Sim | ID do usuário logado na plataforma (capturado pela extensão) |
| `refresh_token` | string | ✅ Sim | Token de refresh do Cartola que contém os IDs dos times |
| `access_token` | string | ✅ Sim | Token de acesso atual do Cartola |
| `id_token` | string | ❌ Não | Token de identificação do Cartola (opcional) |
| `team_name` | string | ❌ Não | Nome do time do Cartola (pode ser obtido via API depois) |

### Exemplo de Requisição

```bash
curl -X POST http://localhost:5001/api/teams/associate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123,
    "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "team_name": "Meu Time FC"
  }'
```

## Conexão com PostgreSQL

### Exemplo de Código Python (usando psycopg2)

```python
import psycopg2
import os
from typing import Optional

# Configurações do PostgreSQL
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD'),
    'database': os.getenv('POSTGRES_DB')
}

def get_db_connection():
    """Conecta ao banco de dados PostgreSQL"""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        conn.autocommit = False
        return conn
    except psycopg2.Error as e:
        print(f"Erro ao conectar ao PostgreSQL: {e}")
        return None

def close_db_connection(conn):
    """Fecha a conexão com o banco de dados"""
    if conn:
        try:
            conn.close()
        except psycopg2.Error as e:
            print(f"Erro ao fechar conexão: {e}")
```

### Exemplo de Inserção na Tabela

```python
def create_team(
    conn,
    user_id: int,
    access_token: str,
    refresh_token: str,
    id_token: str = None,
    team_name: str = None
) -> Optional[int]:
    """Cria um novo time. Retorna o ID do time criado."""
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO acw_teams (user_id, access_token, refresh_token, id_token, team_name)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        ''', (user_id, access_token, refresh_token, id_token, team_name))
        team_id = cursor.fetchone()[0]
        conn.commit()
        return team_id
    except psycopg2.Error as e:
        conn.rollback()
        print(f"Erro ao criar time: {e}")
        return None
    finally:
        cursor.close()
```

## Endpoint Flask Sugerido

### Estrutura Básica do Endpoint

```python
from flask import Flask, request, jsonify
import psycopg2
from database import get_db_connection, close_db_connection

app = Flask(__name__)

@app.route('/api/teams/associate', methods=['POST'])
def associate_team():
    """
    Endpoint para associar um time do Cartola a um usuário.
    
    Payload esperado:
    {
        "user_id": int,
        "refresh_token": str,
        "access_token": str,
        "id_token": str (opcional),
        "team_name": str (opcional)
    }
    """
    try:
        data = request.get_json()
        
        # Validação dos campos obrigatórios
        if not data:
            return jsonify({'error': 'Payload vazio'}), 400
        
        user_id = data.get('user_id')
        refresh_token = data.get('refresh_token')
        access_token = data.get('access_token')
        
        if not user_id or not refresh_token or not access_token:
            return jsonify({
                'error': 'Campos obrigatórios faltando',
                'required': ['user_id', 'refresh_token', 'access_token']
            }), 400
        
        # Campos opcionais
        id_token = data.get('id_token')
        team_name = data.get('team_name')
        
        # Conectar ao banco
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Erro ao conectar ao banco de dados'}), 500
        
        try:
            # Verificar se o usuário existe
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM acw_users WHERE id = %s', (user_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Usuário não encontrado'}), 404
            
            # Inserir o time
            cursor.execute('''
                INSERT INTO acw_teams (user_id, access_token, refresh_token, id_token, team_name)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, created_at
            ''', (user_id, access_token, refresh_token, id_token, team_name))
            
            result = cursor.fetchone()
            team_id = result[0]
            created_at = result[1]
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Time associado com sucesso',
                'team_id': team_id,
                'user_id': user_id,
                'created_at': created_at.isoformat()
            }), 201
            
        except psycopg2.IntegrityError as e:
            conn.rollback()
            return jsonify({'error': 'Erro de integridade: possivelmente usuário não existe'}), 400
        except psycopg2.Error as e:
            conn.rollback()
            return jsonify({'error': f'Erro ao inserir no banco: {str(e)}'}), 500
        finally:
            cursor.close()
            close_db_connection(conn)
            
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
```

## Validações Recomendadas

1. **Validação de Usuário**: Verificar se o `user_id` existe na tabela `acw_users`
2. **Validação de Tokens**: Validar formato básico dos tokens (não vazios, tamanho mínimo)
3. **Validação de Duplicatas**: Decidir se permite múltiplos times por usuário (a tabela permite)
4. **Sanitização**: Validar e sanitizar todos os inputs antes de inserir no banco
5. **Rate Limiting**: Implementar rate limiting para evitar abuso

## Segurança

1. **Autenticação**: Considere adicionar autenticação no endpoint (API key, JWT, etc.)
2. **HTTPS**: Use HTTPS em produção
3. **Validação de Origem**: Valide que as requisições vêm da extensão autorizada
4. **Logs**: Registre todas as tentativas de associação (sucesso e falha)
5. **Criptografia**: Considere criptografar os tokens antes de armazenar (se ainda não estiver implementado)

## Fluxo de Funcionamento

1. **Extensão captura a sessão**: A extensão do navegador captura o `user_id` do usuário logado
2. **Extensão captura tokens**: A extensão captura os tokens do Cartola (refresh_token, access_token, etc.)
3. **Extensão envia payload**: A extensão faz POST para o endpoint `/api/teams/associate`
4. **Servidor valida**: O servidor valida o payload e verifica se o usuário existe
5. **Servidor insere**: O servidor insere os dados na tabela `acw_teams`
6. **Servidor responde**: O servidor retorna sucesso com o `team_id` criado

## Dependências Python

Crie um arquivo `requirements.txt`:

```txt
Flask==3.0.0
psycopg2-binary==2.9.9
python-dotenv==1.0.0
```

## Dockerfile Sugerido

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Expor porta
EXPOSE 5000

# Comando para rodar a aplicação
CMD ["python", "app.py"]
```

## Testes

### Teste Manual com cURL

```bash
# Teste básico
curl -X POST http://localhost:5001/api/teams/associate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "refresh_token": "test_refresh_token",
    "access_token": "test_access_token"
  }'

# Teste com todos os campos
curl -X POST http://localhost:5001/api/teams/associate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "refresh_token": "test_refresh_token",
    "access_token": "test_access_token",
    "id_token": "test_id_token",
    "team_name": "Meu Time FC"
  }'
```

## Próximos Passos

1. Implementar o servidor Flask com o endpoint descrito
2. Configurar Docker e docker-compose
3. Testar a conexão com o banco de dados
4. Implementar validações e tratamento de erros
5. Adicionar logs e monitoramento
6. Implementar autenticação/autorização (se necessário)
7. Criar a extensão do navegador que enviará os payloads

## Notas Importantes

- O `refresh_token` contém informações sobre os times do usuário no Cartola
- A extensão será responsável por capturar o `user_id` da sessão logada
- O servidor apenas recebe e armazena os dados, não faz refresh de tokens
- A tabela permite múltiplos times por usuário (um usuário pode ter vários times)
- Use a mesma rede Docker (`infra_network`) para comunicação entre containers


