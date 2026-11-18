from odoo import api, fields, models
from odoo.exceptions import UserError


class MedicalEncounter(models.Model):
    _name = 'medical.encounter'
    _description = 'Encounter'
    _inherit = ['medical.record.mixin', 'mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New')
    date = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True)
    practitioner_id = fields.Many2one(
        'medical.practitioner', string='Practitioner', required=True, tracking=True,
        default=lambda self: self.env['medical.practitioner'].search([('user_id', '=', self.env.uid)], limit=1))
    encounter_type = fields.Selection(
        [('consultation', 'Consultation'), ('emergency', 'Emergency'), ('admission', 'Admission'),
         ('followup', 'Follow-up'), ('procedure', 'Procedure')],
        required=True, default='consultation')
    complaint = fields.Text(string='Chief Complaint')
    diagnosis = fields.Text()
    notes = fields.Html()
    addendum_ids = fields.One2many('medical.encounter.addendum', 'encounter_id', string='Addenda')
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done'), ('cancel', 'Cancelled')],
                             default='draft', required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('medical.encounter') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        locked = {'complaint', 'diagnosis', 'notes', 'date', 'practitioner_id', 'patient_id', 'encounter_type'}
        if locked & set(vals) and any(e.state != 'draft' for e in self):
            raise UserError(self.env._("A finished encounter is locked. Add an addendum instead."))
        return super().write(vals)

    def unlink(self):
        raise UserError(self.env._("Clinical records cannot be deleted. Cancel the encounter instead."))

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def _history_date(self):
        return self.date

    def _history_title(self):
        return ' - '.join(filter(None, [self.name, self.diagnosis or self.complaint]))


class MedicalEncounterAddendum(models.Model):
    _name = 'medical.encounter.addendum'
    _description = 'Encounter Addendum'
    _order = 'id'

    encounter_id = fields.Many2one('medical.encounter', required=True, ondelete='cascade', index=True)
    note = fields.Text(required=True)
    author_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)
    create_date = fields.Datetime(readonly=True)
