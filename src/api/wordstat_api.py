from flask import Blueprint, jsonify
import sqlite3
import subprocess
import os
import sys

# Adjust path to import modules from src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database_manager import get_db_connection

wordstat_bp = Blueprint('wordstat_api', __name__, url_prefix='/api/wordstat')

@wordstat_bp.route('/keywords', methods=['GET'])
def get_keywords():
    """Get all popular keywords with simplified categorization"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get all keywords ordered by views
        cursor.execute("""
            SELECT keyword, views, category, updated_at 
            FROM WordstatKeywords 
            ORDER BY views DESC
        """)
        
        rows = cursor.fetchall()
        keywords = [dict(row) for row in rows]
        
        # Group by category
        by_category = {}
        for k in keywords:
            cat = k['category'] or 'other'
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(k)
            
        return jsonify({
            'success': True,
            'count': len(keywords),
            'items': keywords,
            'grouped': by_category
        })
        
    except Exception as e:
        print(f"Error fetching wordstat keywords: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

@wordstat_bp.route('/update', methods=['POST'])
def trigger_update():
    """Trigger the background update script"""
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'update_wordstat_data.py')
        
        # Run in background (nohup) or wait? 
        # Since it can take time, normally background. But user might want feedback.
        # Let's run it synchronously for now if it's not too long, or use check_update_needed logic.
        # Actually, let's run it as a subprocess.
        
        # Check if auth token is set
        # We can't easily check env vars passed to subprocess unless we pass them.
        # Assuming environment is set up.
        
        # Using subprocess to run the script
        process = subprocess.Popen(
            ['python3', script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for a bit (timeout) to see if it crashes immediately, otherwise return accepted.
        try:
            stdout, stderr = process.communicate(timeout=2)
            if process.returncode != 0:
                 return jsonify({'success': False, 'error': f"Script failed: {stderr}"}), 500
        except subprocess.TimeoutExpired:
            # Running in background
            pass
            
        return jsonify({
            'success': True, 
            'message': 'Update started manually. Check back in a few minutes.'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@wordstat_bp.route('/metadata', methods=['GET'])
def get_metadata():
    """Get metadata about last update"""
    try:
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'prompts')
        metadata_path = os.path.join(prompts_dir, 'wordstat_metadata.json')
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                import json
                data = json.load(f)
                return jsonify({'success': True, 'metadata': data})
        else:
            return jsonify({'success': False, 'error': 'No metadata found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
