from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

EPSILON = 1e-6


class TraceProcess(models.Model):
    _name = 'trace.process'
    _description = 'Processing Run'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(readonly=True, copy=False, default='New')
    process_type = fields.Selection(
        [('process', 'Process'), ('split', 'Split'), ('merge', 'Merge')], required=True, default='process')
    description = fields.Char(help="e.g. washed, cooked and packed")
    party_id = fields.Many2one(
        'res.partner', string='Party', required=True, index=True, readonly=True,
        default=lambda self: self.env.user.trace_party_id)
    date = fields.Datetime(default=fields.Datetime.now)
    location = fields.Char()
    notes = fields.Text()
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft', required=True, tracking=True)
    input_ids = fields.One2many('trace.process.input', 'process_id', string='Inputs')
    output_ids = fields.One2many('trace.process.output', 'process_id', string='Outputs')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('trace.process') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if any(p.state == 'done' for p in self) and not self.env.su:
            raise UserError(self.env._("A finished processing run is part of the history and cannot be edited."))
        return super().write(vals)

    def unlink(self):
        if any(p.state == 'done' for p in self):
            raise UserError(self.env._("A finished processing run cannot be deleted."))
        return super().unlink()

    # ------------------------------------------------------------------ rules
    def _validate(self):
        self.ensure_one()
        inputs, outputs = self.input_ids, self.output_ids
        if not inputs or not outputs:
            raise ValidationError(self.env._("Add at least one input batch and one output."))
        if self.party_id != self.env.user.trace_party_id and not self.env.su:
            raise UserError(self.env._("Only %s can confirm this processing run.", self.party_id.name))
        for line in inputs:
            batch = line.batch_id.sudo()
            if batch.holder_id != self.party_id:
                raise UserError(self.env._("%s is not held by %s.", batch.name, self.party_id.name))
            if batch.state != 'active':
                raise UserError(self.env._("%(batch)s is %(state)s and cannot be used.", batch=batch.name, state=batch.state))
            if line.quantity <= 0 or line.quantity > batch.quantity_remaining + EPSILON:
                raise UserError(self.env._("Use between 0 and the %(remaining)s remaining of %(batch)s.",
                                           remaining=batch.quantity_remaining, batch=batch.name))
        if len(set(inputs.batch_id.ids)) != len(inputs):
            raise ValidationError(self.env._("Each input batch can only appear once."))
        if any(out.quantity <= 0 for out in outputs):
            raise ValidationError(self.env._("Output quantities must be positive."))
        if self.process_type in ('split', 'merge'):
            product = inputs[0].batch_id.product_id
            if any(line.batch_id.product_id != product for line in inputs) or any(out.product_id != product for out in outputs):
                raise ValidationError(self.env._("Splits and merges keep the same product."))
            total_in, total_out = sum(inputs.mapped('quantity')), sum(outputs.mapped('quantity'))
            if abs(total_in - total_out) > EPSILON:
                raise ValidationError(self.env._("Quantities must balance: %(inp)s in, %(out)s out.", inp=total_in, out=total_out))
        if self.process_type == 'split' and len(inputs) != 1:
            raise ValidationError(self.env._("A split takes exactly one input batch."))
        if self.process_type == 'merge' and (len(inputs) < 2 or len(outputs) != 1):
            raise ValidationError(self.env._("A merge takes two or more input batches and gives one output."))

    # ------------------------------------------------------------------ confirm
    def action_confirm(self):
        for process in self:
            if process.state != 'draft':
                raise UserError(self.env._("%s is already done.", process.name))
            process._validate()
            process._execute()
        return True

    def _execute(self):
        self.ensure_one()
        Event = self.env['trace.event'].sudo().with_context(trace_system_event=True)
        origin_event = {'process': 'produced', 'split': 'split', 'merge': 'merged'}[self.process_type]
        inputs = self.input_ids.batch_id.sudo()
        for line in self.input_ids:
            Event.create({
                'batch_id': line.batch_id.id, 'event_type': 'consumed', 'party_id': self.party_id.id,
                'quantity_delta': -line.quantity, 'location': self.location,
                'notes': self.env._("Used in %(process)s %(what)s", process=self.name, what=self.description or '')})
        for out in self.output_ids:
            batch = self.env['trace.batch'].sudo().with_context(trace_origin_event_type=origin_event).create({
                'product_id': out.product_id.id,
                'origin_party_id': self.party_id.id,
                'origin_place': self.location,
                'holder_id': self.party_id.id,
                'initial_quantity': out.quantity,
                'parent_ids': [(6, 0, inputs.ids)],
                'notes': self.env._("%(process)s %(what)s from %(inputs)s", process=self.name, what=self.description or '',
                                    inputs=', '.join(inputs.mapped('name'))),
            })
            out.sudo().batch_id = batch
        inputs._refresh_state()
        self.sudo().state = 'done'


class TraceProcessInput(models.Model):
    _name = 'trace.process.input'
    _description = 'Processing Input'

    process_id = fields.Many2one('trace.process', required=True, ondelete='cascade', index=True)
    batch_id = fields.Many2one('trace.batch', required=True, domain="[('is_holder', '=', True), ('state', '=', 'active')]")
    available = fields.Float(related='batch_id.quantity_remaining', digits=(16, 4))
    unit = fields.Selection(related='batch_id.unit')
    quantity = fields.Float(digits=(16, 4), required=True)


class TraceProcessOutput(models.Model):
    _name = 'trace.process.output'
    _description = 'Processing Output'

    process_id = fields.Many2one('trace.process', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('trace.product', required=True)
    unit = fields.Selection(related='product_id.unit')
    quantity = fields.Float(digits=(16, 4), required=True)
    batch_id = fields.Many2one('trace.batch', string='New Batch', readonly=True)
