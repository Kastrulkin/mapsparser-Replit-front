
import unittest
from unittest.mock import MagicMock
import sqlite3

# Mock implementation of the refactored function
def _sync_parsed_services_to_db_mock(business_id: str, products: list, user_id: str, conn: sqlite3.Connection):
    if not products:
        return

    # STRICT CHECK
    if not user_id:
        raise ValueError("user_id (str) is required for service sync")

    cursor = conn.cursor()
    # Logic simulation: using user_id in insert
    for product in products:
        cursor.execute("INSERT INTO UserServices (user_id) VALUES (?)", (user_id,))

class TestServicesSyncLogic(unittest.TestCase):
    def setUp(self):
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    def test_sync_with_valid_user_id(self):
        products = [{'items': [{'name': 'Test'}]}]
        user_id = "user_123"
        
        _sync_parsed_services_to_db_mock("biz_123", products, user_id, self.mock_conn)
        
        # Verify passed to execute
        self.mock_cursor.execute.assert_called()
        call_args = self.mock_cursor.execute.call_args
        self.assertIn("INSERT INTO UserServices", call_args[0][0])
        self.assertEqual(call_args[0][1], (user_id,))

    def test_sync_with_none_user_id(self):
        products = [{'items': [{'name': 'Test'}]}]
        user_id = None
        
        with self.assertRaises(ValueError) as cm:
             _sync_parsed_services_to_db_mock("biz_123", products, user_id, self.mock_conn)
        
        self.assertIn("user_id (str) is required", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
