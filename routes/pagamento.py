"""
Rotas para pagamento e assinaturas via Stripe
"""
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import stripe
from dotenv import load_dotenv
from database import get_db_connection, close_db_connection

load_dotenv()

# Validar variáveis de ambiente obrigatórias
required_env_vars = [
    'STRIPE_SECRET_KEY',
    'STRIPE_PRODUCT_STARTER',
    'STRIPE_PRODUCT_PRO_PLUS',
    'DOMAIN'
]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Variáveis de ambiente obrigatórias não definidas: {', '.join(missing_vars)}")

# Configurar Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Criar Blueprint
pagamento_bp = Blueprint('pagamento', __name__, url_prefix='/pagamento')

# Mapeamento dos planos para os IDs dos produtos no Stripe (carregado do .env)
def get_plan_products():
    """Retorna o mapeamento de planos carregado do .env"""
    return {
        'aero-cartola-avancado': os.getenv('STRIPE_PRODUCT_AVANCADO', os.getenv('STRIPE_PRODUCT_STARTER')),  # Fallback para compatibilidade
        'aero-cartola-pro': os.getenv('STRIPE_PRODUCT_PRO', os.getenv('STRIPE_PRODUCT_PRO_PLUS')),  # Fallback para compatibilidade
        # Mantendo os antigos para compatibilidade
        'aero-cartola-starter': os.getenv('STRIPE_PRODUCT_STARTER'),
        'aero-cartola-pro-plus': os.getenv('STRIPE_PRODUCT_PRO_PLUS'),
    }

def get_domain():
    """Retorna o domínio base da aplicação"""
    return os.getenv('DOMAIN')

