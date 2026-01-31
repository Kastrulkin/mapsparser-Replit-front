import unittest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.query_adapter import QueryAdapter

class TestQueryAdapter(unittest.TestCase):
    
    def test_simple_replacement(self):
        query = "SELECT * FROM users WHERE id = ?"
        params = (123,)
        new_query = QueryAdapter.adapt_query(query, params)
        self.assertEqual(new_query, "SELECT * FROM users WHERE id = %s")

    def test_multiple_params(self):
        query = "INSERT INTO t (a, b) VALUES (?, ?)"
        params = (1, 2)
        new_query = QueryAdapter.adapt_query(query, params)
        self.assertEqual(new_query, "INSERT INTO t (a, b) VALUES (%s, %s)")

    def test_question_mark_in_literal_single_quote(self):
        query = "SELECT * FROM questions WHERE text = 'What?' AND id = ?"
        params = (1,)
        # Should replace only the SECOND ?
        new_query = QueryAdapter.adapt_query(query, params)
        self.assertEqual(new_query, "SELECT * FROM questions WHERE text = 'What?' AND id = %s")

    def test_question_mark_in_literal_double_quote(self):
        query = 'SELECT * FROM "questions?" WHERE id = ?'
        params = (1,)
        new_query = QueryAdapter.adapt_query(query, params)
        self.assertEqual(new_query, 'SELECT * FROM "questions?" WHERE id = %s')

    def test_count_mismatch_raises(self):
        query = "SELECT * FROM t WHERE id = ?"
        params = (1, 2) # Too many params
        with self.assertRaises(ValueError):
            QueryAdapter.adapt_query(query, params)
            
    def test_count_mismatch_too_few(self):
        query = "SELECT * FROM t WHERE id = ? AND name = ?"
        params = (1,) 
        with self.assertRaises(ValueError):
            QueryAdapter.adapt_query(query, params)

    def test_adapt_params_dict(self):
        params = ({"key": "value"},)
        new_params = QueryAdapter.adapt_params(params)
        self.assertIsInstance(new_params[0], str)
        self.assertIn('"key": "value"', new_params[0])

if __name__ == '__main__':
    unittest.main()
