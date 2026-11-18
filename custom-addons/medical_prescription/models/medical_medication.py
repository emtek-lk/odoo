from odoo import fields, models


class MedicalMedication(models.Model):
    _name = 'medical.medication'
    _description = 'Medication'
    _order = 'name'

    name = fields.Char(required=True)
    generic_name = fields.Char()
    strength = fields.Char(help="e.g. 500 mg")
    form = fields.Selection(
        [('tablet', 'Tablet'), ('capsule', 'Capsule'), ('syrup', 'Syrup'), ('injection', 'Injection'),
         ('cream', 'Cream'), ('drops', 'Drops'), ('other', 'Other')], default='tablet')
    active = fields.Boolean(default=True)
