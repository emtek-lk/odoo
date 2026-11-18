from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    medical_type = fields.Selection(
        [('hospital', 'Hospital'), ('clinic', 'Clinic'), ('lab', 'Laboratory'), ('pharmacy', 'Pharmacy')],
        string='Institution Type')
    medical_licence = fields.Char(string='Medical Licence No.')