def login_required(f):
    """Decorator para proteger rotas que requerem autenticação"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Você precisa fazer login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@pagamento_bp.route('/')
@login_required
def index():
    """Página de seleção de planos"""
    return render_template('pagamento.html')

@pagamento_bp.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Cria uma sessão de checkout no Stripe"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            flash('Você precisa estar logado para realizar uma assinatura.', 'error')
            return redirect(url_for('login'))
        
        lookup_key = request.form.get('lookup_key')
        
        if not lookup_key:
            print("[ERRO] lookup_key não fornecido")
            flash('Plano não especificado.', 'error')
            return redirect(url_for('pagamento.index'))
        
        print(f"[INFO] Buscando plano: {lookup_key} para usuário {user_id}")
        
        # Busca o produto ID do mapeamento (carregado do .env)
        plan_products = get_plan_products()
        product_id = plan_products.get(lookup_key)
        
        if not product_id:
            print(f"[ERRO] Plano '{lookup_key}' não encontrado no mapeamento")
            flash('Plano não encontrado.', 'error')
            return redirect(url_for('pagamento.index'))
        
        print(f"[INFO] Produto ID: {product_id}")
        
        # Busca os preços ativos associados ao produto
        try:
            prices = stripe.Price.list(
                product=product_id,
                active=True,
                expand=['data.product']
            )
            print(f"[INFO] Preços encontrados: {len(prices.data)}")
        except stripe.error.StripeError as e:
            print(f"[ERRO] Erro ao buscar preços no Stripe: {e}")
            flash(f'Erro ao buscar preços: {str(e)}', 'error')
            return redirect(url_for('pagamento.index'))
        
        if not prices.data:
            print(f"[ERRO] Nenhum preço ativo encontrado para o produto {product_id}")
            flash('Nenhum preço ativo encontrado para este produto. Verifique no Stripe Dashboard.', 'error')
            return redirect(url_for('pagamento.index'))

        price_id = prices.data[0].id
        print(f"[INFO] Usando preço: {price_id}")

        # Buscar email do usuário para passar ao Stripe
        conn = get_db_connection()
        user_email = None
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('SELECT email FROM acw_users WHERE id = %s', (user_id,))
                user_row = cursor.fetchone()
                if user_row:
                    user_email = user_row[0]
            except Exception as e:
                print(f"[AVISO] Erro ao buscar email do usuário: {e}")
            finally:
                close_db_connection(conn)

        try:
            # Criar sessão de checkout com metadata do user_id
            checkout_session = stripe.checkout.Session.create(
                line_items=[
                    {
                        'price': price_id,
                        'quantity': 1,
                    },
                ],
                mode='subscription',
                customer_email=user_email,  # Email do usuário
                client_reference_id=str(user_id),  # ID do usuário (visível no Stripe Dashboard)
                metadata={
                    'user_id': str(user_id),  # Passar user_id como metadata
                    'lookup_key': lookup_key
                },
                success_url=get_domain() + url_for('pagamento.success') + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=get_domain() + url_for('pagamento.cancel'),
            )
            print(f"[OK] Sessão de checkout criada: {checkout_session.id} para usuário {user_id}")
            return redirect(checkout_session.url, code=303)
        except stripe.error.StripeError as e:
            print(f"[ERRO] Erro ao criar sessão de checkout no Stripe: {e}")
            flash(f'Erro ao criar sessão de checkout: {str(e)}', 'error')
            return redirect(url_for('pagamento.index'))
            
    except KeyError as e:
        print(f"[ERRO] Campo não encontrado no formulário: {e}")
        flash(f'Campo obrigatório não encontrado: {str(e)}', 'error')
        return redirect(url_for('pagamento.index'))
    except Exception as e:
        print(f"[ERRO] Erro inesperado ao criar sessão de checkout: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Erro no servidor: {str(e)}', 'error')
        return redirect(url_for('pagamento.index'))

@pagamento_bp.route('/success')
def success():
    """
    Página de sucesso após pagamento
    
    NOTA: Não usa @login_required porque a sessão pode expirar durante
    o redirecionamento do Stripe. A validação é feita via metadata do Stripe.
    """
    session_id = request.args.get('session_id')
    if not session_id:
        flash('Sessão de checkout não encontrada.', 'error')
        return redirect(url_for('login'))
    
    try:
        # Recuperar informações da sessão do Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        # Pegar user_id do metadata (mais confiável que a sessão Flask)
        metadata = checkout_session.metadata or {}
        user_id_from_metadata = metadata.get('user_id')
        
        if not user_id_from_metadata:
            flash('Erro: Não foi possível identificar o usuário da assinatura.', 'error')
            return redirect(url_for('login'))
        
        # Tentar pegar user_id da sessão atual (se ainda estiver logado)
        user_id_from_session = session.get('user_id')
        
        # Se a sessão expirou, fazer login automático ou mostrar mensagem
        if user_id_from_session and str(user_id_from_session) == str(user_id_from_metadata):
            # Sessão ainda válida, tudo ok
            return render_template('pagamento_success.html', session_id=session_id)
        else:
            # Sessão expirou, mas temos o user_id do metadata
            # Redirecionar para login com mensagem informativa
            flash('Pagamento confirmado! Faça login novamente para acessar sua conta.', 'success')
            # Opcional: você pode fazer login automático aqui se quiser
            return redirect(url_for('login'))
        
    except stripe.error.StripeError as e:
        print(f"[ERRO] Erro ao recuperar sessão do Stripe: {e}")
        flash(f'Erro ao verificar pagamento: {str(e)}', 'error')
        return redirect(url_for('login'))

@pagamento_bp.route('/cancel')
def cancel():
    """
    Página de cancelamento do checkout
    
    NOTA: Não usa @login_required porque a sessão pode expirar durante
    o redirecionamento do Stripe.
    """
    # Tentar manter a sessão se ainda estiver logado
    if not session.get('user_id'):
        flash('Checkout cancelado. Faça login para tentar novamente.', 'info')
        return redirect(url_for('login'))
    
    return render_template('pagamento_cancel.html')

@pagamento_bp.route('/create-portal-session', methods=['POST'])
@login_required
def customer_portal():
    """Cria uma sessão do portal do cliente do Stripe"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            flash('Você precisa estar logado.', 'error')
            return redirect(url_for('login'))
        
        checkout_session_id = request.form.get('session_id')
        if not checkout_session_id:
            flash('Sessão não encontrada.', 'error')
            return redirect(url_for('pagamento.index'))
        
        checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)
        
        # Verificar se o user_id na sessão corresponde ao metadata
        if checkout_session.metadata and checkout_session.metadata.get('user_id') != str(user_id):
            flash('Erro: Esta assinatura não pertence ao seu usuário.', 'error')
            return redirect(url_for('index'))
        
        # Criar sessão do portal do cliente
        portal_session = stripe.billing_portal.Session.create(
            customer=checkout_session.customer,
            return_url=get_domain() + url_for('pagamento.index'),
        )
        return redirect(portal_session.url, code=303)
    except stripe.error.StripeError as e:
        print(f"[ERRO] Erro ao criar sessão do portal: {e}")
        flash(f'Erro ao acessar portal: {str(e)}', 'error')
        return redirect(url_for('pagamento.index'))

