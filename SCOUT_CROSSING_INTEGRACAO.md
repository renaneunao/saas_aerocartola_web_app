# Integração do cruzamento de scouts

O módulo está isolado em `routes/scout_crossing.py` e não altera `app.py` nem os templates de posição. Para ativá-lo, faça manualmente a integração abaixo.

## 1. Registrar o blueprint

No bloco de registro de blueprints do `app.py`:

```python
from routes.scout_crossing import scout_crossing_bp
app.register_blueprint(scout_crossing_bp)
```

A página ficará em `/cruzamento-scouts/`. Um link de navegação pode usar:

```jinja2
<a href="{{ url_for('scout_crossing.index') }}">Cruzamento de Scouts</a>
```

## 2. Botão nos modais de posição

Em cada template de posição que deverá oferecer a ação, inclua o fragmento uma vez, carregue os assets e adicione um botão no conteúdo do modal existente:

```jinja2
{% include 'modals/modal_cruzamento_scouts.html' %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/scout-crossing.css') }}">
<script src="{{ url_for('static', filename='js/scout-crossing.js') }}"></script>
```

O script funciona mesmo sem a página do cruzamento estar presente e expõe a função global:

```jinja2
<button type="button"
        onclick="openScoutCrossingModal({{ atleta_id }}, { temporada: {{ temporada_atual }}, rodada: {{ rodada_atual }} })">
    <i class="fas fa-crosshairs"></i> Cruzar scouts
</button>
```

Se o modal já tiver uma variável de temporada/rodada diferente, passe esses valores no mesmo objeto. A função carrega o detalhe da rodada pela API do blueprint e abre o fragmento sem substituir o modal existente.

## 3. APIs disponíveis

- `GET /cruzamento-scouts/api/opcoes?temporada=2026&posicao_id=5&rodada=10&atleta_id=...`
- `GET /cruzamento-scouts/api/cruzar?atleta_id=...&posicao_id=5&temporada=2026&rodada=10&adversario_id=...`
- `GET /cruzamento-scouts/api/detalhe/<atleta_id>/<rodada>?temporada=2026`

As consultas usam as tabelas ACF existentes (`acf_atletas`, `acf_atletas_historico`, `acf_pontuados`, `acf_partidas` e `acf_clubes`); nenhuma migração é necessária.
