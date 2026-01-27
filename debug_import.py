import sys
import os

# Set up paths like main.py does
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    print("Attempting to import wordstat_bp...")
    from src.api.wordstat_api import wordstat_bp
    print("✅ Import successful!")
    print(f"Blueprint name: {wordstat_bp.name}")
    print(f"URL prefix: {wordstat_bp.url_prefix}")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
