"""Contratos dos planos e APIs, sem acesso ao banco ou ao Cartola."""
import os
import json
import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from unittest.mock import MagicMock, patch

for name, value in {
    'POSTGRES_HOST': 'localhost', 'POSTGRES_USER': 'test',
    'POSTGRES_PASSWORD': 'test', 'POSTGRES_DB': 'test',
    'STRIPE_SECRET_KEY': 'sk_test_fixture', 'STRIPE_PRODUCT_STARTER': 'fixture',
    'STRIPE_PRODUCT_PRO_PLUS': 'fixture', 'DOMAIN': 'http://localhost',
}.items():
    os.environ.setdefault(name, value)

import app as web
from models.plans import PLANS_CONFIG
from utils.plan_policy import DEFAULT_PRIORITIES


class PlanApiTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.plan = 'free'
        self.user = {'id': 101, 'username': 'tier-test', 'is_admin': False, 'plano': 'free'}
        self.conn = MagicMock()
        self.conn.cursor.return_value.fetchone.return_value = (30,)
        self.stack.enter_context(patch.object(web, 'get_db_connection', return_value=self.conn))
        self.stack.enter_context(patch.object(web, 'close_db_connection'))
        self.stack.enter_context(patch.object(web, 'get_current_user', return_value=self.user))
        self.stack.enter_context(patch('models.plans.get_user_plan_config', side_effect=lambda _: PLANS_CONFIG[self.plan].copy()))
        self.stack.enter_context(redirect_stdout(StringIO()))
        web.app.config.update(TESTING=True)
        self.client = web.app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = self.user['id']
            session['selected_team_id'] = 501

    def test_information_and_single_team_send_available_to_every_tier(self):
        for plan in PLANS_CONFIG:
            with self.subTest(plan=plan):
                self.plan = plan
                response = self.client.get('/api/user/permissions')
                self.assertEqual(response.status_code, 200)
                permissions = response.json['permissions']
                for feature in ('rankingCompleto', 'estatisticasAvancadas', 'podeEscalar', 'verEscalacaoIdealCompleta'):
                    self.assertTrue(permissions[feature], feature)

    def test_weight_writes_enforced_by_api(self):
        for plan in PLANS_CONFIG:
            with self.subTest(plan=plan):
                self.plan = plan
                self.conn.commit.reset_mock()
                response = self.client.post('/api/modulos/atacante/pesos', json={'FATOR_MEDIA': 2.5})
                self.assertEqual(response.status_code, 403 if plan == 'free' else 200)
                if plan == 'free':
                    self.conn.commit.assert_not_called()

    def test_basic_formation_captain_and_luxury_configuration_is_free(self):
        with patch('models.user_escalacao_config.create_user_escalacao_config_table'), \
             patch('models.user_escalacao_config.upsert_user_escalacao_config') as save:
            response = self.client.post('/api/escalacao-ideal/config', json={
                'formation': '4-4-2', 'posicao_capitao': 'meias',
                'posicao_reserva_luxo': 'laterais', 'prioridades': DEFAULT_PRIORITIES,
            })
        self.assertEqual(response.status_code, 200)
        save.assert_called_once()

    def test_weight_values_must_be_finite_numbers(self):
        self.plan = 'pro'
        for value in (None, True, '', 'abc', '2.5junk', 'NaN', 'Infinity', {}, []):
            with self.subTest(value=value):
                self.conn.commit.reset_mock()
                response = self.client.post('/api/modulos/atacante/pesos', json={'FATOR_MEDIA': value})
                self.assertEqual(response.status_code, 400)
                self.conn.commit.assert_not_called()

    def test_decimal_weight_updates_preserve_other_weights_and_invalidate_ranking(self):
        self.plan = 'avancado'
        cursor = self.conn.cursor.return_value
        cursor.fetchone.return_value = (30, {'FATOR_MEDIA': 2.4, 'FATOR_G': 6.5})
        response = self.client.post('/api/modulos/atacante/pesos', json={'FATOR_MEDIA': '2,51'})
        self.assertEqual(response.status_code, 200)
        updates = [call.args for call in cursor.execute.call_args_list if 'UPDATE acw_posicao_weights' in call.args[0]]
        self.assertEqual(json.loads(updates[0][1][0]), {'FATOR_MEDIA': 2.51, 'FATOR_G': 6.5})
        deletes = [call.args for call in cursor.execute.call_args_list if 'DELETE FROM acw_rankings_teams' in call.args[0]]
        self.assertEqual(deletes[0][1], (101, 501, 5))

    def test_pro_options_cannot_be_written_by_other_tiers(self):
        for plan in PLANS_CONFIG:
            for option in ('hack_goleiro', 'fechar_defesa', 'prioridades'):
                with self.subTest(plan=plan, option=option):
                    self.plan = plan
                    value = 'goleiros,laterais,meias,zagueiros,atacantes,treinadores' if option == 'prioridades' else True
                    with patch('models.user_escalacao_config.create_user_escalacao_config_table'), \
                         patch('models.user_escalacao_config.upsert_user_escalacao_config') as save:
                        response = self.client.post('/api/escalacao-ideal/config', json={option: value})
                    self.assertEqual(response.status_code, 200 if plan == 'pro' else 403)
                    if plan != 'pro':
                        save.assert_not_called()

    def test_downgrade_deactivates_old_pro_options_in_reads(self):
        old_config = dict(formation='4-3-3', hack_goleiro=True, fechar_defesa=True,
                          posicao_capitao='atacantes', prioridades='goleiros,laterais,meias,zagueiros,atacantes,tecnicos')
        with patch('models.user_escalacao_config.create_user_escalacao_config_table'), \
             patch('models.user_escalacao_config.get_user_escalacao_config', return_value=old_config):
            response = self.client.get('/api/escalacao-ideal/config')
        self.assertFalse(response.json['hack_goleiro'])
        self.assertFalse(response.json['fechar_defesa'])
        self.assertEqual(response.json['prioridades'], DEFAULT_PRIORITIES)
        self.assertTrue(old_config['hack_goleiro'])  # Sem apagar configuração persistida.

    def test_all_round_profiles_are_available_on_every_tier(self):
        cursor = self.conn.cursor.return_value
        cursor.fetchall.return_value = [(10,), (20,), (30,), (40,), (50,), (60,)]
        with patch('models.user_configurations.create_user_configurations_table'), \
             patch.object(web, 'get_all_user_teams', return_value=[{'id': 501}]), \
             patch('models.user_configurations.create_user_configuration') as save:
            for plan in PLANS_CONFIG:
                with self.subTest(plan=plan):
                    self.plan = plan
                    response = self.client.post('/salvar-configuracao-perfis', data={
                        'perfil_peso_jogo': '60', 'perfil_peso_sg': '60'
                    })
                    self.assertEqual(response.location, '/modulos')
                    save.assert_called_once()
                    save.reset_mock()
            response = self.client.post('/salvar-configuracao-perfis', data={
                'perfil_peso_jogo': '999', 'perfil_peso_sg': '60'
            })
            self.assertEqual(response.status_code, 302)
            save.assert_not_called()
            response = self.client.post('/salvar-configuracao-perfis', data={'perfil_peso_jogo': 'invalid'})
            self.assertEqual(response.status_code, 302)
            save.assert_not_called()

    def test_team_limit_checked_before_gateway_call(self):
        for plan, count, expected in (('free', 1, 403), ('avancado', 2, 403), ('pro', 200, 200)):
            with self.subTest(plan=plan), patch.object(web, 'get_all_user_teams', return_value=[{}] * count), \
                 patch.object(web, 'render_template', return_value='fixture'), patch('requests.post') as gateway:
                self.plan = plan
                response = self.client.post('/associar-credenciais', data={})
                self.assertEqual(response.status_code, expected)
                gateway.assert_not_called()

    def test_send_for_own_team_works_on_free_with_mock_cartola(self):
        positions = {'goleiros': 1, 'laterais': 2, 'zagueiros': 2, 'meias': 3, 'atacantes': 3, 'treinadores': 1}
        athlete_id = 1
        starters = {}
        for position, count in positions.items():
            starters[position] = []
            for _ in range(count):
                starters[position].append({'atleta_id': athlete_id, 'apelido': 'Fixture', 'eh_capitao': athlete_id == 9})
                athlete_id += 1
        team = {'id': 501, 'user_id': 101, 'access_token': 'fixture-token'}
        result = MagicMock(status_code=200)
        result.json.return_value = {'mensagem': 'Time Escalado! Boa Sorte!'}
        with patch.object(web, '_get_player_availability_rules', return_value={'saved_ids': set()}), \
             patch('models.teams.get_team', return_value=team) as lookup, \
             patch('requests.post', return_value=result) as cartola:
            response = self.client.post('/api/escalacao-ideal/escalar', json={'escalacao': {'titulares': starters, 'reservas': {}}})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])
        lookup.assert_called_once_with(self.conn, 501, 101)
        self.assertEqual(len(cartola.call_args.kwargs['json']['atletas']), 12)
        self.assertEqual(cartola.call_args.kwargs['json']['capitao'], 9)


if __name__ == '__main__':
    unittest.main()
