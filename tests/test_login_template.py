"""Regressions for the native-account login screen."""
import unittest
from pathlib import Path


class LoginTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = (Path(__file__).resolve().parents[1] / 'templates' / 'login.html').read_text(encoding='utf-8')

    def test_no_external_provider_buttons(self):
        for icon in ('fa-google', 'fa-github', 'fa-apple'):
            self.assertNotIn(icon, self.template)

    def test_registration_redirect_preserves_server_messages(self):
        self.assertIn("switchTab('register', true)", self.template)
        self.assertIn('flashContainer && !preserveMessages', self.template)


if __name__ == '__main__':
    unittest.main()
