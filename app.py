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
    
    # Se tiver times, redirecionar para o dashboard
    return redirect(url_for('dashboard'))

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

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal com verificações de status do time"""
    user = get_current_user()
    
    from models.teams import create_teams_table, get_team, get_all_user_teams
    from models.user_configurations import get_user_default_configuration, create_user_configurations_table
    from models.user_rankings import create_user_rankings_table
    from api_cartola import fetch_team_info_by_team_id
    from utils.team_shields import get_team_shield
    
    conn = get_db_connection()
    try:
        create_teams_table(conn)
        create_user_configurations_table(conn)
        create_user_rankings_table(conn)
        
        # Verificar se há time selecionado
        team_id = session.get('selected_team_id')
        
        if not team_id:
            # Buscar todos os times do usuário
            all_teams = get_all_user_teams(conn, user['id'])
            if not all_teams or len(all_teams) == 0:
                flash('Por favor, associe suas credenciais do Cartola primeiro.', 'warning')
                return redirect(url_for('associar_credenciais'))
            
            # Selecionar o primeiro time como padrão
            selected_team = all_teams[0]
            team_id = selected_team['id']
            session['selected_team_id'] = team_id
        else:
            selected_team = get_team(conn, team_id, user['id'])
            if not selected_team:
                flash('Time não encontrado. Por favor, selecione um time.', 'warning')
                return redirect(url_for('credenciais'))
        
        # 1. Verificar se perfis foram configurados
        config = get_user_default_configuration(conn, user['id'], team_id)
        tem_perfis = config is not None and config.get('perfil_peso_jogo') and config.get('perfil_peso_sg')
        
        # 2. Verificar se posições foram calculadas (verificar se há dados em user_rankings)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM user_rankings 
            WHERE user_id = %s AND team_id = %s
        ''', (user['id'], team_id))
        count_rankings = cursor.fetchone()[0]
        tem_calculos = count_rankings > 0
        
        # 3. Verificar se tem escalação (verificar se há dados em user_escalacao_config)
        cursor.execute('''
            SELECT COUNT(*) FROM user_escalacao_config 
            WHERE user_id = %s AND team_id = %s
        ''', (user['id'], team_id))
        count_escalacao = cursor.fetchone()[0]
        tem_escalacao = count_escalacao > 0
        
        # Buscar informações do time do Cartola
        team_info_cartola = None
        team_shield_url = None
        try:
            team_info_cartola = fetch_team_info_by_team_id(selected_team['access_token'])
            if team_info_cartola and team_info_cartola.get('time', {}).get('url_escudo_png'):
                team_shield_url = team_info_cartola['time']['url_escudo_png']
        except:
            pass
        
        # Buscar informações do time
        team_info = {
            'id': selected_team['id'],
            'team_name': selected_team.get('team_name', 'Meu Time'),
            'team_slug': team_info_cartola.get('time', {}).get('slug') if team_info_cartola else None,
            'team_shield_url': team_shield_url
        }
        
        status = {
            'tem_perfis': tem_perfis,
            'tem_calculos': tem_calculos,
            'tem_escalacao': tem_escalacao,
            'perfis_info': config if tem_perfis else None
        }
        
    except Exception as e:
        print(f"Erro ao carregar dashboard: {e}")
        import traceback
        traceback.print_exc()
        flash('Erro ao carregar o dashboard.', 'error')
        return redirect(url_for('credenciais'))
    finally:
        close_db_connection(conn)
    
    return render_template('dashboard.html', 
                         current_user=user, 
                         team=team_info,
                         status=status)

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

@app.route('/api/admin/limpar-rankings', methods=['POST'])
@login_required
def api_admin_limpar_rankings():
    """API para limpar todos os rankings (admin only)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Contar antes
        cursor.execute("SELECT COUNT(*) FROM acw_rankings_teams")
        total_antes = cursor.fetchone()[0]
        
        # Deletar todos
        cursor.execute("DELETE FROM acw_rankings_teams")
        conn.commit()
        
        # Contar depois
        cursor.execute("SELECT COUNT(*) FROM acw_rankings_teams")
        total_depois = cursor.fetchone()[0]
        
        return jsonify({
            'success': True,
            'deletados': total_antes,
            'restantes': total_depois,
            'mensagem': f'✅ {total_antes} rankings deletados com sucesso!'
        })
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao limpar rankings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        close_db_connection(conn)

