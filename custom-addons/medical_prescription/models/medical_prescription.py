from odoo import api, fields, models
from odoo.exceptions import UserError


class MedicalPrescription(models.Model):
    _name = 'medical.prescription'
    _description = 'Prescription'
    _inherit = ['medical.record.mixin', 'mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New')
    date = fields.Datetime(required=True, default=fields.Datetime.now)
    practitioner_id = fields.Many2one(
        'medical.practitioner', string='Prescriber', required=True,
        default=lambda self: self.env['medical.practitioner'].search([('user_id', '=', self.env.uid)], limit=1))
    encounter_id = fields.Many2one(
        'medical.encounter', string='Encounter', domain="[('patient_id', '=', patient_id)]", check_company=True)
    pharmacy_company_id = fields.Many2one(
        'res.company', string='Pharmacy', domain=[('medical_type', '=', 'pharmacy')],
        help="The pharmacy the patient chose. It may read and dispense this prescription.")
    pharmacy_name = fields.Char(related='pharmacy_company_id.name', store=True)
    line_ids = fields.One2many('medical.prescription.line', 'prescription_id', string='Medications')
    dispense_ids = fields.One2many('medical.dispense', 'prescription_id', string='Dispensing')
    notes = fields.Text()
    state = fields.Selection(
        [('draft', 'Draft'), ('issued', 'Issued'), ('partial', 'Partly Dispensed'),
         ('dispensed', 'Dispensed'), ('cancel', 'Cancelled')],
        default='draft', required=True, tracking=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('medical.prescription') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        locked = {'patient_id', 'practitioner_id', 'line_ids', 'date', 'encounter_id'}
        if locked & set(vals) and any(p.state != 'draft' for p in self):
            raise UserError(self.env._("An issued prescription cannot be changed. Cancel it and write a new one."))
        return super().write(vals)

    def unlink(self):
        raise UserError(self.env._("Clinical records cannot be deleted. Cancel the prescription instead."))

    def action_issue(self):
        for prescription in self:
            if not prescription.line_ids:
                raise UserError(self.env._("Add at least one medication before issuing."))
        self.write({'state': 'issued'})

    def action_cancel(self):
        if any(p.state in ('partial', 'dispensed') for p in self):
            raise UserError(self.env._("A prescription that was already dispensed cannot be cancelled."))
        self.write({'state': 'cancel'})

    def _update_dispense_state(self):
        for prescription in self:
            lines = prescription.line_ids
            if all(line.quantity_dispensed >= line.quantity for line in lines):
                prescription.state = 'dispensed'
            elif any(line.quantity_dispensed for line in lines):
                prescription.state = 'partial'

    def _history_date(self):
        return self.date

    def _history_title(self):
        meds = ', '.join(self.line_ids.medication_id.mapped('name'))
        return ' - '.join(filter(None, [self.name, meds]))


class MedicalPrescriptionLine(models.Model):
    _name = 'medical.prescription.line'
    _description = 'Prescription Line'
    _order = 'id'

    prescription_id = fields.Many2one('medical.prescription', required=True, ondelete='cascade', index=True)
    medication_id = fields.Many2one('medical.medication', required=True)
    dosage = fields.Char(help="e.g. 1 tablet twice a day for 5 days")
    quantity = fields.Float(default=1.0, required=True)
    quantity_dispensed = fields.Float(compute='_compute_quantity_dispensed', store=True)
    note = fields.Char()

    @api.depends('prescription_id.dispense_ids.line_ids.quantity', 'prescription_id.dispense_ids.state')
    def _compute_quantity_dispensed(self):
        for line in self:
            done = line.prescription_id.sudo().dispense_ids.filtered(lambda d: d.state == 'done')
            line.quantity_dispensed = sum(
                d_line.quantity for d_line in done.line_ids if d_line.prescription_line_id == line)
