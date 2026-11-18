import hashlib

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round

GENESIS = '0' * 64

# Events that only the system writes (through batches, transfers and processing), never typed in by hand.
SYSTEM_EVENT_TYPES = {'harvested', 'produced', 'consumed', 'handed_over', 'received', 'split', 'merged', 'recall'}
# Who may record an origin or processing event.
ROLE_RULES = {'harvested': {'farmer', 'harvester'}, 'produced': {'processor'}}


class TraceEvent(models.Model):
    _name = 'trace.event'
    _description = 'Batch Event'
    _order = 'date, id'

    GENESIS = GENESIS

    batch_id = fields.Many2one('trace.batch', required=True, index=True, ondelete='restrict')
    sequence = fields.Integer(readonly=True, index=True)
    date = fields.Datetime(required=True, default=fields.Datetime.now)
    event_type = fields.Selection([
        ('harvested', 'Harvested'), ('produced', 'Produced'), ('inspected', 'Inspected'),
        ('quality_check', 'Quality check'), ('stored', 'Stored'), ('packed', 'Packed'),
        ('transported', 'Transported'), ('handed_over', 'Handed over'), ('received', 'Received'),
        ('consumed', 'Used in processing'), ('split', 'Split'), ('merged', 'Merged'), ('loss', 'Loss or waste'),
        ('sold', 'Sold'), ('recall', 'Recall'), ('correction', 'Correction'), ('note', 'Note')],
        required=True, default='note')
    party_id = fields.Many2one(
        'res.partner', string='Recorded By (party)', required=True, index=True,
        default=lambda self: self.env.user.trace_party_id)
    user_id = fields.Many2one('res.users', string='Recorded By', required=True, default=lambda self: self.env.user)
    location = fields.Char()
    notes = fields.Text()
    quantity_delta = fields.Float(
        string='Quantity Change', digits=(16, 4),
        help="Positive when quantity is added, negative when it leaves the batch (loss, sale, use).")
    temperature = fields.Float(string='Temperature (°C)')
    humidity = fields.Float(string='Humidity (%)')
    attachment_ids = fields.Many2many('ir.attachment', string='Documents')
    corrects_event_id = fields.Many2one('trace.event', string='Corrects', ondelete='restrict')
    is_public = fields.Boolean(
        string='Show on public page', default=True,
        help="Whether the date, type, party and region of this event may appear on the public trace page.")
    previous_hash = fields.Char(readonly=True)
    hash = fields.Char(readonly=True)

    _batch_sequence_uniq = models.Constraint('unique(batch_id, sequence)', 'Event sequence must be unique per batch.')

    # ------------------------------------------------------------------ hashing
    @api.model
    def _hash_payload(self, batch_name, sequence, date, event_type, party_id, user_id, delta, notes,
                      location, is_public, corrects_id, previous_hash):
        return '|'.join([
            batch_name, str(sequence), fields.Datetime.to_string(date), event_type, str(party_id), str(user_id),
            '%.4f' % delta, notes or '', location or '', '1' if is_public else '0', str(corrects_id or 0),
            previous_hash])

    def _compute_hash(self):
        self.ensure_one()
        payload = self._hash_payload(
            self.batch_id.name, self.sequence, self.date, self.event_type, self.party_id.id, self.user_id.id,
            float_round(self.quantity_delta, 4), self.notes, self.location, self.is_public,
            self.corrects_event_id.id, self.previous_hash)
        return hashlib.sha256(payload.encode()).hexdigest()

    # ------------------------------------------------------------------ create / append-only
    @api.model_create_multi
    def create(self, vals_list):
        events = self.browse()
        for vals in vals_list:
            events |= self._create_chained(vals)
        return events

    def _create_chained(self, vals):
        vals = self._add_missing_default_values(dict(vals))
        Batch = self.env['trace.batch'].sudo()
        batch = Batch.browse(vals['batch_id']).exists()
        if not batch:
            raise ValidationError(self.env._("The batch of this event does not exist."))
        event_type = vals['event_type']
        if event_type in SYSTEM_EVENT_TYPES and not (self.env.su or self.env.context.get('trace_system_event')):
            raise UserError(self.env._("'%s' events are recorded automatically and cannot be added by hand.", event_type))
        if event_type == 'correction' and not vals.get('corrects_event_id'):
            raise ValidationError(self.env._("A correction must say which event it corrects."))
        party = self.env['res.partner'].browse(vals['party_id'])
        allowed = ROLE_RULES.get(event_type)
        if allowed and not allowed & set(party.sudo().trace_role_ids.mapped('code')):
            raise ValidationError(self.env._(
                "%(party)s is not allowed to record a '%(type)s' event. It needs one of these roles: %(roles)s.",
                party=party.name, type=event_type, roles=', '.join(sorted(allowed))))

        # Lock the batch so two users cannot extend the chain from the same event at the same time.
        self.env.cr.execute('SELECT id FROM trace_batch WHERE id = %s FOR UPDATE', [batch.id])
        last = self.sudo().search([('batch_id', '=', batch.id)], order='sequence desc', limit=1)
        delta = float_round(vals.get('quantity_delta') or 0.0, 4)
        remaining = sum(self.sudo().search([('batch_id', '=', batch.id)]).mapped('quantity_delta')) + delta
        if remaining < -1e-6:
            raise ValidationError(self.env._("This would take more than the %s remaining in the batch.", remaining - delta))
        date = fields.Datetime.to_datetime(vals['date']).replace(microsecond=0)
        vals.update({
            'date': date,
            'quantity_delta': delta,
            'sequence': (last.sequence or 0) + 1,
            'previous_hash': last.hash or GENESIS,
        })
        vals['hash'] = hashlib.sha256(self._hash_payload(
            batch.name, vals['sequence'], date, event_type, vals['party_id'], vals['user_id'], delta,
            vals.get('notes'), vals.get('location'), vals.get('is_public'), vals.get('corrects_event_id'),
            vals['previous_hash']).encode()).hexdigest()
        event = super().create([vals])
        batch._grant_visibility(party)
        batch._refresh_state()
        return event

    def write(self, vals):
        raise UserError(self.env._("Events cannot be changed. Add a correction event instead."))

    def unlink(self):
        raise UserError(self.env._("Events cannot be deleted. Add a correction event instead."))

    @api.depends('batch_id.name', 'sequence', 'event_type')
    def _compute_display_name(self):
        types = dict(self._fields['event_type'].selection)
        for event in self:
            event.display_name = '%s #%s %s' % (event.batch_id.name or '', event.sequence or '', types.get(event.event_type, ''))