@app.route('/api/debug/time/<int:team_id>')
@login_required
def api_debug_time(team_id):
    """API de debug para verificar por que um time não retorna rankings"""
    user = get_current_user()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        debug_info = {}
        
        # Buscar rodada
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result else 1
        debug_info['rodada_atual'] = rodada_atual
        
        # Buscar info do time
        cursor.execute("SELECT id, user_id, team_name FROM acw_teams WHERE id = %s", (team_id,))
        time_info = cursor.fetchone()
        if not time_info:
            return jsonify({'error': 'Time não encontrado'}), 404
        
        debug_info['time'] = {
            'id': time_info[0],
            'user_id': time_info[1],
            'team_name': time_info[2]
        }
        
        # Buscar configuração
        from models.user_configurations import get_user_default_configuration
        config = get_user_default_configuration(conn, time_info[1], team_id)
        
        debug_info['configuracao'] = {
            'existe': config is not None,
            'config_id': config.get('id') if config else None,
            'perfil_peso_jogo': config.get('perfil_peso_jogo') if config else None,
            'perfil_peso_sg': config.get('perfil_peso_sg') if config else None
        }
        
        # Verificar rankings - QUERY DIRETA
        cursor.execute("""
            SELECT posicao_id, configuration_id, 
                   CASE 
                       WHEN ranking_data::text = '[]' THEN 0
                       ELSE jsonb_array_length(ranking_data)
                   END as qtd_jogadores
            FROM acw_rankings_teams
            WHERE team_id = %s
              AND rodada_atual = %s
            ORDER BY posicao_id
        """, (team_id, rodada_atual))
        
        rankings_direto = cursor.fetchall()
        debug_info['rankings_direto'] = [
            {'posicao_id': r[0], 'configuration_id': r[1], 'qtd_jogadores': r[2]}
            for r in rankings_direto
        ]
        
        # Verificar rankings com configuration_id
        if config:
            cursor.execute("""
                SELECT posicao_id,
                       CASE 
                           WHEN ranking_data::text = '[]' THEN 0
                           ELSE jsonb_array_length(ranking_data)
                       END as qtd_jogadores
                FROM acw_rankings_teams
                WHERE team_id = %s
                  AND rodada_atual = %s
                  AND configuration_id = %s
                ORDER BY posicao_id
            """, (team_id, rodada_atual, config.get('id')))
            
            rankings_com_config = cursor.fetchall()
            debug_info['rankings_com_config_id'] = [
                {'posicao_id': r[0], 'qtd_jogadores': r[1]}
                for r in rankings_com_config
            ]
        else:
            debug_info['rankings_com_config_id'] = []
        
        # Usar a mesma função da API
        from models.user_rankings import get_team_rankings
        posicoes = {
            'goleiro': 1, 'lateral': 2, 'zagueiro': 3,
            'meia': 4, 'atacante': 5, 'treinador': 6
        }
        
        rankings_via_funcao = {}
        for pos_nome, pos_id in posicoes.items():
            rankings = get_team_rankings(
                conn,
                time_info[1],  # user_id
                team_id=team_id,
                configuration_id=config.get('id') if config else None,
                posicao_id=pos_id,
                rodada_atual=rodada_atual
            )
            
            if rankings:
                ranking_data = rankings[0].get('ranking_data', [])
                qtd = len(ranking_data) if isinstance(ranking_data, list) else 0
                rankings_via_funcao[pos_nome] = {'qtd_jogadores': qtd, 'tem_ranking': True}
            else:
                rankings_via_funcao[pos_nome] = {'qtd_jogadores': 0, 'tem_ranking': False}
        
        debug_info['rankings_via_funcao'] = rankings_via_funcao
        
        # Diagnóstico
        debug_info['diagnostico'] = []
        
        if not config:
            debug_info['diagnostico'].append('❌ TIME NÃO TEM CONFIGURAÇÃO - Precisa escolher perfis')
        
        if len(debug_info['rankings_direto']) == 0:
            debug_info['diagnostico'].append('❌ NENHUM RANKING SALVO - Precisa calcular os módulos')
        elif len(debug_info['rankings_direto']) < 6:
            debug_info['diagnostico'].append(f'⚠️  APENAS {len(debug_info["rankings_direto"])}/6 RANKINGS')
        
        if config and len(debug_info['rankings_com_config_id']) == 0:
            debug_info['diagnostico'].append('❌ RANKINGS SALVOS COM OUTRO configuration_id - Recalcular módulos')
        
        if not debug_info['diagnostico']:
            debug_info['diagnostico'].append('✅ Tudo parece OK')
        
        return jsonify(debug_info)
        
    except Exception as e:
        print(f"Erro no debug: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        close_db_connection(conn)

@app.route('/api/perfis/verificar')
@login_required
def api_perfis_verificar():
    """API para verificar se há perfis de peso de jogo e SG disponíveis"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Buscar rodada atual
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else None
        
        if not rodada_atual:
            return jsonify({
                'tem_perfis': False,
                'tem_peso_jogo': False,
                'tem_peso_sg': False,
                'rodada_atual': None,
                'mensagem': 'Nenhuma rodada encontrada. Execute o sistema de cálculo de perfis primeiro.'
            })
        
        # Verificar perfis de peso de jogo
        cursor.execute("""
            SELECT COUNT(*) FROM acp_peso_jogo_perfis 
            WHERE rodada_atual = %s
        """, (rodada_atual,))
        count_peso_jogo = cursor.fetchone()[0]
        
        # Verificar perfis de peso SG
        cursor.execute("""
            SELECT COUNT(*) FROM acp_peso_sg_perfis 
            WHERE rodada_atual = %s
        """, (rodada_atual,))
        count_peso_sg = cursor.fetchone()[0]
        
        tem_peso_jogo = count_peso_jogo > 0
        tem_peso_sg = count_peso_sg > 0
        tem_perfis = tem_peso_jogo and tem_peso_sg
        
        mensagem = None
        if not tem_perfis:
            if not tem_peso_jogo and not tem_peso_sg:
                mensagem = 'Não há perfis de Peso de Jogo nem Peso SG calculados. Execute o sistema de cálculo primeiro.'
            elif not tem_peso_jogo:
                mensagem = 'Não há perfis de Peso de Jogo calculados. Execute o sistema de cálculo primeiro.'
            elif not tem_peso_sg:
                mensagem = 'Não há perfis de Peso SG calculados. Execute o sistema de cálculo primeiro.'
        
        return jsonify({
            'tem_perfis': tem_perfis,
            'tem_peso_jogo': tem_peso_jogo,
            'tem_peso_sg': tem_peso_sg,
            'rodada_atual': rodada_atual,
            'count_peso_jogo': count_peso_jogo,
            'count_peso_sg': count_peso_sg,
            'mensagem': mensagem
        })
    except Exception as e:
        print(f"Erro ao verificar perfis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        close_db_connection(conn)

@app.route('/api/modulos/status')
@login_required
def api_modulos_status():
    """API para verificar status de todos os módulos (se foram calculados)"""
    user = get_current_user()
    team_id = session.get('selected_team_id')
    
    if not team_id:
        return jsonify({'error': 'Nenhum time selecionado'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Buscar rodada atual
        cursor.execute('SELECT MAX(rodada_atual) FROM acp_peso_jogo_perfis')
        rodada_result = cursor.fetchone()
        rodada_atual = rodada_result[0] if rodada_result and rodada_result[0] else 1
        
        # Mapeamento de módulos para posicao_id
        posicao_map = {
            'goleiro': 1, 
            'lateral': 2, 
            'zagueiro': 3, 
            'meia': 4, 
            'atacante': 5, 
            'treinador': 6
        }
        
        # Verificar cada módulo de posição
        modulos = ['goleiro', 'lateral', 'zagueiro', 'meia', 'atacante', 'treinador']
        status = {}
        
        for modulo in modulos:
            posicao_id = posicao_map[modulo]
            cursor.execute("""
                SELECT COUNT(*) > 0 as calculado
                FROM acw_rankings_teams
                WHERE team_id = %s
                  AND rodada_atual = %s
                  AND posicao_id = %s
            """, (team_id, rodada_atual, posicao_id))
            
            result = cursor.fetchone()
            status[modulo] = bool(result[0]) if result else False
        
        # Verificar se todos foram calculados
        todos_calculados = all(status.values())
        
        return jsonify({
            'status': status,
            'todos_calculados': todos_calculados,
            'rodada_atual': rodada_atual,
            'team_id': team_id
        })
    except Exception as e:
        print(f"Erro ao verificar status dos módulos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        close_db_connection(conn)

@app.route('/modulos/<modulo>')
@login_required
def modulo_individual(modulo):
    """Página individual de cada módulo (goleiro, lateral, etc)"""
    # Validar se o módulo é válido (apenas módulos de posição)
    modulos_validos = ['goleiro', 'lateral', 'zagueiro', 'meia', 'atacante', 'treinador']
    if modulo not in modulos_validos:
        flash('Módulo inválido', 'error')
        return redirect(url_for('modulos'))
    
    user = get_current_user()
    
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
    
    # Defaults por posição
    defaults_posicao = {
        'goleiro': {
            'FATOR_MEDIA': 0.3,
            'FATOR_FF': 1.3,
            'FATOR_FD': 1.3,
            'FATOR_SG': 1.4,
            'FATOR_PESO_JOGO': 0.3,
            'FATOR_GOL_ADVERSARIO': 1.4
        },
        'lateral': {
            'FATOR_MEDIA': 1.6,
            'FATOR_DS': 2.1,
            'FATOR_SG': 2.0,
            'FATOR_ESCALACAO': 1.5,
            'FATOR_FF': 1.4,
            'FATOR_FS': 1.3,
            'FATOR_FD': 1.4,
            'FATOR_G': 1.5,
            'FATOR_A': 1.8,
            'FATOR_PESO_JOGO': 1.5
        },
        'zagueiro': {
            'FATOR_MEDIA': 1.5,
            'FATOR_DS': 2.0,
            'FATOR_SG': 2.0,
            'FATOR_ESCALACAO': 1.5,
            'FATOR_PESO_JOGO': 1.5
        },
        'meia': {
            'FATOR_MEDIA': 2.5,
            'FATOR_DS': 3.0,
            'FATOR_FF': 2.9,
            'FATOR_FS': 2.8,
            'FATOR_FD': 3.2,
            'FATOR_G': 4.2,
            'FATOR_A': 3.5,
            'FATOR_ESCALACAO': 2.0,
            'FATOR_PESO_JOGO': 2.5
        },
        'atacante': {
            'FATOR_MEDIA': 2.9,
            'FATOR_DS': 2.0,
            'FATOR_FF': 3.2,
            'FATOR_FS': 2.3,
            'FATOR_FD': 3.4,
            'FATOR_G': 4.0,
            'FATOR_A': 3.5,
            'FATOR_ESCALACAO': 3.0,
            'FATOR_PESO_JOGO': 3.5
        },
        'treinador': {
            'FATOR_PESO_JOGO': 1.0
        }
    }
    
    defaults_modulo = defaults_posicao.get(modulo, defaults_posicao['goleiro'])
    
    # Buscar team_id da sessão
    team_id = session.get('selected_team_id')
    
    # Buscar pesos salvos para este time e módulo (se houver time selecionado)
    pesos_atuais = {}
    if team_id:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT weights_json FROM acw_posicao_weights
                WHERE user_id = %s AND team_id = %s AND posicao = %s
            ''', (user['id'], team_id, modulo))
            peso_row = cursor.fetchone()
            
            if peso_row and peso_row[0]:
                # Pesos salvos encontrados para este time
                pesos_salvos = peso_row[0] if isinstance(peso_row[0], dict) else json.loads(peso_row[0])
                for key, default in defaults_modulo.items():
                    pesos_atuais[key] = float(pesos_salvos.get(key, default))
            else:
                # Não há pesos salvos, usar defaults
                pesos_atuais = {key: float(default) for key, default in defaults_modulo.items()}
        finally:
            close_db_connection(conn)
    else:
        # Sem time selecionado, usar defaults
        pesos_atuais = {key: float(default) for key, default in defaults_modulo.items()}
    
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
        
        # ⭐ OBTER TEAM_ID DA SESSÃO - ISSO É CRÍTICO!
        team_id = session.get('selected_team_id')
        if not team_id:
            return jsonify({'error': 'Nenhum time selecionado'}), 400
        
        # Buscar configuração DO TIME (não só do usuário!)
        from models.user_configurations import get_user_default_configuration
        config = get_user_default_configuration(conn, user['id'], team_id)
        
        if not config:
            return jsonify({'error': 'Configuração não encontrada para este time'}), 404
        
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
                    'posicao_capitao': config['posicao_capitao'],
                    'posicao_reserva_luxo': config.get('posicao_reserva_luxo', 'atacantes'),
                    'prioridades': config.get('prioridades', 'atacantes,laterais,meias,zagueiros,goleiros,tecnicos')
                })
            else:
                # Retornar valores padrão
                return jsonify({
                    'formation': '4-3-3',
                    'hack_goleiro': False,
                    'fechar_defesa': False,
                    'posicao_capitao': 'atacantes',
                    'posicao_reserva_luxo': 'atacantes',
                    'prioridades': 'atacantes,laterais,meias,zagueiros,goleiros,tecnicos'
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
            posicao_reserva_luxo = data.get('posicao_reserva_luxo', 'atacantes')
            prioridades = data.get('prioridades', 'atacantes,laterais,meias,zagueiros,goleiros,tecnicos')
            
            upsert_user_escalacao_config(
                conn, user['id'], team_id, formation, hack_goleiro, fechar_defesa, posicao_capitao, posicao_reserva_luxo, prioridades
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
                    
                    # Buscar preços e status_id da tabela atletas
                    preco_dict = {}
                    status_dict = {}
                    
                    # Buscar para todos os atletas do ranking (para garantir status_id atualizado)
                    atleta_ids_ranking = [j['atleta_id'] for j in ranking_data if j.get('atleta_id')]
                    if atleta_ids_ranking:
                        placeholders = ','.join(['%s'] * len(atleta_ids_ranking))
                        cursor.execute(f'''
                            SELECT atleta_id, preco_num, status_id
                            FROM acf_atletas
                            WHERE atleta_id IN ({placeholders})
                        ''', atleta_ids_ranking)
                        rows_atletas = cursor.fetchall()
                        
                        for row in rows_atletas:
                            atleta_id = row[0]
                            preco_val = float(row[1]) if row[1] else 0.0
                            status_val = int(row[2]) if row[2] else 0
                            
                            preco_dict[atleta_id] = preco_val
                            status_dict[atleta_id] = status_val
                        
                        print(f"[DEBUG] Buscados preços e status para {len(rows_atletas)} atletas da posição {pos_nome}")
                    
                    if atleta_ids_sem_preco:
                        print(f"[DEBUG] {len(atleta_ids_sem_preco)} atletas sem preço na posição {pos_nome}")
                    
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
                        
                        # Adicionar status_id atual da tabela (não do ranking salvo)
                        if atleta_id and atleta_id in status_dict:
                            jogador_norm['status_id'] = status_dict[atleta_id]
                        else:
                            jogador_norm['status_id'] = 0  # Status desconhecido
                        
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
            SELECT clube_id, peso_sg
            FROM acp_peso_sg_perfis
            WHERE perfil_id = %s AND rodada_atual = %s
            ORDER BY peso_sg DESC
            LIMIT 10
        ''', (perfil_peso_sg, rodada_atual))
        clubes_sg = [{'clube_id': row[0], 'peso_sg': float(row[1])} for row in cursor.fetchall()]
        
        # Buscar TODOS os goleiros (para hack do goleiro) - incluindo não prováveis
        print("[DEBUG] Buscando TODOS os goleiros da tabela acf_atletas...")
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.preco_num, a.status_id
            FROM acf_atletas a
            WHERE a.posicao_id = 1
            ORDER BY a.preco_num DESC
        ''')
        
        rows_goleiros = cursor.fetchall()
        print(f"[DEBUG] Query retornou {len(rows_goleiros)} goleiros da tabela acf_atletas")
        
        todos_goleiros = []
        goleiros_nulos_count = 0
        goleiros_provaveis_count = 0
        
        for row in rows_goleiros:
            if row and len(row) >= 5:
                status_id = int(row[4]) if row[4] else 0
                
                # Contar por status
                if status_id in [2, 7]:
                    goleiros_provaveis_count += 1
                else:
                    goleiros_nulos_count += 1
                
                goleiro_data = {
                    'atleta_id': row[0],
                    'apelido': row[1],
                    'clube_id': row[2],
                    'preco_num': float(row[3]) if row[3] else 0,
                    'preco': float(row[3]) if row[3] else 0,
                    'status_id': status_id,
                    'pontuacao_total': 0  # Goleiros nulos não precisam de pontuação
                }
                todos_goleiros.append(goleiro_data)
        
        print(f"[DEBUG] Total de goleiros processados: {len(todos_goleiros)}")
        print(f"[DEBUG] Goleiros prováveis (status 2 ou 7): {goleiros_provaveis_count}")
        print(f"[DEBUG] Goleiros NULOS (outros status): {goleiros_nulos_count}")
        
        if todos_goleiros:
            # Mostrar os 5 goleiros nulos mais caros
            goleiros_nulos_lista = [g for g in todos_goleiros if g['status_id'] not in [2, 7]]
            goleiros_nulos_lista.sort(key=lambda x: x['preco_num'], reverse=True)
            
            if goleiros_nulos_lista:
                print(f"[DEBUG] Top 5 goleiros NULOS mais caros:")
                for g in goleiros_nulos_lista[:5]:
                    print(f"  - {g['apelido']} - R$ {g['preco_num']:.2f} - status_id: {g['status_id']}")
            else:
                print("[DEBUG] ATENÇÃO: Nenhum goleiro NULO encontrado!")
        else:
            print("[DEBUG] ATENÇÃO: Lista de todos_goleiros está VAZIA!")
        
        # Buscar top 5 de peso de jogo
        perfil_peso_jogo = config.get('perfil_peso_jogo', 2)
        cursor.execute('''
            SELECT clube_id, peso_jogo
            FROM acp_peso_jogo_perfis
            WHERE perfil_id = %s AND rodada_atual = %s
            ORDER BY peso_jogo DESC
            LIMIT 5
        ''', (perfil_peso_jogo, rodada_atual))
        top5_peso_jogo = [{'clube_id': row[0], 'peso_jogo': float(row[1])} for row in cursor.fetchall()]
        
        # Buscar top 5 de peso SG
        cursor.execute('''
            SELECT clube_id, peso_sg
            FROM acp_peso_sg_perfis
            WHERE perfil_id = %s AND rodada_atual = %s
            ORDER BY peso_sg DESC
            LIMIT 5
        ''', (perfil_peso_sg, rodada_atual))
        top5_peso_sg = [{'clube_id': row[0], 'peso_sg': float(row[1])} for row in cursor.fetchall()]
        
        # Buscar dados de clubes com escudos para os cards
        from utils.team_shields import get_team_shield
        clube_ids_set = set()
        
        # Coletar IDs de clubes dos rankings
        for pos_nome, ranking in rankings_por_posicao.items():
            for jogador in ranking[:5]:  # Top 5 apenas
                if jogador.get('clube_id'):
                    clube_ids_set.add(jogador['clube_id'])
        
        # Coletar IDs dos top 5 de pesos
        for item in top5_peso_jogo:
            clube_ids_set.add(item['clube_id'])
        for item in top5_peso_sg:
            clube_ids_set.add(item['clube_id'])
        
        # Buscar dados dos clubes
        clubes_dict = {}
        if clube_ids_set:
            placeholders = ','.join(['%s'] * len(clube_ids_set))
            cursor.execute(f'''
                SELECT id, nome, abreviacao
                FROM acf_clubes
                WHERE id IN ({placeholders})
            ''', list(clube_ids_set))
            
            for row in cursor.fetchall():
                clube_id = row[0]
                escudo_url = get_team_shield(clube_id, size='45x45')
                clubes_dict[clube_id] = {
                    'nome': row[1],
                    'abreviacao': row[2],
                    'escudo_url': escudo_url
                }
        
        response_data = {
            'team_id': team_id,
            'rodada_atual': rodada_atual,
            'rankings_por_posicao': rankings_por_posicao,
            'todos_goleiros': todos_goleiros,  # Lista completa de goleiros para hack
            'config': {
                'formation': escalacao_config['formation'] if escalacao_config else '4-3-3',
                'hack_goleiro': escalacao_config['hack_goleiro'] if escalacao_config else False,
                'fechar_defesa': escalacao_config['fechar_defesa'] if escalacao_config else False,
                'posicao_capitao': escalacao_config['posicao_capitao'] if escalacao_config else 'atacantes'
            },
            'patrimonio': patrimonio,
            'clubes_sg': clubes_sg,
            'top5_peso_jogo': top5_peso_jogo,
            'top5_peso_sg': top5_peso_sg,
            'clubes_dict': clubes_dict
        }
        
        # Adicionar erro de patrimônio se houver
        if patrimonio_error:
            response_data['patrimonio_error'] = patrimonio_error
        
        print(f"[DEBUG] Retornando patrimônio: {patrimonio}, erro: {patrimonio_error}")
        print(f"[DEBUG] Enviando {len(todos_goleiros)} goleiros no campo 'todos_goleiros' da resposta")
        
        return jsonify(response_data)
    except Exception as e:
        print(f"Erro ao buscar dados de escalação: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/diagnostico/goleiros-nulos')
@login_required
def diagnostico_goleiros_nulos():
    """Página de diagnóstico para visualizar goleiros nulos"""
    return render_template('diagnostico_goleiros.html')

@app.route('/api/escalacao-ideal/goleiros-nulos')
@login_required
def api_goleiros_nulos():
    """API para buscar goleiros nulos diretamente da tabela acf_atletas"""
    conn = get_db_connection()
    
    try:
        # Parâmetro opcional: preço mínimo do goleiro titular
        preco_minimo = request.args.get('preco_minimo', 0, type=float)
        
        cursor = conn.cursor()
        
        # Buscar TODOS os goleiros da tabela
        cursor.execute('''
            SELECT a.atleta_id, a.apelido, a.clube_id, a.preco_num, a.status_id,
                   c.nome as clube_nome, c.abreviacao as clube_abrev
            FROM acf_atletas a
            LEFT JOIN acf_clubes c ON a.clube_id = c.id
            WHERE a.posicao_id = 1
            ORDER BY a.preco_num DESC
        ''')
        
        todos_goleiros = []
        goleiros_nulos = []
        goleiros_provaveis = []
        
        for row in cursor.fetchall():
            if row and len(row) >= 5:
                goleiro = {
                    'atleta_id': row[0],
                    'apelido': row[1],
                    'clube_id': row[2],
                    'preco_num': float(row[3]) if row[3] else 0,
                    'status_id': int(row[4]) if row[4] else 0,
                    'clube_nome': row[5] if len(row) > 5 else None,
                    'clube_abrev': row[6] if len(row) > 6 else None
                }
                
                todos_goleiros.append(goleiro)
                
                # Classificar por status
                if goleiro['status_id'] in [2, 7]:  # Provável ou dúvida
                    goleiros_provaveis.append(goleiro)
                else:  # Nulo (qualquer outro status)
                    goleiros_nulos.append(goleiro)
        
        # Filtrar goleiros nulos mais caros que o preço mínimo
        goleiros_nulos_mais_caros = [
            g for g in goleiros_nulos 
            if g['preco_num'] > preco_minimo
        ]
        
        # Ordenar por preço (mais caros primeiro)
        goleiros_nulos_mais_caros.sort(key=lambda x: x['preco_num'], reverse=True)
        
        response = {
            'total_goleiros': len(todos_goleiros),
            'total_goleiros_provaveis': len(goleiros_provaveis),
            'total_goleiros_nulos': len(goleiros_nulos),
            'total_goleiros_nulos_mais_caros': len(goleiros_nulos_mais_caros),
            'preco_minimo_filtro': preco_minimo,
            'todos_goleiros': todos_goleiros,
            'goleiros_provaveis': goleiros_provaveis,
            'goleiros_nulos': goleiros_nulos,
            'goleiros_nulos_mais_caros': goleiros_nulos_mais_caros,
            'status_ids': {
                '2': 'Dúvida',
                '3': 'Suspenso',
                '5': 'Contundido',
                '6': 'Nulo',
                '7': 'Provável'
            }
        }
        
        print(f"[DEBUG] Goleiros na base: {len(todos_goleiros)}")
        print(f"[DEBUG] Goleiros prováveis (status 2 ou 7): {len(goleiros_provaveis)}")
        print(f"[DEBUG] Goleiros nulos (outros status): {len(goleiros_nulos)}")
        print(f"[DEBUG] Goleiros nulos mais caros que R$ {preco_minimo:.2f}: {len(goleiros_nulos_mais_caros)}")
        
        if goleiros_nulos_mais_caros:
            top5 = goleiros_nulos_mais_caros[:5]
            print(f"[DEBUG] Top 5 goleiros nulos mais caros:")
            for g in top5:
                print(f"  - {g['apelido']} ({g['clube_abrev']}) - R$ {g['preco_num']:.2f} - status_id: {g['status_id']}")
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Erro ao buscar goleiros nulos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        close_db_connection(conn)

@app.route('/api/escalacao-ideal/escalar', methods=['POST'])
@login_required
def api_escalar_time():
    """API para escalar o time no Cartola FC"""
    from api_cartola import salvar_time_no_cartola
    from models.teams import get_team
    
    user = get_current_user()
    conn = get_db_connection()
    
    try:
        # Receber dados da escalação
        data = request.get_json()
        print(f"[DEBUG] Dados recebidos: {data}")
        
        escalacao = data.get('escalacao') if data else None
        
        if not escalacao:
            print(f"[ERROR] Escalação não fornecida. Data: {data}")
            return jsonify({'error': 'Escalação não fornecida'}), 400
        
        # Obter team_id da sessão
        team_id = session.get('selected_team_id')
        if not team_id:
            return jsonify({'error': 'Nenhum time selecionado'}), 400
        
        # Buscar team no banco
        team = get_team(conn, team_id)
        if not team:
            return jsonify({'error': 'Time não encontrado'}), 404
        
        access_token = team.get('access_token')
        if not access_token:
            return jsonify({'error': 'Token de acesso não encontrado'}), 401
        
        # Mapear posições para IDs numéricos (usado pela API do Cartola)
        posicao_id_map = {
            'goleiros': 1,
            'laterais': 2,
            'zagueiros': 3,
            'meias': 4,
            'atacantes': 5,
            'treinadores': 6
        }
        
        # Preparar payload para API do Cartola
        titulares = escalacao.get('titulares', {})
        reservas = escalacao.get('reservas', {})
        
        # Array de IDs dos titulares (12 atletas)
        atletas_ids = []
        for posicao in ['goleiros', 'zagueiros', 'laterais', 'meias', 'atacantes', 'treinadores']:
            jogadores = titulares.get(posicao, [])
            print(f"[DEBUG] Posição {posicao}: {len(jogadores)} jogadores")
            for jogador in jogadores:
                atleta_id = jogador.get('atleta_id')
                print(f"[DEBUG]   - Jogador: {jogador.get('apelido', 'N/A')} (ID: {atleta_id})")
                atletas_ids.append(atleta_id)
        
        print(f"[DEBUG] Total de atletas: {len(atletas_ids)}")
        
        # Validar 12 atletas
        if len(atletas_ids) != 12:
            print(f"[ERROR] Escalação inválida: {len(atletas_ids)} atletas")
            print(f"[ERROR] Titulares: {titulares}")
            return jsonify({
                'error': f'Escalação inválida: {len(atletas_ids)} atletas. Esperado: 12',
                'detalhes': {
                    'atletas_encontrados': len(atletas_ids),
                    'por_posicao': {pos: len(titulares.get(pos, [])) for pos in ['goleiros', 'zagueiros', 'laterais', 'meias', 'atacantes', 'treinadores']}
                }
            }), 400
        
        # Identificar capitão
        capitao_id = None
        for posicao_jogadores in titulares.values():
            for jogador in posicao_jogadores:
                if jogador.get('eh_capitao'):
                    capitao_id = jogador.get('atleta_id')
                    break
            if capitao_id:
                break
        
        # Mapear reservas {posicao_id: atleta_id}
        # IMPORTANTE: Reserva de luxo também deve estar aqui!
        # As chaves devem ser STRINGS com os IDs das posições
        reservas_map = {}
        for posicao, jogadores in reservas.items():
            for jogador in jogadores:
                posicao_id = posicao_id_map.get(posicao)
                if posicao_id:
                    atleta_id = jogador.get('atleta_id')
                    reservas_map[str(posicao_id)] = atleta_id  # String!
                    print(f"[DEBUG] Reserva posição {posicao_id} ({posicao}): {jogador.get('apelido')} (ID: {atleta_id}) - Luxo: {jogador.get('eh_reserva_luxo', False)}")
        
        # Identificar reserva de luxo
        reserva_luxo_id = None
        for jogadores in reservas.values():
            for jogador in jogadores:
                if jogador.get('eh_reserva_luxo'):
                    reserva_luxo_id = jogador.get('atleta_id')
                    print(f"[DEBUG] Reserva de luxo identificado: {jogador.get('apelido')} (ID: {reserva_luxo_id})")
                    break
            if reserva_luxo_id:
                break
        
        print(f"[DEBUG] Reservas completas: {reservas_map}")
        print(f"[DEBUG] Capitão: {capitao_id}")
        print(f"[DEBUG] Reserva luxo: {reserva_luxo_id}")
        
        # Obter esquema da formação (mapear 4-3-3 -> ID 3, etc)
        esquema_map = {
            '4-3-3': 3,
            '4-4-2': 1,
            '3-5-2': 2,
            '3-4-3': 4,
            '4-5-1': 5,
            '5-4-1': 6
        }
        formacao = data.get('formacao', '4-3-3')
        esquema_id = esquema_map.get(formacao, 3)
        
        # Montar payload
        time_para_escalacao = {
            'esquema': esquema_id,
            'atletas': atletas_ids,
            'capitao': capitao_id,
            'reservas': reservas_map,
            'reserva_luxo_id': reserva_luxo_id
        }
        
        print(f"[DEBUG] Escalando time {team_id}")
        print(f"[DEBUG] Payload: {time_para_escalacao}")
        
        # Enviar para API do Cartola
        # Criar uma função auxiliar que usa team_id
        from api_cartola import API_URL_SALVAR_TIME, refresh_access_token_by_team_id
        import requests
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://cartola.globo.com",
            "Referer": "https://cartola.globo.com/",
            "x-glb-app": "cartola_web",
            "x-glb-auth": "oidc",
        }
        
        try:
            # Timeout de 10 segundos para não travar o cliente
            response = requests.post(API_URL_SALVAR_TIME, json=time_para_escalacao, headers=headers, timeout=10)
            
            if response.status_code == 401:
                # Token expirado, tentar refresh
                print(f"[DEBUG] Token expirado, tentando refresh...")
                new_token = refresh_access_token_by_team_id(conn, team_id)
                if new_token:
                    headers["Authorization"] = f"Bearer {new_token}"
                    response = requests.post(API_URL_SALVAR_TIME, json=time_para_escalacao, headers=headers, timeout=10)
                else:
                    return jsonify({'error': 'Falha ao atualizar token'}), 401
            
            # Processar resposta
            if 200 <= response.status_code < 300:
                try:
                    response_data = response.json()
                    if response_data.get("mensagem") == "Time Escalado! Boa Sorte!":
                        return jsonify({
                            'success': True,
                            'mensagem': 'Time escalado com sucesso!',
                            'detalhes': response_data
                        })
                    else:
                        return jsonify({
                            'error': response_data.get('mensagem', 'Erro desconhecido'),
                            'detalhes': response_data
                        }), 400
                except Exception:
                    return jsonify({
                        'error': 'Resposta inesperada da API',
                        'status': response.status_code
                    }), 400
            else:
                try:
                    error_data = response.json()
                    return jsonify({
                        'error': error_data.get('mensagem', f'Erro HTTP {response.status_code}'),
                        'detalhes': error_data
                    }), response.status_code
                except Exception:
                    return jsonify({
                        'error': f'Erro HTTP {response.status_code}',
                        'mensagem': response.text[:200]
                    }), response.status_code
                    
        except requests.exceptions.Timeout:
            print(f"[ERROR] Timeout ao escalar time")
            return jsonify({'error': 'A API do Cartola demorou demais para responder. Tente novamente.'}), 504
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Erro ao escalar: {e}")
            return jsonify({'error': f'Erro de conexão: {str(e)}'}), 500
        
    except Exception as e:
        print(f"[ERROR] Erro no endpoint escalar: {e}")
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

