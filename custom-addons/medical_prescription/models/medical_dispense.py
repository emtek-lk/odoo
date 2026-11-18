from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MedicalDispense(models.Model):
    _name = 'medical.dispense'
    _description = 'Dispensing'
    _inherit = ['medical.record.mixin', 'mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New')
    date = fields.Datetime(required=True, default=fields.Datetime.now)
    prescription_id = fields.Many2one('medical.prescription', required=True, index=True, ondelete='restrict')
    patient_id = fields.Many2one(related='prescription_id.patient_id', store=True, readonly=True, required=False)
    pharmacist_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)
    line_ids = fields.One2many('medical.dispense.line', 'dispense_id', string='Dispensed')
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done'), ('cancel', 'Cancelled')],
                             default='draft', required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('medical.dispense') or 'New'
        return super().create(vals_list)

    def unlink(self):
        raise UserError(self.env._("Clinical records cannot be deleted. Cancel the dispensing instead."))

    def action_done(self):
        for dispense in self:
            if dispense.prescription_id.state not in ('issued', 'partial'):
                raise UserError(self.env._("Only issued prescriptions can be dispensed."))
            if not dispense.line_ids:
                raise UserError(self.env._("Add at least one dispensed medication."))
        self.write({'state': 'done'})
        # sudo: the pharmacy updates the prescription counters although it cannot edit the prescription
        self.prescription_id.sudo().line_ids._compute_quantity_dispensed()
        self.prescription_id.sudo()._update_dispense_state()

    def action_cancel(self):
        self.write({'state': 'cancel'})
        self.prescription_id.sudo().line_ids._compute_quantity_dispensed()
        self.prescription_id.sudo()._update_dispense_state()

    def _history_date(self):
        return self.date

    def _history_kind(self):
        return self.env._("Dispensing")


class MedicalDispenseLine(models.Model):
    _name = 'medical.dispense.line'
    _description = 'Dispensing Line'

    dispense_id = fields.Many2one('medical.dispense', required=True, ondelete='cascade', index=True)
    prescription_line_id = fields.Many2one(
        'medical.prescription.line', string='Prescribed', required=True,
        domain="[('prescription_id', '=', parent.prescription_id)]")
    medication_id = fields.Many2one(related='prescription_line_id.medication_id')
    quantity = fields.Float(required=True)

    @api.constrains('quantity', 'prescription_line_id')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(self.env._("The dispensed quantity must be positive."))
            presc = line.prescription_line_id.sudo()
            total = sum(
                d.quantity for d in self.sudo().search([
                    ('prescription_line_id', '=', presc.id), ('dispense_id.state', '!=', 'cancel')]))
            if total > presc.quantity:
                raise ValidationError(self.env._("You cannot dispense more than was prescribed."))
