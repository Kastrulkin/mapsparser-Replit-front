from flask import Blueprint, request, jsonify
from services.prospecting_service import ProspectingService
from database_manager import DatabaseManager
import threading

admin_prospecting_bp = Blueprint('admin_prospecting', __name__)

@admin_prospecting_bp.route('/api/admin/prospecting/search', methods=['POST'])
def search_businesses():
    """Search for businesses using Apify"""
    try:
        data = request.json
        query = data.get('query')
        location = data.get('location')
        limit = data.get('limit', 50)

        if not query or not location:
            return jsonify({'error': 'Query and location are required'}), 400

        service = ProspectingService()
        if not service.client:
            return jsonify({'error': 'APIFY_TOKEN is not configured'}), 500

        # This might take a while, so ideally it should be async or background job.
        # For now, we'll keep it synchronous but warn about timeout, or user should increase timeout.
        # Apify actors can take minutes.
        # TODO: Move to background task if it's too slow.
        
        results = service.search_businesses(query, location, limit)
        return jsonify({'results': results})
    except Exception as e:
        print(f"Error in prospecting search: {e}")
        return jsonify({'error': str(e)}), 500

@admin_prospecting_bp.route('/api/admin/prospecting/leads', methods=['GET'])
def get_leads():
    """Get all saved leads"""
    try:
        with DatabaseManager() as db:
            leads = db.get_all_leads()
        return jsonify({'leads': leads})
    except Exception as e:
        print(f"Error getting leads: {e}")
        return jsonify({'error': str(e)}), 500

@admin_prospecting_bp.route('/api/admin/prospecting/save', methods=['POST'])
def save_lead():
    """Save a lead to database"""
    try:
        data = request.json
        lead_data = data.get('lead')
        
        if not lead_data:
            return jsonify({'error': 'Lead data is required'}), 400

        with DatabaseManager() as db:
            lead_id = db.save_lead(lead_data)
            
        return jsonify({'success': True, 'lead_id': lead_id})
    except Exception as e:
        print(f"Error saving lead: {e}")
        return jsonify({'error': str(e)}), 500

@admin_prospecting_bp.route('/api/admin/prospecting/lead/<string:lead_id>/status', methods=['POST'])
def update_lead_status(lead_id):
    """Update lead status"""
    try:
        data = request.json
        status = data.get('status')
        
        if not status:
            return jsonify({'error': 'Status is required'}), 400

        with DatabaseManager() as db:
            success = db.update_lead_status(lead_id, status)
            
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Lead not found'}), 404
    except Exception as e:
        print(f"Error updating lead status: {e}")
        return jsonify({'error': str(e)}), 500

@admin_prospecting_bp.route('/api/admin/prospecting/lead/<string:lead_id>', methods=['DELETE'])
def delete_lead(lead_id):
    """Delete a lead"""
    try:
        with DatabaseManager() as db:
            success = db.delete_lead(lead_id)
            
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Lead not found'}), 404
    except Exception as e:
        print(f"Error deleting lead: {e}")
        return jsonify({'error': str(e)}), 500
