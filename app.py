from flask import Flask, jsonify, render_template, Response, request, redirect, url_for, flash, session
import traceback
import json
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'change-me-to-a-secure-random-value')

from database import get_db_connection, close_db_connection
from models.users import (
    authenticate_user,
    get_all_users,
    create_user,
    update_user_password
)
from models.teams import get_all_user_teams, create_team, get_team, update_team

# Timezone: Brasília (America/Sao_Paulo)
try:
    from zoneinfo import ZoneInfo
    TZ_BR = ZoneInfo("America/Sao_Paulo")
except Exception:
    TZ_BR = None
    try:
        import pytz
        TZ_BR = pytz.timezone("America/Sao_Paulo")
    except Exception:
        pytz = None

def now_brasilia():
    """Return current datetime in Brasília timezone if possible, else local naive now."""
    try:
        if TZ_BR is not None:
            return datetime.now(TZ_BR)
    except Exception:
        pass
    return datetime.now()

# ========================================
# SISTEMA DE AUTENTICAÇÃO
# ========================================

def login_required(f):
    """Decorator para proteger rotas que requerem autenticação"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_user_authenticated():
            flash('Você precisa fazer login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator para proteger rotas que requerem privilégios de admin"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_user_authenticated():
            flash('Você precisa fazer login para acessar esta página.', 'error')
            return redirect(url_for('login'))
        
        user = get_current_user()
        if not user or not user.get('is_admin', False):
            flash('Você precisa ser administrador para acessar esta página.', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def is_user_authenticated():
    """Verifica se o usuário está autenticado"""
    return session.get('user_id') is not None

def get_current_user():
    """Retorna os dados do usuário atual ou None"""
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, email, full_name, is_active, is_admin
            FROM acw_users
            WHERE id = %s AND is_active = TRUE
        ''', (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'username': row[1],
            'email': row[2],
            'full_name': row[3],
            'is_active': row[4],
            'is_admin': row[5]
        }
    except Exception as e:
        print(f"Erro ao buscar usuário: {e}")
        return None
    finally:
        close_db_connection(conn)

def logout_user():
    """Faz logout do usuário atual"""
    session.clear()

# ========================================
# ROTAS PRINCIPAIS
# ========================================

@app.route('/')
@login_required
def index():
    user = get_current_user()
    
    # Verificar se o usuário tem times associados
    from models.teams import create_teams_table
    conn = get_db_connection()
    try:
        create_teams_table(conn)
        times = get_all_user_teams(conn, user['id'])
    finally:
        close_db_connection(conn)
    
    # Se não tiver times, redirecionar para página de associação
    if not times or len(times) == 0:
        return redirect(url_for('associar_credenciais'))
    
    # Se tiver times, mostrar página inicial com seleção de perfis
    return redirect(url_for('pagina_inicial'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página e processamento de login"""
    if is_user_authenticated():
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember_me = bool(request.form.get('remember'))
        
        if not username_or_email or not password:
            flash('Por favor, preencha todos os campos.', 'error')
            return render_template('login.html')
        
        auth_result = authenticate_user(username_or_email, password)
        
        if auth_result['success']:
            user = auth_result['user']
            # Usar sessão do Flask diretamente (sem sessões customizadas)
            session['user_id'] = user['id']
            session['username'] = user['username']
            # Inicializar time selecionado com o primeiro time do usuário (se houver)
            from models.teams import create_teams_table
            conn = get_db_connection()
            try:
                create_teams_table(conn)
                times = get_all_user_teams(conn, user['id'])
                if times and len(times) > 0:
                    session['selected_team_id'] = times[0]['id']
            finally:
                close_db_connection(conn)
            flash(f'Bem-vindo, {user.get("full_name") or user["username"]}!', 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash(auth_result['error'], 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout do usuário"""
    logout_user()
    flash('Você foi desconectado com sucesso.', 'success')
    return redirect(url_for('login'))

@app.route('/associar-credenciais', methods=['GET', 'POST'])
@login_required
def associar_credenciais():
    """Página para associar credenciais do Cartola ao usuário"""
    user = get_current_user()
    
    from models.teams import create_teams_table
    
    if request.method == 'POST':
        access_token = request.form.get('access_token', '').strip()
        refresh_token = request.form.get('refresh_token', '').strip()
        id_token = request.form.get('id_token', '').strip() or None
        team_name = request.form.get('team_name', '').strip() or None
        
        if not access_token or not refresh_token:
            flash('Por favor, preencha pelo menos o Access Token e Refresh Token.', 'error')
            return render_template('associar_credenciais.html', current_user=user)
        
        conn = get_db_connection()
        try:
            create_teams_table(conn)
            
            # Buscar dados do time da API do Cartola para obter nome
            from api_cartola import fetch_team_info_by_team_id
            final_team_name = team_name
            
            # Criar time temporário para buscar dados
            temp_id = create_team(
                conn, user['id'], access_token, refresh_token, id_token, team_name
            )
            
            # Buscar informações do time (nome)
            try:
                team_info = fetch_team_info_by_team_id(conn, temp_id)
                if team_info and 'time' in team_info and isinstance(team_info['time'], dict):
                    time_data = team_info['time']
                    if not final_team_name and 'nome' in time_data:
                        final_team_name = time_data['nome']
            except Exception as e:
                print(f"Erro ao buscar informações do time da API: {e}")
                # Continuar mesmo se não conseguir buscar dados
            
            # Atualizar time com nome
            from models.teams import update_team
            if final_team_name != team_name:
                update_team(conn, temp_id, user['id'], team_name=final_team_name)
            
            # Se não houver time selecionado, selecionar o novo
            if not session.get('selected_team_id'):
                session['selected_team_id'] = temp_id
            
            flash('Time associado com sucesso!', 'success')
            return redirect(url_for('credenciais'))
        except Exception as e:
            flash(f'Erro ao associar credenciais: {str(e)}', 'error')
            import traceback
            traceback.print_exc()
        finally:
            close_db_connection(conn)
    
    return render_template('associar_credenciais.html', current_user=user)

@app.route('/pagina-inicial')
@login_required
def pagina_inicial():
    """Página inicial com seleção de perfis de peso de jogo e peso SG"""
    user = get_current_user()
    
    from models.teams import create_teams_table
    conn = get_db_connection()
    try:
        create_teams_table(conn)
        times = get_all_user_teams(conn, user['id'])
        if not times or len(times) == 0:
            flash('Por favor, associe suas credenciais do Cartola primeiro.', 'warning')
            return redirect(url_for('associar_credenciais'))
    finally:
        close_db_connection(conn)
    
    # Buscar perfis disponíveis de peso de jogo com rankings (top 3 clubes)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Buscar rodada atual
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        # Buscar partidas da rodada atual para identificar adversários
        cursor.execute('''
            SELECT clube_casa_id, clube_visitante_id
            FROM acf_partidas
            WHERE rodada_id = %s AND valida = TRUE
        ''', (rodada_atual,))
        partidas = cursor.fetchall()
        
        # Criar dicionário de adversários: {clube_id: adversario_id}
        adversarios_dict = {}
        for casa_id, visitante_id in partidas:
            adversarios_dict[casa_id] = visitante_id
            adversarios_dict[visitante_id] = casa_id
        
        # Buscar perfis de peso de jogo com top 3 clubes
        cursor.execute('''
            SELECT DISTINCT pj.perfil_id, pj.ultimas_partidas
            FROM acp_peso_jogo_perfis pj
            WHERE pj.rodada_atual = %s
            ORDER BY pj.perfil_id
            LIMIT 10
        ''', (rodada_atual,))
        perfis_raw = cursor.fetchall()
        
        perfis_peso_jogo = []
        for perfil_id, ultimas_partidas in perfis_raw:
            # Buscar TODOS os clubes para este perfil (ordenados por peso)
            cursor.execute('''
                SELECT clube_id, peso_jogo
                FROM acp_peso_jogo_perfis
                WHERE perfil_id = %s AND rodada_atual = %s
                ORDER BY peso_jogo DESC
            ''', (perfil_id, rodada_atual))
            todos_clubes = cursor.fetchall()
            
            descricoes = {
                1: "Muito recente (foca nas últimas partidas)",
                2: "Recente (padrão atual)",
                3: "Médio (balanço entre recente e histórico)",
                4: "Mais histórico (considera mais partidas)",
                5: "Recente com peso crescente",
                6: "Histórico com peso crescente",
                7: "Análise intermediária",
                8: "Análise abrangente",
                9: "Análise profunda",
                10: "Análise completa"
            }
            
            top_clubes_list = []
            pesos_values = [row[1] for row in todos_clubes]
            peso_min = min(pesos_values) if pesos_values else 0
            peso_max = max(pesos_values) if pesos_values else 1
            
            for row in todos_clubes:
                clube_id = row[0]
                adversario_id = adversarios_dict.get(clube_id)
                peso_value = round(row[1], 2)
                
                # Calcular cor baseada na posição entre min e max (0 a 1)
                # Verde para valores altos, vermelho para valores baixos
                if peso_max > peso_min:
                    normalized = (peso_value - peso_min) / (peso_max - peso_min)
                else:
                    normalized = 1.0
                
                # Gerar cor: verde (0,255,0) para 1.0, vermelho (255,0,0) para 0.0
                red = int(255 * (1 - normalized))
                green = int(255 * normalized)
                color_hex = f"#{red:02x}{green:02x}00"
                
                top_clubes_list.append({
                    'clube_id': clube_id,
                    'peso_jogo': peso_value,
                    'peso_jogo_str': f"{peso_value:.2f}",
                    'adversario_id': adversario_id,
                    'peso_color': color_hex
                })
            
            perfis_peso_jogo.append({
                'perfil_id': perfil_id,
                'ultimas_partidas': ultimas_partidas,
                'top_clubes': top_clubes_list,
                'descricao': descricoes.get(perfil_id, f"Analisa as últimas {ultimas_partidas} partidas")
            })
        
        # Buscar perfis de peso SG com top 3 clubes
        cursor.execute('''
            SELECT DISTINCT ps.perfil_id, ps.ultimas_partidas
            FROM acp_peso_sg_perfis ps
            WHERE ps.rodada_atual = %s
            ORDER BY ps.perfil_id
            LIMIT 10
        ''', (rodada_atual,))
        perfis_raw = cursor.fetchall()
        
        perfis_peso_sg = []
        for perfil_id, ultimas_partidas in perfis_raw:
            # Buscar TODOS os clubes para este perfil (ordenados por peso)
            cursor.execute('''
                SELECT clube_id, peso_sg
                FROM acp_peso_sg_perfis
                WHERE perfil_id = %s AND rodada_atual = %s
                ORDER BY peso_sg DESC
            ''', (perfil_id, rodada_atual))
            todos_clubes = cursor.fetchall()
            
            top_clubes_list = []
            pesos_values = [row[1] for row in todos_clubes]
            peso_min = min(pesos_values) if pesos_values else 0
            peso_max = max(pesos_values) if pesos_values else 1
            
            for row in todos_clubes:
                clube_id = row[0]
                adversario_id = adversarios_dict.get(clube_id)
                peso_value = round(row[1], 2)
                
                # Calcular cor baseada na posição entre min e max (0 a 1)
                # Verde para valores altos, vermelho para valores baixos
                if peso_max > peso_min:
                    normalized = (peso_value - peso_min) / (peso_max - peso_min)
                else:
                    normalized = 1.0
                
                # Gerar cor: verde (0,255,0) para 1.0, vermelho (255,0,0) para 0.0
                red = int(255 * (1 - normalized))
                green = int(255 * normalized)
                color_hex = f"#{red:02x}{green:02x}00"
                
                top_clubes_list.append({
                    'clube_id': clube_id,
                    'peso_sg': peso_value,
                    'peso_sg_str': f"{peso_value:.2f}",
                    'adversario_id': adversario_id,
                    'peso_color': color_hex
                })
            
            perfis_peso_sg.append({
                'perfil_id': perfil_id,
                'ultimas_partidas': ultimas_partidas,
                'top_clubes': top_clubes_list,
                'descricao': descricoes.get(perfil_id, f"Analisa saldo de gols das últimas {ultimas_partidas} partidas")
            })
        
        # Buscar nomes dos clubes e escudos
        # Coletar todos os IDs de clubes que precisamos (dos perfis + adversários)
        clube_ids_set = set(adversarios_dict.keys()) | set(adversarios_dict.values())
        
        # Adicionar clubes dos perfis de peso de jogo
        for perfil in perfis_peso_jogo:
            for clube in perfil['top_clubes']:
                clube_ids_set.add(clube['clube_id'])
                if clube.get('adversario_id'):
                    clube_ids_set.add(clube['adversario_id'])
        
        # Adicionar clubes dos perfis de peso SG
        for perfil in perfis_peso_sg:
            for clube in perfil['top_clubes']:
                clube_ids_set.add(clube['clube_id'])
                if clube.get('adversario_id'):
                    clube_ids_set.add(clube['adversario_id'])
        
        # Buscar todos os clubes necessários
        if clube_ids_set:
            placeholders = ','.join(['%s'] * len(clube_ids_set))
            cursor.execute(f'SELECT id, nome, abreviacao FROM acf_clubes WHERE id IN ({placeholders})', list(clube_ids_set))
        else:
            cursor.execute('SELECT id, nome, abreviacao FROM acf_clubes LIMIT 50')
        clubes_data = cursor.fetchall()
        
        # Buscar escudos da API
        from utils.team_shields import get_team_shield
        clubes_dict = {}
        for row in clubes_data:
            clube_id = row[0]
            escudo_url = get_team_shield(clube_id, size='45x45')
            
            clubes_dict[clube_id] = {
                'nome': row[1], 
                'abreviacao': row[2],
                'escudo_url': escudo_url
            }
        
    except Exception as e:
        print(f"Erro ao buscar perfis: {e}")
        import traceback
        traceback.print_exc()
        perfis_peso_jogo = []
        perfis_peso_sg = []
        clubes_dict = {}
        rodada_atual = 1
    finally:
        close_db_connection(conn)
    
    # Buscar configuração padrão do usuário se existir
    from models.user_configurations import get_user_default_configuration, create_user_configurations_table
    conn = get_db_connection()
    try:
        create_user_configurations_table(conn)
        team_id = session.get('selected_team_id')
        config_default = get_user_default_configuration(conn, user['id'], team_id) if team_id else None
    finally:
        close_db_connection(conn)
    
    return render_template(
        'pagina_inicial.html',
        current_user=user,
        perfis_peso_jogo=perfis_peso_jogo,
        perfis_peso_sg=perfis_peso_sg,
        clubes_dict=clubes_dict,
        rodada_atual=rodada_atual,
        config_default=config_default
    )

@app.route('/salvar-configuracao-perfis', methods=['POST'])
@login_required
def salvar_configuracao_perfis():
    """Salva a configuração de perfis escolhidos pelo usuário"""
    user = get_current_user()
    
    perfil_peso_jogo = int(request.form.get('perfil_peso_jogo'))
    perfil_peso_sg = int(request.form.get('perfil_peso_sg'))
    
    from models.user_configurations import create_user_configuration, create_user_configurations_table
    
    # Obter team_id da sessão
    team_id = session.get('selected_team_id')
    if not team_id:
        flash('Selecione um time primeiro!', 'error')
        return redirect(url_for('credenciais'))
    
    conn = get_db_connection()
    try:
        create_user_configurations_table(conn)
        
        pesos_posicao = {
            'goleiro': {},
            'lateral': {},
            'zagueiro': {},
            'meia': {},
            'atacante': {},
            'treinador': {}
        }
        
        create_user_configuration(
            conn, user['id'], team_id, 'Configuração Padrão', 
            perfil_peso_jogo, perfil_peso_sg, pesos_posicao, is_default=True
        )
        
        flash('Perfis salvos com sucesso!', 'success')
        return redirect(url_for('modulos'))
    except Exception as e:
        flash(f'Erro ao salvar configuração: {str(e)}', 'error')
        return redirect(url_for('pagina_inicial'))
    finally:
        close_db_connection(conn)

@app.route('/credenciais')
@login_required
def credenciais():
    """Página para visualizar e gerenciar todos os times do usuário"""
    user = get_current_user()
    
    from models.teams import get_all_user_teams, create_teams_table
    from api_cartola import fetch_team_info_by_team_id
    conn = get_db_connection()
    try:
        create_teams_table(conn)
        all_times = get_all_user_teams(conn, user['id'])
        
        # Buscar escudos dinamicamente para cada time
        for time in all_times:
            time['team_shield_url'] = None
            try:
                team_info = fetch_team_info_by_team_id(conn, time['id'])
                if team_info and 'time' in team_info and isinstance(team_info['time'], dict):
                    time_data = team_info['time']
                    # Priorizar url_escudo_png, depois url_escudo_svg, depois foto_perfil
                    if 'url_escudo_png' in time_data:
                        time['team_shield_url'] = time_data['url_escudo_png']
                    elif 'url_escudo_svg' in time_data:
                        time['team_shield_url'] = time_data['url_escudo_svg']
                    elif 'foto_perfil' in time_data:
                        time['team_shield_url'] = time_data['foto_perfil']
            except Exception as e:
                print(f"Erro ao buscar escudo do time {time['id']}: {e}")
    finally:
        close_db_connection(conn)
    
    return render_template('credenciais.html', current_user=user, all_times=all_times)

@app.route('/credenciais/editar/<int:time_id>', methods=['GET', 'POST'])
@login_required
def editar_credenciais(time_id):
    """Editar credenciais de um time específico"""
    user = get_current_user()
    
    from models.teams import get_all_user_teams, create_teams_table
    conn = get_db_connection()
    
    try:
        create_teams_table(conn)
        
        # Verificar se o time pertence ao usuário
        all_times = get_all_user_teams(conn, user['id'])
        time_to_edit = next((t for t in all_times if t['id'] == time_id), None)
        
        if not time_to_edit:
            flash('Time não encontrado ou não pertence ao usuário', 'error')
            return redirect(url_for('credenciais'))
        
        if request.method == 'POST':
            # Atualizar credenciais
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE acw_teams
                SET access_token = %s,
                    refresh_token = %s,
                    id_token = %s,
                    team_name = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
            ''', (
                request.form.get('access_token', '').strip(),
                request.form.get('refresh_token', '').strip(),
                request.form.get('id_token', '').strip() or None,
                request.form.get('team_name', '').strip() or None,
                time_id,
                user['id']
            ))
            conn.commit()
            flash('Credenciais atualizadas com sucesso!', 'success')
            return redirect(url_for('credenciais'))
        
        # GET - mostrar formulário
        return render_template('editar_credenciais.html', current_user=user, credenciais=time_to_edit)
    finally:
        close_db_connection(conn)

@app.route('/modulos')
@login_required
def modulos():
    """Página principal dos módulos individuais"""
    # Verificar se há time selecionado
    team_id = session.get('selected_team_id')
    if not team_id:
        flash('Associe um time primeiro para acessar os módulos', 'warning')
        return redirect(url_for('credenciais'))
    return render_template('modulos.html')

@app.route('/modulos/<modulo>')
@login_required
def modulo_individual(modulo):
    """Página individual de cada módulo (goleiro, lateral, etc)"""
    # Validar se o módulo é válido (apenas módulos de posição)
    modulos_validos = ['goleiro', 'lateral', 'zagueiro', 'meia', 'atacante', 'treinador']
    if modulo not in modulos_validos:
        flash('Módulo inválido', 'error')
        return redirect(url_for('modulos'))
    
    # Buscar rodada atual
    conn = get_db_connection()
    rodada_atual = 1
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
    finally:
        close_db_connection(conn)
    
    # Buscar pesos atuais do módulo
    from utils.weights import get_weight
    defaults_goleiro = {
        'FATOR_MEDIA': 0.2,
        'FATOR_FF': 4.5,
        'FATOR_FD': 6.5,
        'FATOR_SG': 1.5,
        'FATOR_PESO_JOGO': 1.5,
        'FATOR_GOL_ADVERSARIO': 2.0
    }
    
    # Buscar pesos salvos ou usar defaults
    pesos_atuais = {}
    for key, default in defaults_goleiro.items():
        pesos_atuais[key] = float(get_weight(modulo, key, default))
    
    # Renderizar template específico para cada módulo
    template_map = {
        'goleiro': 'modulo_goleiro.html',
        'lateral': 'modulo_lateral.html',
        'zagueiro': 'modulo_zagueiro.html',
        'meia': 'modulo_meia.html',
        'atacante': 'modulo_atacante.html',
        'treinador': 'modulo_treinador.html'
    }
    
    template_name = template_map.get(modulo, 'modulo_goleiro.html')
    
    return render_template(template_name, 
                         modulo=modulo, 
                         rodada_atual=rodada_atual,
                         pesos_atuais=pesos_atuais)

@app.route('/modulos/<modulo>/recalcular')
@login_required
def recalcular_modulo(modulo):
    """Endpoint para recalcular um módulo específico"""
    # Por enquanto apenas redireciona de volta (funcionalidade será implementada)
    flash('Funcionalidade de recálculo será implementada em breve', 'info')
    return redirect(url_for('modulo_individual', modulo=modulo))

@app.route('/api/modulos/<modulo>/verificar-ranking', methods=['GET'])
@login_required
def api_verificar_ranking(modulo):
    """API rápida para verificar se há ranking salvo antes de buscar todos os dados"""
    from flask import jsonify
    user = get_current_user()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Buscar rodada atual
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        # Obter team_id da sessão
        team_id = session.get('selected_team_id')
        if not team_id:
            return jsonify({'has_ranking': False})
        
        # Buscar configuração do usuário para este time
        from models.user_configurations import get_user_default_configuration
        config = get_user_default_configuration(conn, user['id'], team_id)
        
        if not config:
            return jsonify({'has_ranking': False})
        
        # Validar módulo
        posicao_map = {
            'goleiro': 1, 'lateral': 2, 'zagueiro': 3, 'meia': 4, 'atacante': 5, 'treinador': 6
        }
        posicao_id = posicao_map.get(modulo)
        
        if not posicao_id:
            return jsonify({'has_ranking': False})
        
        # Verificar se há ranking salvo
        from models.user_rankings import get_team_rankings
        
        rankings = get_team_rankings(
            conn, 
            user['id'],
            team_id=team_id,
            configuration_id=config.get('id'),
            posicao_id=posicao_id,
            rodada_atual=rodada_atual
        )
        
        if rankings:
            ranking_salvo = rankings[0]
            ranking_data = ranking_salvo.get('ranking_data', [])
            
            if isinstance(ranking_data, dict):
                ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
            elif not isinstance(ranking_data, list):
                ranking_data = []
            
            has_ranking = isinstance(ranking_data, list) and len(ranking_data) > 0
            
            if has_ranking:
                return jsonify({
                    'has_ranking': True,
                    'rodada_atual': rodada_atual,
                    'ranking_count': len(ranking_data)
                })
        
        # Tentar sem configuration_id
        rankings_sem_config = get_team_rankings(
            conn, 
            user['id'], 
            configuration_id=None,
            posicao_id=posicao_id,
            rodada_atual=rodada_atual
        )
        
        if rankings_sem_config:
            ranking_dict = rankings_sem_config[0]
            ranking_data = ranking_dict.get('ranking_data', [])
            
            if isinstance(ranking_data, dict):
                ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
            elif not isinstance(ranking_data, list):
                ranking_data = []
            
            has_ranking = isinstance(ranking_data, list) and len(ranking_data) > 0
            
            if has_ranking:
                return jsonify({
                    'has_ranking': True,
                    'rodada_atual': rodada_atual,
                    'ranking_count': len(ranking_data)
                })
        
        return jsonify({'has_ranking': False})
        
    except Exception as e:
        print(f"Erro ao verificar ranking: {e}")
        return jsonify({'has_ranking': False})
    finally:
        close_db_connection(conn)

@app.route('/api/modulos/<modulo>/salvar-ranking', methods=['POST'])
@login_required
def api_salvar_ranking(modulo):
    """API para salvar ranking calculado pelo frontend"""
    from flask import jsonify, request
    user = get_current_user()
    
    try:
        data = request.get_json()
        ranking_data = data.get('ranking_data')
        rodada_atual = data.get('rodada_atual')
        configuration_id = data.get('configuration_id')
        
        if not ranking_data or not rodada_atual:
            return jsonify({'error': 'Dados incompletos'}), 400
        
        # Validar módulo
        posicao_map = {
            'goleiro': 1, 'lateral': 2, 'zagueiro': 3, 'meia': 4, 'atacante': 5, 'treinador': 6
        }
        posicao_id = posicao_map.get(modulo)
        
        if not posicao_id:
            return jsonify({'error': 'Módulo inválido'}), 400
        
        # Obter team_id da sessão
        team_id = session.get('selected_team_id')
        if not team_id:
            return jsonify({'error': 'Nenhum time selecionado'}), 400
        
        # Salvar ranking
        conn = get_db_connection()
        try:
            from models.user_rankings import save_team_ranking
            ranking_id = save_team_ranking(
                conn,
                user['id'],
                team_id,
                configuration_id if configuration_id else None,
                posicao_id,
                rodada_atual,
                ranking_data
            )
            print(f"[RANKING SALVO] Usuário {user['id']}, Módulo {modulo}, Rodada {rodada_atual}, ID: {ranking_id}")
            return jsonify({'success': True, 'ranking_id': ranking_id, 'message': 'Ranking salvo com sucesso'})
        finally:
            close_db_connection(conn)
            
    except Exception as e:
        print(f"Erro ao salvar ranking: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/modulos/<modulo>/pesos', methods=['POST'])
@login_required
def api_salvar_pesos(modulo):
    """API para salvar pesos de um módulo específico por time"""
    from flask import jsonify, request
    user = get_current_user()
    
    try:
        pesos = request.get_json()
        
        # Validar módulo
        modulos_validos = ['goleiro', 'lateral', 'zagueiro', 'meia', 'atacante', 'treinador']
        if modulo not in modulos_validos:
            return jsonify({'error': 'Módulo inválido'}), 400
        
        # Obter time selecionado
        team_id = session.get('selected_team_id')
        if not team_id:
            return jsonify({'error': 'Nenhum time selecionado. Selecione um time primeiro.'}), 400
        
        # Salvar pesos no banco
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Verificar se existe registro
            cursor.execute('''
                SELECT id FROM acw_posicao_weights 
                WHERE user_id = %s AND team_id = %s AND posicao = %s
            ''', (user['id'], team_id, modulo))
            existing = cursor.fetchone()
            
            if existing:
                # Atualizar
                cursor.execute('''
                    UPDATE acw_posicao_weights 
                    SET weights_json = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND team_id = %s AND posicao = %s
                ''', (json.dumps(pesos, ensure_ascii=False), user['id'], team_id, modulo))
            else:
                # Inserir
                cursor.execute('''
                    INSERT INTO acw_posicao_weights (user_id, team_id, posicao, weights_json)
                    VALUES (%s, %s, %s, %s)
                ''', (user['id'], team_id, modulo, json.dumps(pesos, ensure_ascii=False)))
            
            conn.commit()
            return jsonify({'success': True, 'message': 'Pesos salvos com sucesso'})
        finally:
            close_db_connection(conn)
            
    except Exception as e:
        print(f"Erro ao salvar pesos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/modulos/<modulo>/dados')
@login_required
def api_modulo_dados(modulo):
    """API para fornecer dados necessários para cálculos JavaScript"""
    from flask import jsonify
    user = get_current_user()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Buscar rodada atual
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        # Buscar configuração do usuário
        from models.user_configurations import get_user_default_configuration
        config = get_user_default_configuration(conn, user['id'])
        
        if not config:
            return jsonify({'error': 'Nenhuma configuração encontrada. Configure os perfis primeiro.'}), 400
        
        # Buscar partidas da rodada atual
        cursor.execute('''
            SELECT clube_casa_id, clube_visitante_id
            FROM acf_partidas
            WHERE rodada_id = %s AND valida = TRUE
        ''', (rodada_atual,))
        partidas = cursor.fetchall()
        
        adversarios_dict = {}
        for casa_id, visitante_id in partidas:
            adversarios_dict[casa_id] = visitante_id
            adversarios_dict[visitante_id] = casa_id
        
        # Buscar dados de atletas baseado no módulo
        posicao_map = {
            'goleiro': 1,
            'lateral': 2,
            'zagueiro': 3,
            'meia': 4,
            'atacante': 5,
            'treinador': 6
        }
        
        posicao_id = posicao_map.get(modulo)
        
        if not posicao_id:
            return jsonify({'error': 'Módulo inválido'}), 400
        
        # Buscar atletas com dados necessários (sem peso_jogo e peso_sg, eles vêm das tabelas de perfis)
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.pontos_num, a.media_num, 
                   a.preco_num, a.jogos_num, c.nome as clube_nome,
                   c.abreviacao as clube_abrev
            FROM acf_atletas a
            JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.posicao_id = %s AND a.status_id = 7
        ''', (posicao_id,))
        atletas_raw = cursor.fetchall()
        
        # Buscar peso_jogo e peso_sg das tabelas de perfis baseado na configuração do usuário
        perfil_peso_jogo = config['perfil_peso_jogo']
        perfil_peso_sg = config['perfil_peso_sg']
        
        # Buscar peso_jogo para todos os clubes dos atletas
        clube_ids = []
        if atletas_raw:
            clube_ids = [row[2] for row in atletas_raw if len(row) > 2]  # clube_id é o terceiro campo
        
        peso_jogo_dict = {}
        if clube_ids and len(clube_ids) > 0 and perfil_peso_jogo:
            try:
                placeholders = ','.join(['%s'] * len(clube_ids))
                cursor.execute(f'''
                    SELECT clube_id, peso_jogo
                    FROM acp_peso_jogo_perfis
                    WHERE perfil_id = %s AND rodada_atual = %s AND clube_id IN ({placeholders})
                ''', [perfil_peso_jogo, rodada_atual] + clube_ids)
                
                for row in cursor.fetchall():
                    if row and len(row) >= 2:
                        clube_id, peso_jogo = row
                        peso_jogo_dict[clube_id] = float(peso_jogo) if peso_jogo else 0
            except Exception as e:
                print(f"Erro ao buscar peso_jogo: {e}")
        
        # Buscar peso_sg para todos os clubes dos atletas
        peso_sg_dict = {}
        if clube_ids and len(clube_ids) > 0 and perfil_peso_sg:
            try:
                placeholders = ','.join(['%s'] * len(clube_ids))
                cursor.execute(f'''
                    SELECT clube_id, peso_sg
                    FROM acp_peso_sg_perfis
                    WHERE perfil_id = %s AND rodada_atual = %s AND clube_id IN ({placeholders})
                ''', [perfil_peso_sg, rodada_atual] + clube_ids)
                
                for row in cursor.fetchall():
                    if row and len(row) >= 2:
                        clube_id, peso_sg = row
                        peso_sg_dict[clube_id] = float(peso_sg) if peso_sg else 0
            except Exception as e:
                print(f"Erro ao buscar peso_sg: {e}")
        
        # Buscar escudos
        from utils.team_shields import get_team_shield
        
        atletas = []
        for row in atletas_raw:
            if not row or len(row) < 9:
                continue
            try:
                atleta_id, apelido, clube_id, pontos, media, preco, jogos, clube_nome, clube_abrev = row
                escudo_url = get_team_shield(clube_id, size='45x45')
                adversario_id = adversarios_dict.get(clube_id)
                
                atletas.append({
                    'atleta_id': atleta_id,
                    'apelido': apelido,
                    'clube_id': clube_id,
                    'clube_nome': clube_nome,
                    'clube_abrev': clube_abrev,
                    'clube_escudo_url': escudo_url,
                    'pontos_num': float(pontos) if pontos else 0,
                    'media_num': float(media) if media else 0,
                    'preco_num': float(preco) if preco else 0,
                    'jogos_num': int(jogos) if jogos else 0,
                    'peso_jogo': peso_jogo_dict.get(clube_id, 0),
                    'peso_sg': peso_sg_dict.get(clube_id, 0),
                    'adversario_id': adversario_id
                })
            except Exception as e:
                print(f"Erro ao processar atleta: {e}, row: {row}")
                continue
        
        # Buscar dados de pontuados para cálculos
        # 1. Buscar médias de scouts por atleta
        atleta_ids = [a['atleta_id'] for a in atletas]
        pontuados_data = {}
        
        if atleta_ids:
            placeholders = ','.join(['%s'] * len(atleta_ids))
            try:
                cursor.execute(f'''
                    SELECT atleta_id, 
                           AVG(scout_ds) as avg_ds,
                           AVG(scout_ff) as avg_ff, 
                           AVG(scout_fd) as avg_fd,
                           AVG(scout_fs) as avg_fs,
                           AVG(scout_g) as avg_g,
                           AVG(scout_a) as avg_a
                    FROM acf_pontuados
                    WHERE atleta_id IN ({placeholders}) AND rodada_id <= %s AND entrou_em_campo = TRUE
                    GROUP BY atleta_id
                ''', atleta_ids + [rodada_atual - 1])
                
                for row in cursor.fetchall():
                    if row and len(row) >= 7:
                        atleta_id, avg_ds, avg_ff, avg_fd, avg_fs, avg_g, avg_a = row
                        pontuados_data[atleta_id] = {
                            'avg_ds': float(avg_ds) if avg_ds else 0,
                            'avg_ff': float(avg_ff) if avg_ff else 0,
                            'avg_fd': float(avg_fd) if avg_fd else 0,
                            'avg_fs': float(avg_fs) if avg_fs else 0,
                            'avg_g': float(avg_g) if avg_g else 0,
                            'avg_a': float(avg_a) if avg_a else 0
                        }
            except Exception as e:
                print(f"Erro ao buscar dados de pontuados por atleta: {e}")
        
        # 2. Buscar médias de desarmes cedidos por adversários (por posição)
        if adversarios_dict and posicao_id:
            adversario_ids = list(set(adversarios_dict.values()))
            if adversario_ids and len(adversario_ids) > 0:
                placeholders = ','.join(['%s'] * len(adversario_ids))
                try:
                    # Buscar média de desarmes cedidos pelos adversários para esta posição
                    cursor.execute(f'''
                        SELECT p.clube_id, AVG(p.scout_ds) as avg_ds_cedidos
                        FROM acf_pontuados p
                        JOIN acf_partidas pt ON p.rodada_id = pt.rodada_id
                        WHERE p.posicao_id = %s 
                          AND ((pt.clube_casa_id IN ({placeholders}) AND p.clube_id = pt.clube_visitante_id)
                               OR (pt.clube_visitante_id IN ({placeholders}) AND p.clube_id = pt.clube_casa_id))
                          AND p.rodada_id <= %s AND p.entrou_em_campo = TRUE
                        GROUP BY p.clube_id
                    ''', [posicao_id] + adversario_ids + adversario_ids + [rodada_atual - 1])
                    
                    for row in cursor.fetchall():
                        if row and len(row) >= 2:
                            clube_id, avg_ds_cedidos = row
                            if clube_id not in pontuados_data:
                                pontuados_data[clube_id] = {}
                            pontuados_data[clube_id]['avg_ds_cedidos'] = float(avg_ds_cedidos) if avg_ds_cedidos else 0
                except Exception as e:
                    print(f"Erro ao buscar desarmes cedidos por adversários: {e}")
        
        # 3. Buscar escalações (top 20 destaques)
        escalacoes_data = {}
        try:
            cursor.execute('''
                SELECT atleta_id, escalacoes
                FROM acf_destaques
                ORDER BY escalacoes DESC
                LIMIT 20
            ''')
            for row in cursor.fetchall():
                if row and len(row) >= 2:
                    atleta_id, escalacoes = row
                    escalacoes_data[atleta_id] = float(escalacoes) if escalacoes else 0
        except Exception as e:
            print(f"Erro ao buscar escalações: {e}")
        
        # Buscar dados de partidas para média de gols
        gols_data = {}
        if adversarios_dict:
            adversario_ids = list(set(adversarios_dict.values()))
            if adversario_ids and len(adversario_ids) > 0:
                placeholders = ','.join(['%s'] * len(adversario_ids))
                try:
                    # Query simplificada: buscar gols marcados por cada clube adversário
                    cursor.execute(f'''
                        SELECT 
                            clube_casa_id as clube_id,
                            SUM(placar_oficial_mandante) as gols_marcados,
                            COUNT(*) as jogos
                        FROM acf_partidas
                        WHERE clube_casa_id IN ({placeholders})
                          AND rodada_id < %s AND valida = TRUE 
                          AND placar_oficial_mandante IS NOT NULL
                        GROUP BY clube_casa_id
                    ''', adversario_ids + [rodada_atual])
                    
                    for row in cursor.fetchall():
                        if row and len(row) >= 3:
                            clube_id, gols_marcados, jogos = row
                            if jogos and jogos > 0:
                                gols_data[clube_id] = {
                                    'gols_marcados': float(gols_marcados) if gols_marcados else 0,
                                    'jogos': int(jogos),
                                    'media_gols': float(gols_marcados) / float(jogos) if jogos > 0 else 0
                                }
                    
                    # Também buscar para clubes visitantes
                    cursor.execute(f'''
                        SELECT 
                            clube_visitante_id as clube_id,
                            SUM(placar_oficial_visitante) as gols_marcados,
                            COUNT(*) as jogos
                        FROM acf_partidas
                        WHERE clube_visitante_id IN ({placeholders})
                          AND rodada_id < %s AND valida = TRUE 
                          AND placar_oficial_visitante IS NOT NULL
                        GROUP BY clube_visitante_id
                    ''', adversario_ids + [rodada_atual])
                    
                    for row in cursor.fetchall():
                        if row and len(row) >= 3:
                            clube_id, gols_marcados, jogos = row
                            if clube_id in gols_data:
                                # Somar aos dados existentes
                                gols_data[clube_id]['gols_marcados'] += float(gols_marcados) if gols_marcados else 0
                                gols_data[clube_id]['jogos'] += int(jogos)
                                total_jogos = gols_data[clube_id]['jogos']
                                gols_data[clube_id]['media_gols'] = gols_data[clube_id]['gols_marcados'] / total_jogos if total_jogos > 0 else 0
                            elif jogos and jogos > 0:
                                gols_data[clube_id] = {
                                    'gols_marcados': float(gols_marcados) if gols_marcados else 0,
                                    'jogos': int(jogos),
                                    'media_gols': float(gols_marcados) / float(jogos) if jogos > 0 else 0
                                }
                except Exception as e:
                    print(f"Erro ao buscar dados de gols: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Buscar nomes dos clubes adversários
        clubes_dict = {}
        if adversarios_dict:
            todos_clube_ids = set(adversarios_dict.keys()) | set(adversarios_dict.values())
            if todos_clube_ids:
                placeholders = ','.join(['%s'] * len(todos_clube_ids))
                cursor.execute(f'''
                    SELECT id, nome, abreviacao
                    FROM acf_clubes
                    WHERE id IN ({placeholders})
                ''', list(todos_clube_ids))
                
                for row in cursor.fetchall():
                    clube_id, nome, abreviacao = row
                    escudo_url = get_team_shield(clube_id, size='45x45')
                    clubes_dict[clube_id] = {
                        'nome': nome,
                        'abreviacao': abreviacao,
                        'escudo_url': escudo_url
                    }
        
        # Adicionar nome do adversário aos atletas
        for atleta in atletas:
            if atleta['adversario_id'] and atleta['adversario_id'] in clubes_dict:
                atleta['adversario_nome'] = clubes_dict[atleta['adversario_id']]['nome']
            else:
                atleta['adversario_nome'] = 'N/A'
        
        # Buscar pesos do módulo
        from utils.weights import get_weight
        
        # Defaults por posição
        defaults_posicao = {
            'goleiro': {
                'FATOR_MEDIA': 0.2, 'FATOR_FF': 4.5, 'FATOR_FD': 6.5, 'FATOR_SG': 1.5,
                'FATOR_PESO_JOGO': 1.5, 'FATOR_GOL_ADVERSARIO': 2.0
            },
            'lateral': {
                'FATOR_MEDIA': 3.0, 'FATOR_DS': 8.0, 'FATOR_SG': 2.0, 'FATOR_ESCALACAO': 10.0,
                'FATOR_FF': 2.0, 'FATOR_FS': 1.0, 'FATOR_FD': 2.0, 'FATOR_G': 4.0,
                'FATOR_A': 4.0, 'FATOR_PESO_JOGO': 1.0
            },
            'zagueiro': {
                'FATOR_MEDIA': 1.5, 'FATOR_DS': 4.5, 'FATOR_SG': 4.0, 'FATOR_ESCALACAO': 5.0,
                'FATOR_PESO_JOGO': 5.0
            },
            'meia': {
                'FATOR_MEDIA': 1.0, 'FATOR_DS': 3.6, 'FATOR_FF': 0.7, 'FATOR_FS': 0.8,
                'FATOR_FD': 0.9, 'FATOR_G': 2.5, 'FATOR_A': 2.0, 'FATOR_ESCALACAO': 10.0,
                'FATOR_PESO_JOGO': 9.5
            },
            'atacante': {
                'FATOR_MEDIA': 2.5, 'FATOR_DS': 2.0, 'FATOR_FF': 1.2, 'FATOR_FS': 1.3,
                'FATOR_FD': 1.3, 'FATOR_G': 2.5, 'FATOR_A': 2.5, 'FATOR_ESCALACAO': 10.0,
                'FATOR_PESO_JOGO': 10.0
            },
            'treinador': {
                'FATOR_PESO_JOGO': 1.0
            }
        }
        
        defaults_modulo = defaults_posicao.get(modulo, defaults_posicao['goleiro'])
        
        # Buscar pesos do time selecionado
        team_id = session.get('selected_team_id')
        if not team_id:
            return jsonify({'error': 'Nenhum time selecionado. Selecione um time primeiro.'}), 400
        
        # Buscar pesos salvos para este time e módulo
        cursor.execute('''
            SELECT weights_json FROM acw_posicao_weights
            WHERE user_id = %s AND team_id = %s AND posicao = %s
        ''', (user['id'], team_id, modulo))
        peso_row = cursor.fetchone()
        
        if peso_row and peso_row[0]:
            pesos_salvos = peso_row[0] if isinstance(peso_row[0], dict) else json.loads(peso_row[0])
        else:
            # Buscar pesos do JSONB de configuração do usuário, ou usar defaults
            pesos_posicao = config.get('pesos_posicao', {})
            pesos_salvos = pesos_posicao.get(modulo, {})
        
        pesos = {}
        for key, default in defaults_modulo.items():
            pesos[key] = float(pesos_salvos.get(key, default))
        
        # Verificar se já existe ranking salvo para esta rodada e módulo
        from models.user_rankings import get_team_rankings
        posicao_map = {
            'goleiro': 1, 'lateral': 2, 'zagueiro': 3, 'meia': 4, 'atacante': 5, 'treinador': 6
        }
        posicao_id = posicao_map.get(modulo)
        
        ranking_salvo = None
        if posicao_id:
            rankings = get_team_rankings(
                conn, 
                user['id'],
                team_id=team_id,
                configuration_id=config.get('id'),
                posicao_id=posicao_id,
                rodada_atual=rodada_atual
            )
            if rankings:
                ranking_salvo = rankings[0]  # Pegar o mais recente
                # Converter ranking_data para lista se for dict
                ranking_data = ranking_salvo.get('ranking_data', [])
                # Garantir que seja uma lista
                if isinstance(ranking_data, dict):
                    # Se for dict, tentar extrair lista
                    ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
                elif not isinstance(ranking_data, list):
                    ranking_data = []
                ranking_salvo = ranking_data if (isinstance(ranking_data, list) and len(ranking_data) > 0) else None
                if ranking_salvo:
                    print(f"[API] ✅ Ranking encontrado com configuration_id - tamanho: {len(ranking_data)}")
                else:
                    print(f"[API] ⚠️ Ranking encontrado mas vazio ou formato incorreto - tipo: {type(ranking_data)}")
            
            # Se não encontrou com configuration_id, tentar buscar sem (para compatibilidade)
            if not ranking_salvo:
                rankings_sem_config = get_team_rankings(
                    conn, 
                    user['id'],
                    team_id=team_id,
                    configuration_id=None,
                    posicao_id=posicao_id,
                    rodada_atual=rodada_atual
                )
                if rankings_sem_config:
                    ranking_dict = rankings_sem_config[0]
                    ranking_data = ranking_dict.get('ranking_data', [])
                    # Garantir que seja uma lista
                    if isinstance(ranking_data, dict):
                        ranking_data = ranking_data.get('ranking', ranking_data.get('resultados', []))
                    elif not isinstance(ranking_data, list):
                        ranking_data = []
                    ranking_salvo = ranking_data if (isinstance(ranking_data, list) and len(ranking_data) > 0) else None
                    if ranking_salvo:
                        print(f"[API] ✅ Ranking encontrado sem configuration_id - tamanho: {len(ranking_data)}")
        
        # Log final decisivo
        if ranking_salvo and isinstance(ranking_salvo, list) and len(ranking_salvo) > 0:
            print(f"[API] ✅✅✅ Ranking salvo VÁLIDO encontrado: {len(ranking_salvo)} itens - NÃO VAI CALCULAR")
            print(f"[API] Primeiro item do ranking: {ranking_salvo[0] if ranking_salvo else 'N/A'}")
        else:
            print("[API] ❌❌❌ Nenhum ranking salvo encontrado ou inválido - VAI CALCULAR AUTOMATICAMENTE")
            ranking_salvo = None  # Garantir que seja None se inválido
        
        # Garantir que ranking_salvo seja uma lista ou None antes de retornar
        ranking_para_json = ranking_salvo if (ranking_salvo and isinstance(ranking_salvo, list) and len(ranking_salvo) > 0) else None
        
        print(f"[API] Retornando ranking_salvo para JSON: tipo={type(ranking_para_json)}, tamanho={len(ranking_para_json) if ranking_para_json else 0}")
        
        return jsonify({
            'rodada_atual': rodada_atual,
            'perfil_peso_jogo': config['perfil_peso_jogo'],
            'perfil_peso_sg': config['perfil_peso_sg'],
            'atletas': atletas,
            'adversarios_dict': adversarios_dict,
            'clubes_dict': clubes_dict,
            'pontuados_data': pontuados_data,
            'gols_data': gols_data,
            'escalacoes_data': escalacoes_data,
            'pesos': pesos,
            'ranking_salvo': ranking_para_json,  # Usar versão validada
            'configuration_id': config.get('id')
        })
        
    except Exception as e:
        print(f"Erro ao buscar dados do módulo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/modulos/escalacao-ideal')
@login_required
def modulo_escalacao_ideal():
    """Página do módulo de escalação ideal"""
    # Verificar se há time selecionado
    team_id = session.get('selected_team_id')
    if not team_id:
        flash('Selecione um time primeiro na sidebar para calcular a escalação ideal', 'warning')
        return redirect(url_for('modulos'))
    return render_template('modulo_escalacao_ideal.html')

@app.route('/api/credenciais/lista')
@login_required
def api_credenciais_lista():
    """API para listar todas as credenciais (times) de um usuário"""
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        from models.teams import get_all_user_teams, create_teams_table
        create_teams_table(conn)
        
        times = get_all_user_teams(conn, user['id'])
        selected_id = session.get('selected_team_id')
        
        # Se não houver time selecionado e houver times disponíveis, selecionar o primeiro
        if not selected_id and times and len(times) > 0:
            selected_id = times[0]['id']
            session['selected_team_id'] = selected_id
        
        # Buscar escudos dinamicamente para cada time
        from api_cartola import fetch_team_info_by_team_id
        times_list = []
        for time in times:
            team_shield_url = None
            try:
                team_info = fetch_team_info_by_team_id(conn, time['id'])
                if team_info and 'time' in team_info and isinstance(team_info['time'], dict):
                    time_data = team_info['time']
                    # Priorizar url_escudo_png, depois url_escudo_svg, depois foto_perfil
                    if 'url_escudo_png' in time_data:
                        team_shield_url = time_data['url_escudo_png']
                    elif 'url_escudo_svg' in time_data:
                        team_shield_url = time_data['url_escudo_svg']
                    elif 'foto_perfil' in time_data:
                        team_shield_url = time_data['foto_perfil']
            except Exception as e:
                print(f"Erro ao buscar escudo do time {time['id']}: {e}")
            
            times_list.append({
                'id': time['id'],
                'team_name': time['team_name'] or f"Time {time['id']}",
                'team_shield_url': team_shield_url,
                'created_at': time['created_at'].isoformat() if time['created_at'] else None,
                'selected': time['id'] == selected_id
            })
        
        return jsonify({
            'times': times_list,
            'selected_id': selected_id
        })
    except Exception as e:
        print(f"Erro ao listar credenciais: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/time/selecionar', methods=['POST'])
@login_required
def api_selecionar_time():
    """API para selecionar o time ativo"""
    user = get_current_user()
    data = request.get_json()
    team_id = data.get('team_id')
    
    if not team_id:
        return jsonify({'error': 'team_id é obrigatório'}), 400
    
    # Verificar se o time pertence ao usuário
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM acw_teams
            WHERE id = %s AND user_id = %s
        ''', (team_id, user['id']))
        
        if not cursor.fetchone():
            return jsonify({'error': 'Time não encontrado ou não pertence ao usuário'}), 404
        
        session['selected_team_id'] = team_id
        return jsonify({'success': True, 'selected_id': team_id})
    except Exception as e:
        print(f"Erro ao selecionar time: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/time/<int:team_id>/escudo')
@login_required
def api_time_escudo(team_id):
    """API para buscar o escudo de um time dinamicamente"""
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        from models.teams import get_team
        from api_cartola import fetch_team_info_by_team_id
        
        # Verificar se o time pertence ao usuário
        team = get_team(conn, team_id, user['id'])
        if not team:
            return jsonify({'error': 'Time não encontrado ou não pertence ao usuário'}), 404
        
        # Buscar informações do time
        team_info = fetch_team_info_by_team_id(conn, team_id)
        
        if not team_info or 'time' not in team_info:
            return jsonify({'team_shield_url': None})
        
        time_data = team_info['time']
        team_shield_url = None
        
        # Priorizar url_escudo_png, depois url_escudo_svg, depois foto_perfil
        if 'url_escudo_png' in time_data:
            team_shield_url = time_data['url_escudo_png']
        elif 'url_escudo_svg' in time_data:
            team_shield_url = time_data['url_escudo_svg']
        elif 'foto_perfil' in time_data:
            team_shield_url = time_data['foto_perfil']
        
        return jsonify({'team_shield_url': team_shield_url})
    except Exception as e:
        print(f"Erro ao buscar escudo do time: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/time/atualizar-tokens/<int:team_id>', methods=['POST'])
@login_required
def api_atualizar_tokens(team_id):
    """API para atualizar tokens de um time (testa e atualiza se necessário)"""
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        from models.teams import get_team, update_team
        from api_cartola import fetch_team_data_by_team_id, refresh_access_token_by_team_id
        
        # Verificar se o time pertence ao usuário
        team = get_team(conn, team_id, user['id'])
        if not team:
            return jsonify({'error': 'Time não encontrado ou não pertence ao usuário'}), 404
        
        # Tentar buscar dados do time (isso já testa os tokens)
        from api_cartola import fetch_team_info_by_team_id
        team_info = fetch_team_info_by_team_id(conn, team_id)
        
        if not team_info:
            # Se não conseguiu, tentar atualizar tokens
            new_token = refresh_access_token_by_team_id(conn, team_id)
            if new_token:
                # Tentar novamente após atualizar
                team_info = fetch_team_info_by_team_id(conn, team_id)
        
        if not team_info:
            return jsonify({'error': 'Não foi possível atualizar os tokens. Verifique se as credenciais estão corretas.'}), 400
        
        # Extrair nome atualizado
        final_team_name = team.get('team_name')
        team_shield_url = None
        
        if 'time' in team_info and isinstance(team_info['time'], dict):
            time_data = team_info['time']
            if 'nome' in time_data:
                final_team_name = time_data['nome']
            
            # Extrair escudo
            if 'url_escudo_png' in time_data:
                team_shield_url = time_data['url_escudo_png']
            elif 'url_escudo_svg' in time_data:
                team_shield_url = time_data['url_escudo_svg']
            elif 'foto_perfil' in time_data:
                team_shield_url = time_data['foto_perfil']
        
        # Atualizar nome no banco (escudo não é salvo, é buscado dinamicamente)
        if final_team_name != team.get('team_name'):
            update_team(conn, team_id, user['id'], team_name=final_team_name)
        
        return jsonify({
            'success': True,
            'message': 'Tokens atualizados com sucesso!',
            'team_name': final_team_name,
            'team_shield_url': team_shield_url
        })
    except Exception as e:
        print(f"Erro ao atualizar tokens: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/escalacao-ideal/config', methods=['GET', 'POST'])
@login_required
def api_escalacao_config():
    """API para obter ou salvar configurações de escalação ideal"""
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        from models.user_escalacao_config import get_user_escalacao_config, upsert_user_escalacao_config
        from models.user_escalacao_config import create_user_escalacao_config_table
        create_user_escalacao_config_table(conn)  # Garantir que a tabela existe
        
        if request.method == 'GET':
            # Usar time selecionado na sessão
            team_id = session.get('selected_team_id')
            if not team_id:
                # Se não houver time selecionado, buscar o primeiro
                from models.teams import get_all_user_teams, create_teams_table
                create_teams_table(conn)
                times = get_all_user_teams(conn, user['id'])
                if times and len(times) > 0:
                    team_id = times[0]['id']
                    session['selected_team_id'] = team_id
            
            config = get_user_escalacao_config(conn, user['id'], team_id)
            if config:
                return jsonify({
                    'formation': config['formation'],
                    'hack_goleiro': config['hack_goleiro'],
                    'fechar_defesa': config['fechar_defesa'],
                    'posicao_capitao': config['posicao_capitao']
                })
            else:
                # Retornar valores padrão
                return jsonify({
                    'formation': '4-3-3',
                    'hack_goleiro': False,
                    'fechar_defesa': False,
                    'posicao_capitao': 'atacantes'
                })
        else:  # POST
            data = request.get_json()
            # Usar time selecionado na sessão
            team_id = session.get('selected_team_id')
            if not team_id:
                return jsonify({'error': 'Nenhum time selecionado'}), 400
            
            formation = data.get('formation', '4-3-3')
            hack_goleiro = data.get('hack_goleiro', False)
            fechar_defesa = data.get('fechar_defesa', False)
            posicao_capitao = data.get('posicao_capitao', 'atacantes')
            
            upsert_user_escalacao_config(
                conn, user['id'], team_id, formation, hack_goleiro, fechar_defesa, posicao_capitao
            )
            return jsonify({'success': True})
    except Exception as e:
        print(f"Erro em api_escalacao_config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/escalacao-ideal/dados')
@login_required
def api_escalacao_dados():
    """API para fornecer dados necessários para cálculo de escalação ideal"""
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        from models.user_escalacao_config import create_user_escalacao_config_table
        create_user_escalacao_config_table(conn)  # Garantir que a tabela existe
        
        # Usar time selecionado na sessão
        team_id = session.get('selected_team_id')
        if not team_id:
            # Se não houver time selecionado, buscar o primeiro
            from models.teams import get_all_user_teams, create_teams_table
            create_teams_table(conn)
            times = get_all_user_teams(conn, user['id'])
            if times and len(times) > 0:
                team_id = times[0]['id']
                session['selected_team_id'] = team_id
            else:
                return jsonify({'error': 'Nenhum time cadastrado'}), 404
        
        # Buscar rodada atual
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        # Buscar configuração padrão do usuário para este time
        from models.user_configurations import get_user_default_configuration
        config = get_user_default_configuration(conn, user['id'], team_id)
        if not config:
            return jsonify({'error': 'Configuração não encontrada'}), 404
        
        # Buscar rankings salvos de todas as posições
        from models.user_rankings import get_team_rankings
        posicao_map = {
            'goleiro': 1, 'lateral': 2, 'zagueiro': 3, 
            'meia': 4, 'atacante': 5, 'treinador': 6
        }
        
        rankings_por_posicao = {}
        for pos_nome, pos_id in posicao_map.items():
            rankings = get_team_rankings(
                conn, user['id'],
                team_id=team_id,
                configuration_id=config.get('id'),
                posicao_id=pos_id,
                rodada_atual=rodada_atual
            )
            if rankings:
                ranking_data = rankings[0].get('ranking_data', [])
                if isinstance(ranking_data, list) and len(ranking_data) > 0:
                    # Normalizar campos: garantir que preco_num exista
                    # Se não estiver no ranking salvo, buscar da tabela atletas
                    ranking_normalizado = []
                    atleta_ids_sem_preco = []
                    
                    # Primeira passagem: identificar jogadores sem preço
                    print(f"[DEBUG] Processando ranking {pos_nome} com {len(ranking_data)} jogadores")
                    for jogador in ranking_data:
                        jogador_norm = dict(jogador)
                        # Verificar se tem preço válido (> 0)
                        preco_num_val = jogador_norm.get('preco_num', 0)
                        preco_val = jogador_norm.get('preco', 0)
                        
                        # Tentar converter para float
                        try:
                            if preco_num_val:
                                preco_num_val = float(preco_num_val)
                            else:
                                preco_num_val = 0
                            if preco_val:
                                preco_val = float(preco_val)
                            else:
                                preco_val = 0
                        except (ValueError, TypeError):
                            preco_num_val = 0
                            preco_val = 0
                        
                        preco_existe = (preco_num_val and preco_num_val > 0) or (preco_val and preco_val > 0)
                        
                        if not preco_existe and jogador_norm.get('atleta_id'):
                            atleta_ids_sem_preco.append(jogador_norm['atleta_id'])
                            # Log para debug (apenas primeiros 3)
                            if len(atleta_ids_sem_preco) <= 3:
                                print(f"[DEBUG] Jogador {jogador_norm.get('apelido', 'N/A')} (ID: {jogador_norm.get('atleta_id')}) sem preço válido. preco_num={preco_num_val}, preco={preco_val}")
                    
                    # Buscar preços da tabela atletas para os que não têm
                    preco_dict = {}
                    if atleta_ids_sem_preco:
                        print(f"[DEBUG] Buscando preços para {len(atleta_ids_sem_preco)} atletas sem preço na posição {pos_nome}")
                        placeholders = ','.join(['%s'] * len(atleta_ids_sem_preco))
                        cursor.execute(f'''
                            SELECT atleta_id, preco_num
                            FROM acf_atletas
                            WHERE atleta_id IN ({placeholders})
                        ''', atleta_ids_sem_preco)
                        rows_precos = cursor.fetchall()
                        print(f"[DEBUG] Encontrados {len(rows_precos)} preços na tabela atletas")
                        for row in rows_precos:
                            preco_val = float(row[1]) if row[1] else 0.0
                            preco_dict[row[0]] = preco_val
                            if preco_val > 0:
                                print(f"[DEBUG] Atleta {row[0]}: preco_num = {preco_val}")
                    else:
                        print(f"[DEBUG] Todos os jogadores da posição {pos_nome} já têm preço")
                    
                    # Segunda passagem: normalizar todos os jogadores
                    for jogador in ranking_data:
                        jogador_norm = dict(jogador)
                        atleta_id = jogador_norm.get('atleta_id')
                        
                        # Normalizar preço: tentar preco_num, depois preco, depois buscar da tabela
                        preco_valor = None
                        if 'preco_num' in jogador_norm and jogador_norm.get('preco_num'):
                            try:
                                preco_valor = float(jogador_norm['preco_num'])
                            except (ValueError, TypeError):
                                pass
                        
                        if preco_valor is None or preco_valor <= 0:
                            if 'preco' in jogador_norm and jogador_norm.get('preco'):
                                try:
                                    preco_valor = float(jogador_norm['preco'])
                                except (ValueError, TypeError):
                                    pass
                        
                        if (preco_valor is None or preco_valor <= 0) and atleta_id and atleta_id in preco_dict:
                            preco_valor = preco_dict[atleta_id]
                        
                        # Garantir que preco_valor seja um número válido
                        if preco_valor is None or preco_valor <= 0:
                            preco_valor = 0.0
                        
                        # Atualizar campos de preço
                        jogador_norm['preco_num'] = preco_valor
                        jogador_norm['preco'] = preco_valor
                        
                        ranking_normalizado.append(jogador_norm)
                    
                    rankings_por_posicao[pos_nome] = ranking_normalizado
                    print(f"[DEBUG] Ranking {pos_nome}: {len(ranking_normalizado)} jogadores normalizados")
                    if ranking_normalizado:
                        sample = ranking_normalizado[0]
                        print(f"[DEBUG] Exemplo de jogador normalizado: atleta_id={sample.get('atleta_id')}, preco_num={sample.get('preco_num')}, preco={sample.get('preco')}")
        
        # Buscar configuração de escalação
        from models.user_escalacao_config import get_user_escalacao_config
        escalacao_config = get_user_escalacao_config(conn, user['id'], team_id)
        
        # Buscar time para obter patrimônio
        from models.teams import get_team
        team_data_db = None
        if team_id:
            team_data_db = get_team(conn, team_id, user['id'])
        
        # Buscar patrimônio via API do Cartola
        patrimonio = 0
        patrimonio_error = None
        
        if not team_id:
            patrimonio_error = "Time não selecionado"
        else:
            try:
                from api_cartola import fetch_team_data_by_team_id
                print(f"[DEBUG] Buscando patrimônio para time {team_id}...")
                team_data, token_used = fetch_team_data_by_team_id(conn, team_id)
                
                if team_data:
                    # A API do Cartola retorna o patrimônio em time.time_mercado.patrimonio
                    # E também pode ter no nível raiz como time.patrimonio
                    if 'time' in team_data and isinstance(team_data['time'], dict):
                        time_info = team_data['time']
                        # Tentar time_mercado.patrimonio primeiro (estrutura mais comum)
                        if 'time_mercado' in time_info and isinstance(time_info['time_mercado'], dict):
                            patrimonio = time_info['time_mercado'].get('patrimonio', 0)
                        
                        # Se não encontrou, tentar no nível time
                        if not patrimonio or patrimonio <= 0:
                            patrimonio = time_info.get('patrimonio', 0)
                        
                        # Se ainda não encontrou, tentar no nível raiz
                        if not patrimonio or patrimonio <= 0:
                            patrimonio = team_data.get('patrimonio', 0)
                    
                    # Garantir que patrimonio seja um número válido
                    try:
                        patrimonio = float(patrimonio) if patrimonio else 0
                    except (ValueError, TypeError):
                        patrimonio = 0
                    
                    if patrimonio <= 0:
                        print(f"[AVISO] Patrimônio não encontrado ou inválido. Estrutura da resposta: {list(team_data.keys())}")
                        if 'time' in team_data:
                            print(f"[AVISO] Estrutura de 'time': {list(team_data['time'].keys()) if isinstance(team_data['time'], dict) else type(team_data['time'])}")
                        patrimonio_error = "Patrimônio não encontrado na resposta da API do Cartola. Verifique se as credenciais estão corretas."
                    else:
                        print(f"[DEBUG] Patrimônio encontrado: {patrimonio}")
                else:
                    print(f"[AVISO] team_data está vazio ou None. Credenciais podem estar inválidas.")
                    patrimonio_error = "Não foi possível obter dados do time da API do Cartola. Verifique se as credenciais estão corretas."
                    
            except Exception as e:
                print(f"[ERRO] Erro ao buscar patrimônio: {e}")
                import traceback
                traceback.print_exc()
                patrimonio_error = f"Erro ao buscar patrimônio: {str(e)}"
        
        # Buscar clubes para obter informações de SG - usar o perfil configurado pelo usuário
        perfil_peso_sg = config.get('perfil_peso_sg', 2)  # Usar perfil 2 como padrão
        cursor.execute('''
            SELECT clube_id, peso_sg as club_sg
            FROM acp_peso_sg_perfis
            WHERE perfil_id = %s AND rodada_atual = %s
            ORDER BY peso_sg DESC
            LIMIT 10
        ''', (perfil_peso_sg, rodada_atual))
        clubes_sg = [{'clube_id': row[0], 'sg': float(row[1])} for row in cursor.fetchall()]
        
        response_data = {
            'rodada_atual': rodada_atual,
            'rankings_por_posicao': rankings_por_posicao,
            'config': {
                'formation': escalacao_config['formation'] if escalacao_config else '4-3-3',
                'hack_goleiro': escalacao_config['hack_goleiro'] if escalacao_config else False,
                'fechar_defesa': escalacao_config['fechar_defesa'] if escalacao_config else False,
                'posicao_capitao': escalacao_config['posicao_capitao'] if escalacao_config else 'atacantes'
            },
            'patrimonio': patrimonio,
            'clubes_sg': clubes_sg
        }
        
        # Adicionar erro de patrimônio se houver
        if patrimonio_error:
            response_data['patrimonio_error'] = patrimonio_error
        
        print(f"[DEBUG] Retornando patrimônio: {patrimonio}, erro: {patrimonio_error}")
        
        return jsonify(response_data)
    except Exception as e:
        print(f"Erro ao buscar dados de escalação: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        if conn:
            conn.cursor().execute('SELECT 1')
            close_db_connection(conn)
            return jsonify({"status": "healthy"}), 200
    except Exception:
        pass
    return jsonify({"status": "unhealthy"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

