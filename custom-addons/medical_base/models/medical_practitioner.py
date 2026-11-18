from odoo import fields, models


class MedicalPractitioner(models.Model):
    _name = 'medical.practitioner'
    _description = 'Practitioner'
    _inherits = {'res.partner': 'partner_id'}
    _order = 'name'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='restrict', index=True)
    user_id = fields.Many2one('res.users', string='User', copy=False, index=True, ondelete='set null')
    specialty = fields.Char()
    licence_no = fields.Char(string='Licence No.', copy=False)
    institution_ids = fields.Many2many(
        'res.company', 'medical_practitioner_company_rel', 'practitioner_id', 'company_id',
        string='Institutions')
    active = fields.Boolean(default=True)

    _licence_uniq = models.Constraint('unique(licence_no)', 'This licence number is already registered.')
    _user_uniq = models.Constraint('unique(user_id)', 'This user is already a practitioner.')
