from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    trace_party_id = fields.Many2one(
        'res.partner', string='Acts For (Supply Chain)', compute='_compute_trace_party_id',
        help="The organisation this user acts for in the supply chain.")

    @api.depends('partner_id.commercial_partner_id')
    def _compute_trace_party_id(self):
        for user in self:
            user.trace_party_id = user.partner_id.commercial_partner_id
