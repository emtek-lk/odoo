from odoo import fields, models


class MedicalAccessLog(models.Model):
    _name = 'medical.access.log'
    _description = 'Access Log'
    _order = 'id desc'

    user_id = fields.Many2one('res.users', string='Viewed By', required=True, readonly=True, index=True)
    accessor_company_id = fields.Many2one('res.company', string='Viewer Institution', readonly=True)
    owner_company_id = fields.Many2one('res.company', string='Record Owner', readonly=True, index=True)
    patient_id = fields.Many2one('medical.patient', required=True, readonly=True, index=True, ondelete='cascade')
    patient_user_id = fields.Many2one('res.users', related='patient_id.user_id', store=True, index=True)
    res_model = fields.Char(readonly=True)
    res_id = fields.Integer(readonly=True)
    summary = fields.Char(readonly=True)
    create_date = fields.Datetime(string='When', readonly=True)
