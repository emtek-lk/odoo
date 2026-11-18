from odoo import fields, models


class TraceProduct(models.Model):
    _name = 'trace.product'
    _description = 'Traceable Product'
    _order = 'name'

    name = fields.Char(required=True)
    category = fields.Selection(
        [('crop', 'Crop'), ('ingredient', 'Ingredient'), ('processed', 'Processed Product')],
        required=True, default='crop')
    unit = fields.Selection(
        [('kg', 'kg'), ('g', 'g'), ('t', 'tonne'), ('l', 'litre'), ('unit', 'unit')], required=True, default='kg')
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint('unique(name)', 'A product with this name already exists.')
