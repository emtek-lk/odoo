from odoo import fields, models


class MedicalLabTest(models.Model):
    _name = 'medical.lab.test'
    _description = 'Lab Test'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char()
    unit = fields.Char()
    ref_min = fields.Float(string='Normal From')
    ref_max = fields.Float(string='Normal To')
    active = fields.Boolean(default=True)
