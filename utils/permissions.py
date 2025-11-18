"""
Utilitários para verificação de permissões baseadas em planos
"""

from functools import wraps
from flask import session, jsonify, redirect, url_for, flash
from models.plans import (
    check_permission,
    get_user_plan_config,
    get_max_perfis_jogo,
    get_max_perfis_sg,
    get_max_times,
    get_nivel_risco
)


def plan_required(feature: str, redirect_url: str = None, error_message: str = None):
    """
    Decorator para verificar se o usuário tem permissão para uma funcionalidade.
    
    Args:
        feature: Nome da funcionalidade (ex: 'podeEscalar', 'editarPesosModulos')
        redirect_url: URL para redirecionar se não tiver permissão (opcional)
        error_message: Mensagem de erro personalizada (opcional)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id')
            if not user_id:
                flash('Você precisa fazer login para acessar esta funcionalidade.', 'warning')
                return redirect(url_for('login'))
            
            if not check_permission(user_id, feature):
                plan_config = get_user_plan_config(user_id)
                plan_name = plan_config.get('name', 'Free')
                
                # Mensagens padrão por funcionalidade
                messages = {
                    'podeEscalar': f'Esta funcionalidade está disponível no plano Avançado ou Pro.',
                    'editarPesosModulos': f'Edição de pesos está disponível apenas no plano Pro.',
                    'hackGoleiro': f'Hack do Goleiro está disponível apenas no plano Pro.',
                    'multiEscalacao': f'Multi-escalação está disponível apenas no plano Pro.',
                    'fecharDefesa': f'Fechar Defesa está disponível no plano Avançado ou Pro.',
                    'estatisticasAvancadas': f'Estatísticas Avançadas estão disponíveis no plano Avançado ou Pro.',
                }
                
                message = error_message or messages.get(feature, f'Esta funcionalidade não está disponível no seu plano atual ({plan_name}).')
                
                if redirect_url:
                    flash(message, 'error')
                    return redirect(redirect_url)
                else:
                    return jsonify({
                        'success': False,
                        'error': message,
                        'plan': plan_name
                    }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_user_permissions(user_id: int) -> dict:
    """
    Retorna todas as permissões do usuário em formato JSON para o frontend.
    """
    plan_config = get_user_plan_config(user_id)
    
    return {
        'plan': plan_config.get('name', 'Free'),
        'planKey': 'free' if plan_config.get('name') == 'Free' else ('pro' if plan_config.get('name') == 'Pro' else 'avancado'),
        'permissions': {
            'rankingCompleto': plan_config.get('rankingCompleto', False),
            'pesosJogo': plan_config.get('pesosJogo', 2),
            'pesosSG': plan_config.get('pesosSG', 2),
            'editarPesosModulos': plan_config.get('editarPesosModulos', False),
            'verEscalacaoIdealCompleta': plan_config.get('verEscalacaoIdealCompleta', False),
            'podeEscalar': plan_config.get('podeEscalar', False),
            'timesMaximos': plan_config.get('timesMaximos', 1),
            'estatisticasAvancadas': plan_config.get('estatisticasAvancadas', False),
            'fecharDefesa': plan_config.get('fecharDefesa', False),
            'hackGoleiro': plan_config.get('hackGoleiro', False),
            'multiEscalacao': plan_config.get('multiEscalacao', False),
            'reordenarPrioridades': plan_config.get('reordenarPrioridades', False),
            'nivelRisco': plan_config.get('nivelRisco', 1)
        }
    }


def check_max_times(user_id: int, current_count: int):
    """
    Verifica se o usuário pode criar mais times.
    Retorna (pode_criar, mensagem_erro)
    """
    max_times = get_max_times(user_id)
    
    if max_times == 999999:  # Pro (ilimitado)
        return True, None
    
    if current_count >= max_times:
        plan_config = get_user_plan_config(user_id)
        plan_name = plan_config.get('name', 'Free')
        return False, f'Você atingiu o limite de {max_times} time(s) do plano {plan_name}. Faça upgrade para criar mais times.'
    
    return True, None


def check_max_perfis_jogo(user_id: int, perfil_id: int):
    """
    Verifica se o usuário pode usar um perfil de jogo específico.
    Retorna (pode_usar, mensagem_erro)
    """
    max_perfis = get_max_perfis_jogo(user_id)
    
    if perfil_id > max_perfis:
        plan_config = get_user_plan_config(user_id)
        plan_name = plan_config.get('name', 'Free')
        return False, f'Perfil {perfil_id} não está disponível no plano {plan_name}.'
    
    return True, None


def check_max_perfis_sg(user_id: int, perfil_id: int):
    """
    Verifica se o usuário pode usar um perfil de SG específico.
    Retorna (pode_usar, mensagem_erro)
    """
    max_perfis = get_max_perfis_sg(user_id)
    
    if perfil_id > max_perfis:
        plan_config = get_user_plan_config(user_id)
        plan_name = plan_config.get('name', 'Free')
        return False, f'Perfil SG {perfil_id} não está disponível no plano {plan_name}.'
    
    return True, None

