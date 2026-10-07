import os
import unittest
from unittest.mock import MagicMock, patch

for name, value in {
    "POSTGRES_HOST": "localhost",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_DB": "test",
    "STRIPE_SECRET_KEY": "sk_test_fixture",
    "DOMAIN": "http://localhost",
}.items():
    os.environ.setdefault(name, value)

import app as web
import routes.player_availability as availability


class PlayerAvailabilityContextTests(unittest.TestCase):
    def test_context_only_returns_selected_team_round_without_loading_candidates(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value
        cursor.fetchone.return_value = (1,)
        client = web.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 42
            session["selected_team_id"] = 123

        with patch.object(availability, "get_db_connection", return_value=conn), \
             patch.object(availability, "close_db_connection"):
            response = client.get(
                "/api/player-availability/candidates?context_only=1&season=2026&round_number=28"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"team_id": 123, "season": 2026, "round_number": 28})
        cursor.execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
