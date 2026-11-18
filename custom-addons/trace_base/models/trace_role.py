from odoo import fields, models


class TraceRole(models.Model):
    _name = 'trace.role'
    _description = 'Supply Chain Role'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)

    _code_uniq = models.Constraint('unique(code)', 'The role code must be unique.')
