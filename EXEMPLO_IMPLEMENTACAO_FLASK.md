# 💻 Exemplo de Implementação - Flask

## Opção 1: Script Inline no Template (Mais Simples)

### 1. No seu template do dashboard (`templates/dashboard.html` ou similar):

```html
<!DOCTYPE html>
<html>
<head>
    <!-- ... head content ... -->
</head>
<body>
    <!-- ... conteúdo do dashboard ... -->
    
    <!-- ANTES DO FECHAMENTO DO </body>, adicione: -->
    <script>
        // Expor user_id para a extensão do navegador
        {% if current_user and current_user.id %}
        window.userId = {{ current_user.id|tojson }};
        window.user_id = {{ current_user.id|tojson }};
        console.log('✅ [Cartola Manager] User ID exposto:', window.userId);
        {% else %}
        console.warn('⚠️ [Cartola Manager] User ID não disponível');
        {% endif %}
    </script>
</body>
</html>
```

### 2. Se você usa um template base (`templates/base.html`):

```html
<!-- No base.html, antes do </body> -->
<script>
    {% if current_user and current_user.id %}
    window.userId = {{ current_user.id|tojson }};
    window.user_id = {{ current_user.id|tojson }};
    {% endif %}
</script>
```

---

## Opção 2: Arquivo JS Separado

### 1. Criar arquivo `static/js/user-info.js`:

```javascript
// user-info.js
// Este arquivo será gerado dinamicamente pelo Flask
// OU você pode fazer uma requisição AJAX para obter o user_id

(function() {
    'use strict';
    
    // Método 1: Se você pode injetar o user_id via template
    // (veja Opção 1 acima)
    
    // Método 2: Fazer requisição ao backend
    fetch('/api/user/current')
        .then(response => {
            if (!response.ok) {
                throw new Error('Erro ao obter user_id');
            }
            return response.json();
        })
        .then(data => {
            if (data.user_id) {
                window.userId = data.user_id;
                window.user_id = data.user_id;
                window.currentUser = data;
                console.log('✅ [Cartola Manager] User ID carregado:', window.userId);
            }
        })
        .catch(error => {
            console.error('❌ [Cartola Manager] Erro ao carregar user_id:', error);
        });
})();
```

### 2. Criar endpoint no Flask (`app.py` ou `routes.py`):

```python
from flask import jsonify
from flask_login import login_required, current_user

@app.route('/api/user/current', methods=['GET'])
@login_required
def get_current_user():
    """Retorna informações do usuário logado"""
    return jsonify({
        'user_id': current_user.id,
        'username': current_user.username,
        # Adicione outros campos se necessário
    })
```

### 3. Incluir o script no template:

```html
<!-- No template do dashboard -->
<script src="{{ url_for('static', filename='js/user-info.js') }}"></script>
```

---

## Opção 3: Data Attribute no Body

### No template do dashboard:

```html
<body data-user-id="{{ current_user.id if current_user else '' }}" class="...">
    <!-- ... conteúdo ... -->
</body>
```

A extensão já está preparada para ler este atributo automaticamente.

---

## Opção 4: Context Processor (Global)

### 1. Criar context processor no Flask:

```python
# app.py ou __init__.py

@app.context_processor
def inject_user():
    """Injeta variáveis globais em todos os templates"""
    return {
        'current_user_id': current_user.id if current_user.is_authenticated else None
    }
```

### 2. Usar no template:

```html
<script>
    {% if current_user_id %}
    window.userId = {{ current_user_id|tojson }};
    window.user_id = {{ current_user_id|tojson }};
    {% endif %}
</script>
```

---

## 🎯 Recomendação para Flask

**Use a Opção 1 (Script Inline)** porque:

1. ✅ Não requer criar novos arquivos
2. ✅ Não requer criar novos endpoints
3. ✅ Funciona imediatamente
4. ✅ O `current_user` já está disponível no template

### Código Final Recomendado:

```html
<!-- No final do template do dashboard, antes de </body> -->
<script>
    {% if current_user and current_user.is_authenticated %}
    window.userId = {{ current_user.id|tojson }};
    window.user_id = {{ current_user.id|tojson }};
    console.log('✅ [Cartola Manager] User ID:', window.userId);
    {% else %}
    console.warn('⚠️ [Cartola Manager] Usuário não autenticado');
    {% endif %}
</script>
```

---

## ✅ Teste Rápido

Após implementar, abra o console do navegador (F12) no dashboard e digite:

```javascript
window.userId
// Deve retornar: 123 (ou o ID do seu usuário)
```

Se retornar o ID, está funcionando! ✅

