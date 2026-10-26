import unittest
from unittest.mock import patch
from flask import session
from app import create_app, db
from app.models import User, Role, EmailEnviado, create_default_roles

class BasicsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        create_default_roles()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_app_exists(self):
        self.assertIsNotNone(self.app)

    def test_app_is_testing(self):
        self.assertTrue(self.app.config['TESTING'])

    def test_main_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('visitante', response.get_data(as_text=True))

    @patch('app.main.views.send_email')
    def test_cadastro_notifica_ambos(self, mock_email):
        cfg = self.app.config
        mock_email.return_value = ([cfg['STUDENT_EMAIL'], cfg['FLASKY_ADMIN'], 'destino@example.com'], '[Flask] Novo usuário')
        response = self.client.post('/', data={'username': 'estudante01', 'email': 'destino@example.com'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.query.count(), 1)
        self.assertEqual(EmailEnviado.query.count(), 3)
        self.assertEqual(mock_email.call_args.args[0], [cfg['STUDENT_EMAIL'], cfg['FLASKY_ADMIN'], 'destino@example.com'])
        self.assertIn('Olá, estudante01!', response.get_data(as_text=True))
        with self.client.session_transaction() as sess:
            self.assertEqual(sess['name'], 'estudante01')
            self.assertFalse(sess['known'])

    @patch('app.main.views.send_email')
    def test_duplicidade_nao_envia_e_reconhece(self, mock_email):
        role = Role.query.filter_by(name='User').first()
        db.session.add(User(username='existente', role=role))
        db.session.commit()
        response = self.client.post('/', data={'username': 'existente', 'email': 'destino@example.com'}, follow_redirects=True)
        mock_email.assert_not_called()
        self.assertEqual(User.query.count(), 1)
        self.assertIn('Olá novamente, existente!', response.get_data(as_text=True))
        with self.client.session_transaction() as sess:
            self.assertEqual(sess['name'], 'existente')
            self.assertTrue(sess['known'])

    @patch('app.main.views.send_email')
    def test_falha_envio_impede_cadastro(self, mock_email):
        from app.email import EmailDeliveryError
        mock_email.side_effect = EmailDeliveryError('falha')
        self.client.post('/', data={'username': 'falha', 'email': 'destino@example.com'})
        self.assertEqual(User.query.count(), 0)
        self.assertEqual(EmailEnviado.query.count(), 0)
        with self.client.session_transaction() as sess:
            self.assertNotIn('name', sess)

    @patch('app.main.views.send_email')
    def test_usuario_existente_nao_dispara_segunda_notificacao(self, mock_email):
        cfg = self.app.config
        mock_email.return_value = ([cfg['STUDENT_EMAIL'], cfg['FLASKY_ADMIN'], 'destino@example.com'], '[Flask] Novo usuário')
        self.client.post('/', data={'username': 'aluno', 'email': 'destino@example.com'})
        self.client.post('/', data={'username': 'aluno', 'email': 'destino@example.com'})
        self.assertEqual(mock_email.call_count, 1)
        self.assertEqual(EmailEnviado.query.count(), 3)

    @patch('app.main.views.send_email')
    def test_email_invalido_nao_cadastra(self, mock_email):
        self.client.post('/', data={'username': 'invalido', 'email': 'sem-arroba'})
        mock_email.assert_not_called()
        self.assertEqual(User.query.count(), 0)

    @patch('app.email.requests.post')
    def test_sendgrid_payload_tres_destinos(self, post):
        from app.email import send_email
        self.app.config.update(API_KEY='fake', API_FROM='cadastro@example.com')
        post.return_value.status_code = 202
        role = Role.query.filter_by(name='User').first()
        user = User(username='teste', role=role)
        cfg = self.app.config
        recipients = [cfg['STUDENT_EMAIL'], cfg['FLASKY_ADMIN'], 'destino@example.com']
        send_email(recipients + ['destino@example.com'], 'Teste', 'mail/new_user',
                   student_id=cfg['STUDENT_ID'], student_name=cfg['STUDENT_NAME'], user=user)
        payload = post.call_args.kwargs['json']
        self.assertEqual([r['email'] for r in payload['personalizations'][0]['to']], recipients)
        self.assertIn('PT3038084', payload['content'][0]['value'])
        self.assertIn('Taissa Pieri', payload['content'][1]['value'])
        self.assertIn('teste', payload['content'][1]['value'])
