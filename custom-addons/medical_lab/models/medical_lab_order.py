from odoo import api, fields, models
from odoo.exceptions import UserError


class MedicalLabOrder(models.Model):
    _name = 'medical.lab.order'
    _description = 'Lab Order'
    _inherit = ['medical.record.mixin', 'mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='New')
    date = fields.Datetime(required=True, default=fields.Datetime.now)
    practitioner_id = fields.Many2one(
        'medical.practitioner', string='Ordered By',
        default=lambda self: self.env['medical.practitioner'].search([('user_id', '=', self.env.uid)], limit=1))
    encounter_id = fields.Many2one(
        'medical.encounter', string='Encounter', domain="[('patient_id', '=', patient_id)]")
    lab_company_id = fields.Many2one(
        'res.company', string='Laboratory', domain=[('medical_type', '=', 'lab')],
        help="The lab that performs the tests. It may read and complete this order.")
    lab_name = fields.Char(related='lab_company_id.name', store=True)
    line_ids = fields.One2many('medical.lab.result', 'order_id', string='Tests')
    notes = fields.Text()
    state = fields.Selection(
        [('draft', 'Draft'), ('ordered', 'Ordered'), ('done', 'Results Ready'), ('cancel', 'Cancelled')],
        default='draft', required=True, tracking=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('medical.lab.order') or 'New'
        return super().create(vals_list)

    def unlink(self):
        raise UserError(self.env._("Clinical records cannot be deleted. Cancel the order instead."))

    def action_order(self):
        for order in self:
            if not order.line_ids:
                raise UserError(self.env._("Add at least one test before ordering."))
        self.write({'state': 'ordered'})

    def action_done(self):
        for order in self:
            if any(line.value in (False, '') for line in order.line_ids):
                raise UserError(self.env._("Enter a result for every test first."))
        self.check_access('write')
        # sudo: once released the order no longer matches the lab's edit rule, so the transition runs privileged
        self.sudo().write({'state': 'done'})

    def action_cancel(self):
        if any(o.state == 'done' for o in self):
            raise UserError(self.env._("An order with released results cannot be cancelled."))
        self.write({'state': 'cancel'})

    def _history_date(self):
        return self.date

    def _history_kind(self):
        return self.env._("Lab")

    def _history_title(self):
        tests = ', '.join(self.line_ids.test_id.mapped('name'))
        return ' - '.join(filter(None, [self.name, tests]))


class MedicalLabResult(models.Model):
    _name = 'medical.lab.result'
    _description = 'Lab Result'
    _order = 'id'

    order_id = fields.Many2one('medical.lab.order', required=True, ondelete='cascade', index=True)
    test_id = fields.Many2one('medical.lab.test', required=True)
    value = fields.Char(string='Result')
    numeric_value = fields.Float(string='Numeric Result')
    unit = fields.Char(related='test_id.unit')
    flag = fields.Selection(
        [('normal', 'Normal'), ('low', 'Low'), ('high', 'High')], compute='_compute_flag', store=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Report Files')

    @api.depends('numeric_value', 'test_id.ref_min', 'test_id.ref_max', 'value')
    def _compute_flag(self):
        for result in self:
            test = result.test_id
            if not result.value or not (test.ref_min or test.ref_max):
                result.flag = False
            elif result.numeric_value < test.ref_min:
                result.flag = 'low'
            elif test.ref_max and result.numeric_value > test.ref_max:
                result.flag = 'high'
            else:
                result.flag = 'normal'