@pagamento_bp.route('/webhook', methods=['POST'])
def webhook_received():
    """Endpoint para receber webhooks do Stripe"""
    import json
    
    # Replace this endpoint secret with your endpoint's unique secret
    # If you are testing with the CLI, find the secret by running 'stripe listen'
    # If you are using an endpoint defined with the API or dashboard, look in your webhook settings
    # at https://dashboard.stripe.com/webhooks
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    request_data = json.loads(request.data)

    if webhook_secret:
        # Retrieve the event by verifying the signature using the raw body and secret if webhook signing is configured.
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, sig_header=signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            print(f"[ERRO] Erro ao verificar assinatura do webhook: {e}")
            return jsonify({'error': str(e)}), 400
        # Get the type of webhook event sent - used to check the status of PaymentIntents.
        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']
    
    data_object = data['object']

    print(f'[INFO] Evento recebido: {event_type}')

    # Importar funções de planos
    from models.plans import (
        create_or_update_subscription,
        cancel_subscription,
        STRIPE_PLAN_MAPPING
    )
    from datetime import datetime
    
    # Processar eventos do Stripe
    if event_type == 'checkout.session.completed':
        print('[OK] Pagamento bem-sucedido!')
        checkout_session = data_object
        user_id = checkout_session.get('metadata', {}).get('user_id')
        lookup_key = checkout_session.get('metadata', {}).get('lookup_key')
        subscription_id = checkout_session.get('subscription')
        
        if user_id and subscription_id:
            # Mapear plano do Stripe para plano interno
            plano = STRIPE_PLAN_MAPPING.get(lookup_key, 'free')
            
            # Buscar detalhes da assinatura
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                customer_id = subscription.customer
                price_id = subscription.items.data[0].price.id if subscription.items.data else None
                
                # Salvar no banco
                success = create_or_update_subscription(
                    user_id=int(user_id),
                    stripe_subscription_id=subscription_id,
                    stripe_customer_id=customer_id,
                    plano=plano,
                    status=subscription.status,
                    stripe_price_id=price_id,
                    current_period_start=datetime.fromtimestamp(subscription.current_period_start),
                    current_period_end=datetime.fromtimestamp(subscription.current_period_end),
                    cancel_at_period_end=subscription.cancel_at_period_end,
                    canceled_at=datetime.fromtimestamp(subscription.canceled_at) if subscription.canceled_at else None
                )
                
                if success:
                    print(f'[OK] Assinatura salva no banco: {subscription_id} para user_id {user_id}')
                else:
                    print(f'[ERRO] Falha ao salvar assinatura no banco')
            except Exception as e:
                print(f'[ERRO] Erro ao processar checkout.session.completed: {e}')
        
    elif event_type == 'customer.subscription.created':
        print(f'[OK] Assinatura criada: {event["id"]}')
        subscription = data_object
        subscription_id = subscription['id']
        customer_id = subscription['customer']
        metadata = subscription.get('metadata', {})
        user_id = metadata.get('user_id')
        
        if user_id:
            # Tentar determinar o plano pelo price_id
            price_id = subscription['items']['data'][0]['price']['id'] if subscription['items']['data'] else None
            plano = 'avancado'  # Default, pode ser melhorado com busca reversa
            
            success = create_or_update_subscription(
                user_id=int(user_id),
                stripe_subscription_id=subscription_id,
                stripe_customer_id=customer_id,
                plano=plano,
                status=subscription['status'],
                stripe_price_id=price_id,
                current_period_start=datetime.fromtimestamp(subscription['current_period_start']),
                current_period_end=datetime.fromtimestamp(subscription['current_period_end']),
                cancel_at_period_end=subscription.get('cancel_at_period_end', False),
                canceled_at=datetime.fromtimestamp(subscription['canceled_at']) if subscription.get('canceled_at') else None
            )
            
            if success:
                print(f'[OK] Assinatura criada salva no banco: {subscription_id}')
        
    elif event_type == 'customer.subscription.updated':
        print(f'[OK] Assinatura atualizada: {event["id"]}')
        subscription = data_object
        subscription_id = subscription['id']
        customer_id = subscription['customer']
        metadata = subscription.get('metadata', {})
        user_id = metadata.get('user_id')
        
        # Se não tiver user_id no metadata, buscar do banco
        if not user_id:
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT user_id FROM acw_subscriptions
                        WHERE stripe_subscription_id = %s
                    ''', (subscription_id,))
                    result = cursor.fetchone()
                    if result:
                        user_id = result[0]
                except Exception as e:
                    print(f'[ERRO] Erro ao buscar user_id: {e}')
                finally:
                    close_db_connection(conn)
        
        if user_id:
            price_id = subscription['items']['data'][0]['price']['id'] if subscription['items']['data'] else None
            plano = 'avancado'  # Default
            
            success = create_or_update_subscription(
                user_id=int(user_id),
                stripe_subscription_id=subscription_id,
                stripe_customer_id=customer_id,
                plano=plano,
                status=subscription['status'],
                stripe_price_id=price_id,
                current_period_start=datetime.fromtimestamp(subscription['current_period_start']),
                current_period_end=datetime.fromtimestamp(subscription['current_period_end']),
                cancel_at_period_end=subscription.get('cancel_at_period_end', False),
                canceled_at=datetime.fromtimestamp(subscription['canceled_at']) if subscription.get('canceled_at') else None
            )
            
            if success:
                print(f'[OK] Assinatura atualizada no banco: {subscription_id}')
        
    elif event_type == 'customer.subscription.deleted':
        print(f'[OK] Assinatura cancelada: {event["id"]}')
        subscription = data_object
        subscription_id = subscription['id']
        canceled_at = datetime.fromtimestamp(subscription.get('canceled_at', datetime.now().timestamp()))
        
        success = cancel_subscription(subscription_id, canceled_at)
        if success:
            print(f'[OK] Assinatura cancelada no banco: {subscription_id}')
        
    elif event_type == 'customer.subscription.trial_will_end':
        print('[AVISO] Período de teste da assinatura está terminando')
        
    elif event_type == 'entitlements.active_entitlement_summary.updated':
        print(f'[OK] Resumo de direitos ativos atualizado: {event.id}')

    return jsonify({'status': 'success'})

