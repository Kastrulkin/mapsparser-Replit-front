"""
Golden Master Testing for Phase 3.5
Compares legacy API responses with new repository-based responses
"""
import json
import os
import sys
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def assert_json_equal(actual: dict, expected: dict, tolerance: float = 0.01, path: str = ""):
    """
    Compare two JSON objects with tolerance for float values.
    
    Args:
        actual: Actual JSON response
        expected: Expected JSON response (golden master)
        tolerance: Tolerance for float comparison
        path: Current path in JSON structure (for error messages)
    """
    if isinstance(expected, dict) and isinstance(actual, dict):
        # Check all keys in expected
        for key in expected:
            if key not in actual:
                raise AssertionError(f"Missing key at {path}.{key}")
            assert_json_equal(actual[key], expected[key], tolerance, f"{path}.{key}")
        
        # Check for extra keys in actual (warn but don't fail)
        for key in actual:
            if key not in expected:
                print(f"⚠️  Extra key in actual: {path}.{key}")
    
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            raise AssertionError(f"List length mismatch at {path}: expected {len(expected)}, got {len(actual)}")
        
        for i, (exp_item, act_item) in enumerate(zip(expected, actual)):
            assert_json_equal(act_item, exp_item, tolerance, f"{path}[{i}]")
    
    elif isinstance(expected, float) and isinstance(actual, (int, float)):
        if abs(expected - actual) > tolerance:
            raise AssertionError(f"Float mismatch at {path}: expected {expected}, got {actual} (tolerance: {tolerance})")
    
    elif expected != actual:
        raise AssertionError(f"Value mismatch at {path}: expected {expected}, got {actual}")


class GoldenMasterTest(unittest.TestCase):
    """Base class for Golden Master tests"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures directory"""
        cls.fixtures_dir = Path(__file__).parent / 'fixtures' / 'golden'
        cls.fixtures_dir.mkdir(parents=True, exist_ok=True)
    
    def load_golden(self, filename: str) -> dict:
        """Load golden master JSON file"""
        filepath = self.fixtures_dir / filename
        if not filepath.exists():
            self.skipTest(f"Golden master not found: {filename}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_golden(self, filename: str, data: dict):
        """Save golden master JSON file"""
        filepath = self.fixtures_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
        print(f"💾 Saved golden master: {filename}")


class TestBusinessesList(GoldenMasterTest):
    """Test businesses list endpoint"""
    
    def test_businesses_list_matches_golden(self):
        """
        Compare /api/businesses response with golden master.
        
        To generate golden master:
        1. Run legacy code
        2. Call this test with save_golden()
        3. Commit golden master to git
        """
        # TODO: Implement actual API call
        # For now, this is a template
        
        # Example:
        # response = client.get('/api/businesses')
        # actual = response.json
        # expected = self.load_golden('businesses_list.json')
        # assert_json_equal(actual, expected)
        
        self.skipTest("Not implemented yet - requires Flask test client setup")


if __name__ == '__main__':
    unittest.main()
