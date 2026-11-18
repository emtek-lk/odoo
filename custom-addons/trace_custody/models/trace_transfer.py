from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

EPSILON = 1e-6


class TraceTransfer(models.Model):
    _name = 'trace.transfer'
    _description = 'Custody Transfer'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(readonly=True, copy=False, default='New')
    source_batch_id = fields.Many2one(
        'trace.batch', string='Batch', required=True, index=True, readonly=True,
        help="The batch the user selected. For a partial quantity, a child batch is split off and handed over.")
    batch_id = fields.Many2one('trace.batch', string='Handed-over Batch', readonly=True, index=True)
    unit = fields.Selection(related='source_batch_id.unit')
    from_party_id = fields.Many2one(
        'res.partner', string='From', required=True, index=True, readonly=True,
        default=lambda self: self.env.user.trace_party_id)
    to_party_id = fields.Many2one(
        'res.partner', string='To', required=True, index=True, domain=[('is_trace_party', '=', True)], tracking=True)
    quantity = fields.Float(digits=(16, 4), required=True)
    state = fields.Selection(
        [('pending', 'Waiting for acceptance'), ('accepted', 'Accepted'), ('rejected', 'Rejected'),
         ('cancelled', 'Cancelled')], default='pending', required=True, tracking=True, index=True)
    requested_by = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)
    responded_by = fields.Many2one('res.users', readonly=True)
    date_requested = fields.Datetime(default=fields.Datetime.now, readonly=True)
    date_responded = fields.Datetime(readonly=True)
    notes = fields.Text()
    # Private to the two parties: nobody else in the chain sees the deal.
    price = fields.Float(string='Price')
    reference = fields.Char(string='Delivery / Invoice Reference')
    is_sender = fields.Boolean(compute='_compute_roles', search='_search_is_sender', string='I am the sender')
    is_recipient = fields.Boolean(compute='_compute_roles', search='_search_is_recipient', string='I am the recipient')

    @api.depends_context('uid')
    def _compute_roles(self):
        party = self.env.user.trace_party_id
        for transfer in self:
            transfer.is_sender = transfer.from_party_id == party
            transfer.is_recipient = transfer.to_party_id == party

    def _search_party(self, field_name, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise UserError(self.env._("Unsupported search."))
        return [(field_name, '=' if (operator == '=') == value else '!=', self.env.user.trace_party_id.id)]

    def _search_is_sender(self, operator, value):
        return self._search_party('from_party_id', operator, value)

    def _search_is_recipient(self, operator, value):
        return self._search_party('to_party_id', operator, value)

    # ------------------------------------------------------------------ request
    @api.model_create_multi
    def create(self, vals_list):
        transfers = self.browse()
        for vals in vals_list:
            transfers |= self._create_transfer(dict(vals))
        return transfers

    def _create_transfer(self, vals):
        Batch = self.env['trace.batch'].sudo()
        source = Batch.browse(vals.get('source_batch_id')).exists()
        if not source:
            raise ValidationError(self.env._("Choose the batch to hand over."))
        party = self.env.user.trace_party_id
        sender = self.env['res.partner'].browse(vals.get('from_party_id') or party.id)
        if source.holder_id != sender:
            raise UserError(self.env._("Only the party holding %s can hand it over.", source.name))
        if source.state != 'active':
            raise UserError(self.env._("%(batch)s is %(state)s and cannot be handed over.", batch=source.name, state=source.state))
        quantity = vals.get('quantity') or source.quantity_remaining
        if quantity <= 0 or quantity > source.quantity_remaining + EPSILON:
            raise UserError(self.env._("The quantity must be between 0 and the %s remaining.", source.quantity_remaining))
        to_party = self.env['res.partner'].browse(vals['to_party_id'])
        if to_party == sender:
            raise UserError(self.env._("A batch cannot be handed over to the party that already holds it."))
        if self.sudo().search_count([('source_batch_id', '=', source.id), ('state', '=', 'pending')]):
            raise UserError(self.env._("%s already has a transfer waiting for acceptance.", source.name))

        moved = source if abs(quantity - source.quantity_remaining) <= EPSILON else source._split_off(quantity)
        vals.update({
            'name': self.env['ir.sequence'].next_by_code('trace.transfer') or 'New',
            'batch_id': moved.id, 'quantity': quantity, 'from_party_id': sender.id, 'state': 'pending'})
        transfer = super().create([vals])
        moved = moved.sudo()
        # the sender hands over: recorded while the sender still holds the batch
        self._event(moved, 'handed_over', sender, self.env.user,
                    self.env._("Offered %(qty)s to %(to)s (%(ref)s)", qty=quantity, to=to_party.name, ref=transfer.name))
        moved.state = 'in_transit'
        moved._grant_visibility(to_party)  # the recipient can inspect the history before deciding
        return transfer

    @api.model
    def _event(self, batch, event_type, party, user, notes):
        return self.env['trace.event'].sudo().with_context(trace_system_event=True).create({
            'batch_id': batch.id, 'event_type': event_type, 'party_id': party.id, 'user_id': user.id, 'notes': notes})

    # ------------------------------------------------------------------ responses
    def _check_party(self, party, action):
        if self.env.user.trace_party_id != party and not self.env.su:
            raise UserError(self.env._("Only %(party)s can %(action)s this transfer.", party=party.name, action=action))

    def _check_pending(self):
        if any(t.state != 'pending' for t in self):
            raise UserError(self.env._("This transfer is no longer waiting for a response."))

    def action_accept(self):
        self._check_pending()
        for transfer in self:
            transfer._check_party(transfer.to_party_id, self.env._("accept"))
            batch = transfer.batch_id.sudo()
            self._event(batch, 'received', transfer.to_party_id, self.env.user,
                        self.env._("Accepted %(qty)s from %(frm)s (%(ref)s)", qty=transfer.quantity,
                                   frm=transfer.from_party_id.name, ref=transfer.name))
            batch._set_holder(transfer.to_party_id)
            if batch.state == 'in_transit':  # a recall made meanwhile stays a recall
                batch.state = 'active'
            transfer.sudo().write({'state': 'accepted', 'responded_by': self.env.user.id,
                                   'date_responded': fields.Datetime.now()})
        return True

    def action_reject(self):
        self._check_pending()
        for transfer in self:
            transfer._check_party(transfer.to_party_id, self.env._("reject"))
            self._close(transfer, 'rejected', transfer.to_party_id, self.env._("Rejected by %s", transfer.to_party_id.name))
        return True

    def action_cancel(self):
        self._check_pending()
        for transfer in self:
            transfer._check_party(transfer.from_party_id, self.env._("cancel"))
            self._close(transfer, 'cancelled', transfer.from_party_id, self.env._("Cancelled by %s", transfer.from_party_id.name))
        return True

    @api.model
    def _close(self, transfer, state, party, note):
        batch = transfer.batch_id.sudo()
        self._event(batch, 'note', party, self.env.user, '%s (%s)' % (note, transfer.name))
        if batch.state == 'in_transit':
            batch.state = 'active'
        transfer.sudo().write({'state': state, 'responded_by': self.env.user.id, 'date_responded': fields.Datetime.now()})

    def write(self, vals):
        protected = {'source_batch_id', 'batch_id', 'from_party_id', 'to_party_id', 'quantity', 'state', 'name'}
        if protected & set(vals) and not self.env.su:
            raise UserError(self.env._("Use the Accept, Reject or Cancel buttons to change a transfer."))
        return super().write(vals)

    def unlink(self):
        raise UserError(self.env._("Transfers are part of the batch history and cannot be deleted."))
