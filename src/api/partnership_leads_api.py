"""Partnership lead lifecycle routes."""
from __future__ import annotations

from flask import Blueprint

from services import partnership_leads_service as service

partnership_leads_bp = Blueprint("partnership_leads_api", __name__)

@partnership_leads_bp.route('/api/partnership/leads', methods=['GET'])
def partnership_list_leads():
    return service.partnership_list_leads()

@partnership_leads_bp.route('/api/partnership/leads/<string:lead_id>', methods=['PATCH'])
def partnership_update_lead(lead_id):
    return service.partnership_update_lead(lead_id)

@partnership_leads_bp.route('/api/partnership/leads/<string:lead_id>/manual-contact', methods=['POST'])
def partnership_mark_lead_manual_contact(lead_id):
    return service.partnership_mark_lead_manual_contact(lead_id)

@partnership_leads_bp.route('/api/partnership/leads/bulk-update', methods=['POST'])
def partnership_bulk_update_leads():
    return service.partnership_bulk_update_leads()

@partnership_leads_bp.route('/api/partnership/leads/<string:lead_id>', methods=['DELETE'])
def partnership_delete_lead(lead_id):
    return service.partnership_delete_lead(lead_id)

@partnership_leads_bp.route('/api/partnership/leads/bulk-delete', methods=['POST'])
def partnership_bulk_delete_leads():
    return service.partnership_bulk_delete_leads()

@partnership_leads_bp.route('/api/partnership/leads/<string:lead_id>/prepare-room', methods=['POST'])
def partnership_prepare_sales_room(lead_id):
    return service.partnership_prepare_sales_room(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/status', methods=['POST'])
def update_lead_status(lead_id):
    return service.update_lead_status(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/manual-contact', methods=['POST'])
def mark_lead_manual_contact(lead_id):
    return service.mark_lead_manual_contact(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/comment', methods=['POST'])
def add_lead_comment(lead_id):
    return service.add_lead_comment(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/timeline', methods=['GET'])
def get_lead_timeline(lead_id):
    return service.get_lead_timeline(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/shortlist', methods=['POST'])
def review_lead_shortlist(lead_id):
    return service.review_lead_shortlist(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/select', methods=['POST'])
def select_lead_for_outreach(lead_id):
    return service.select_lead_for_outreach(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/channel', methods=['POST'])
def select_outreach_channel(lead_id):
    return service.select_outreach_channel(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/contacts', methods=['POST'])
def update_lead_contacts(lead_id):
    return service.update_lead_contacts(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>/language', methods=['POST'])
def update_lead_language(lead_id):
    return service.update_lead_language(lead_id)

@partnership_leads_bp.route('/api/admin/prospecting/lead/<string:lead_id>', methods=['DELETE'])
def delete_lead(lead_id):
    return service.delete_lead(lead_id)
