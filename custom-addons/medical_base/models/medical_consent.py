from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MedicalConsent(models.Model):
    _name = 'medical.consent'
    _description = 'Consent'
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'

    patient_id = fields.Many2one('medical.patient', required=True, index=True, ondelete='cascade', tracking=True)
    patient_user_id = fields.Many2one('res.users', related='patient_id.user_id', store=True, index=True)
    practitioner_id = fields.Many2one('medical.practitioner', string='Practitioner', index=True, tracking=True)
    grantee_company_id = fields.Many2one('res.company', string='Institution', index=True, tracking=True)
    grantee_user_id = fields.Many2one('res.users', related='practitioner_id.user_id', store=True, index=True)
    scope = fields.Selection(
        [('all', 'Everything'), ('encounter', 'Encounters'), ('prescription', 'Prescriptions'), ('lab', 'Lab')],
        required=True, default='all', tracking=True)
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Valid Until', help="Leave empty for no expiry.", tracking=True)
    state = fields.Selection(
        [('active', 'Active'), ('revoked', 'Revoked'), ('expired', 'Expired')],
        default='active', required=True, tracking=True, index=True)
    method = fields.Selection(
        [('portal', 'Patient (portal)'), ('in_person', 'In person')], required=True, default='portal')
    evidence_ids = fields.Many2many('ir.attachment', string='Evidence', help="Signed form for in-person consent.")
    grantee_name = fields.Char(compute='_compute_grantee_name', compute_sudo=True)

    @api.depends('practitioner_id', 'grantee_company_id')
    def _compute_grantee_name(self):
        for consent in self:
            consent.grantee_name = consent.practitioner_id.name or consent.grantee_company_id.name or ''

    @api.constrains('practitioner_id', 'grantee_company_id')
    def _check_grantee(self):
        if any(bool(c.practitioner_id) == bool(c.grantee_company_id) for c in self):
            raise ValidationError(self.env._("Choose either a practitioner or an institution, not both and not neither."))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        if any(c.date_to and c.date_to < c.date_from for c in self):
            raise ValidationError(self.env._("The end date must not be before the start date."))

    @api.constrains('method', 'evidence_ids')
    def _check_evidence(self):
        if any(c.method == 'in_person' and not c.evidence_ids for c in self):
            raise ValidationError(self.env._("In-person consent needs an attached evidence file."))

    def action_revoke(self):
        self.write({'state': 'revoked'})

    @api.model
    def _cron_expire_consents(self):
        today = fields.Date.context_today(self)
        self.search([('state', '=', 'active'), ('date_to', '<', today)]).write({'state': 'expired'})
