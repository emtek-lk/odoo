from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Only chain managers may change roles: the roles decide who may record origin and processing events.
    trace_role_ids = fields.Many2many(
        'trace.role', 'trace_party_role_rel', 'partner_id', 'role_id', string='Supply Chain Roles',
        groups='trace_base.group_trace_manager')
    is_trace_party = fields.Boolean(
        string='Is a Supply Chain Party', compute='_compute_is_trace_party', store=True, compute_sudo=True)
    trace_region = fields.Char(string='Region')
    trace_certifications = fields.Text(string='Certifications')

    @api.depends('trace_role_ids')
    def _compute_is_trace_party(self):
        for partner in self:
            partner.is_trace_party = bool(partner.sudo().trace_role_ids)
