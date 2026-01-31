import unittest
import sys
import os
import sqlite3
import uuid

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from database_manager import DatabaseManager
from repositories.business_repository import BusinessRepository

class TestBusinessRepository(unittest.TestCase):
    def setUp(self):
        """Use in-memory SQLite for testing"""
        # Note: DatabaseManager uses 'safe_db_utils.get_db_connection' which likely connects to a file.
        # Ideally we should mock the connection or use a test DB.
        # For this integration test, we'll try to use the real logic but transaction rollback if possible, 
        # OR just create a test record and delete it.
        self.db = DatabaseManager()
        self.repo = BusinessRepository(self.db)
        self.test_id = str(uuid.uuid4())
        self.owner_id = "test_owner" 
        
        # Manually insert a test business (assuming owner check might be needed or passed)
        # We need a user for foreign key? SQLite is lax if not enforced, but let's see.
        # If SQLite constraints are on, we might fail. 
        # But this is "Pre-Blitz", let's assume we can insert a business.
        
        # We first need an owner (User)
        cursor = self.db.conn.cursor()
        try:
             cursor.execute("INSERT OR IGNORE INTO Users (id, email, password_hash) VALUES (?, ?, ?)", 
                            (self.owner_id, "test@test.com", "hash"))
             self.db.conn.commit()
        except Exception:
             pass

        cursor.execute("""
            INSERT INTO Businesses (id, name, owner_id, is_active)
            VALUES (?, ?, ?, 1)
        """, (self.test_id, "Test Business", self.owner_id))
        self.db.conn.commit()

    def tearDown(self):
        cursor = self.db.conn.cursor()
        cursor.execute("DELETE FROM business_sources WHERE business_id = ?", (self.test_id,))
        cursor.execute("DELETE FROM Businesses WHERE id = ?", (self.test_id,))
        cursor.execute("DELETE FROM Users WHERE id = ?", (self.owner_id,))
        self.db.conn.commit()
        self.db.close()

    def test_update_yandex_fields_updates_both_tables(self):
        """Test that update_yandex_fields updates Businesses AND business_sources"""
        org_id = "12345"
        url = "https://yandex.ru/maps/org/12345"
        
        self.repo.update_yandex_fields(self.test_id, org_id, url)
        
        # Check Businesses table
        b = self.repo.get_by_id(self.test_id)
        self.assertEqual(b['yandex_org_id'], org_id)
        self.assertEqual(b['yandex_url'], url)
        
        # Check business_sources table
        source = self.repo.get_source_by_business_id(self.test_id, 'yandex')
        self.assertIsNotNone(source)
        self.assertEqual(source['external_id'], org_id)
        self.assertEqual(source['url'], url)
        
        # Test Update (Upsert)
        new_url = "https://yandex.ru/maps/org/NEW"
        self.repo.update_yandex_fields(self.test_id, org_id, new_url)
        
        source_updated = self.repo.get_source_by_business_id(self.test_id, 'yandex')
        self.assertEqual(source_updated['url'], new_url)

if __name__ == '__main__':
    unittest.main()
