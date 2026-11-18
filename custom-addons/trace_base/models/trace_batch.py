import logging
import secrets

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

EPSILON = 1e-6


class TraceBatch(models.Model):
    _name = 'trace.batch'
    _description = 'Batch'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Batch Code', readonly=True, copy=False, default='New', index=True)
    public_token = fields.Char(readonly=True, copy=False, index=True, default=lambda self: secrets.token_urlsafe(9))
    product_id = fields.Many2one('trace.product', required=True, tracking=True)
    unit = fields.Selection(related='product_id.unit')
    origin_party_id = fields.Many2one(
        'res.partner', string='Origin', required=True, index=True, tracking=True,
        default=lambda self: self.env.user.trace_party_id, domain=[('is_trace_party', '=', True)],
        help="The farm, harvester or manufacturer where the batch started.")
    harvester_id = fields.Many2one('res.partner', string='Harvester', domain=[('is_trace_party', '=', True)])
    origin_place = fields.Char(string='Origin Place')
    plot = fields.Char(string='Plot / Field')
    latitude = fields.Float(digits=(10, 6))
    longitude = fields.Float(digits=(10, 6))
    harvest_date = fields.Date(default=fields.Date.context_today)
    initial_quantity = fields.Float(digits=(16, 4))
    quantity_remaining = fields.Float(digits=(16, 4), compute='_compute_quantity_remaining', store=True)
    holder_id = fields.Many2one(
        'res.partner', string='Current Holder', required=True, index=True, tracking=True,
        default=lambda self: self.env.user.trace_party_id, domain=[('is_trace_party', '=', True)])
    is_holder = fields.Boolean(string='Held By My Party', compute='_compute_is_holder', search='_search_is_holder')
    state = fields.Selection(
        [('active', 'Active'), ('in_transit', 'In Transit'), ('consumed', 'Fully Used'), ('recalled', 'Recalled')],
        default='active', required=True, tracking=True, index=True)
    parent_ids = fields.Many2many(
        'trace.batch', 'trace_batch_lineage_rel', 'child_id', 'parent_id', string='Made From', copy=False)
    child_ids = fields.Many2many(
        'trace.batch', 'trace_batch_lineage_rel', 'parent_id', 'child_id', string='Made Into', copy=False)
    event_ids = fields.One2many('trace.event', 'batch_id', string='Events')
    journey_event_ids = fields.Many2many(
        'trace.event', compute='_compute_journey_event_ids', string='Full Journey')
    visible_party_ids = fields.Many2many(
        'res.partner', 'trace_batch_party_rel', 'batch_id', 'partner_id', string='Parties With Access',
        copy=False, readonly=True)
    chain_valid = fields.Boolean(string='History Intact', compute='_compute_chain_valid')
    chain_checked_ok = fields.Boolean(readonly=True, copy=False)
    chain_checked_on = fields.Datetime(readonly=True, copy=False)
    notes = fields.Text()

    _token_uniq = models.Constraint('unique(public_token)', 'The public token must be unique.')

    # ------------------------------------------------------------------ computes
    @api.depends('event_ids.quantity_delta')
    def _compute_quantity_remaining(self):
        for batch in self:
            batch.quantity_remaining = sum(batch.sudo().event_ids.mapped('quantity_delta'))

    @api.depends_context('uid')
    def _compute_is_holder(self):
        party = self.env.user.trace_party_id
        for batch in self:
            batch.is_holder = batch.holder_id == party

    def _search_is_holder(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise UserError(self.env._("Unsupported search on 'Held by my party'."))
        mine = (operator == '=') == value
        return [('holder_id', '=' if mine else '!=', self.env.user.trace_party_id.id)]

    def _compute_journey_event_ids(self):
        for batch in self:
            batches = batch.get_upstream(include_self=True)
            batch.journey_event_ids = self.env['trace.event'].search([('batch_id', 'in', batches.ids)])

    def _compute_chain_valid(self):
        for batch in self:
            batch.chain_valid = batch.verify_chain()[0] if batch.id else True

    # ------------------------------------------------------------------ lineage
    def _walk(self, field_name):
        """Ids of every batch reachable through ``field_name`` ('parent_ids' or 'child_ids'), cycle-safe."""
        seen = set()
        frontier = self.sudo()
        while frontier:
            nxt = frontier[field_name].filtered(lambda b: b.id not in seen and b not in self)
            seen.update(nxt.ids)
            frontier = nxt
        return seen

    def get_upstream(self, include_self=False):
        """Batches this one was made from, all the way back to the origin."""
        ids = self._walk('parent_ids') | (set(self.ids) if include_self else set())
        return self.browse(sorted(ids))

    def get_downstream(self, include_self=False):
        """Batches made from this one, all the way forward."""
        ids = self._walk('child_ids') | (set(self.ids) if include_self else set())
        return self.browse(sorted(ids))

    def _grant_visibility(self, parties):
        """Give ``parties`` read access to these batches and to everything they were made from."""
        parties = parties.filtered(lambda p: p)
        if not parties:
            return
        targets = self.sudo().get_upstream(include_self=True)
        targets.sudo().write({'visible_party_ids': [(4, party.id) for party in parties]})

    def _propagate_lineage_visibility(self):
        """After a batch gets parents: parties on it reach the ancestors, ancestor origins reach it."""
        for batch in self.sudo():
            ancestors = batch.get_upstream()
            if not ancestors:
                continue
            batch.get_upstream().write({'visible_party_ids': [(4, p.id) for p in batch.visible_party_ids]})
            batch.write({'visible_party_ids': [(4, p.id) for p in ancestors.origin_party_id]})

    # ------------------------------------------------------------------ lifecycle
    def _origin_event_type(self, party):
        codes = set(party.sudo().trace_role_ids.mapped('code'))
        if codes & {'farmer', 'harvester'}:
            return 'harvested'
        return 'produced'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('trace.batch') or 'New'
            holder = vals.get('holder_id') or self.env.user.trace_party_id.id
            origin = vals.get('origin_party_id') or self.env.user.trace_party_id.id
            parties = {holder, origin, vals.get('harvester_id')} - {False, None}
            vals['visible_party_ids'] = [(4, pid) for pid in parties]
        batches = super().create(vals_list)
        for batch in batches:
            self.env['trace.event'].with_context(trace_system_event=True).create({
                'batch_id': batch.id,
                'event_type': self.env.context.get('trace_origin_event_type') or self._origin_event_type(batch.holder_id),
                'party_id': batch.holder_id.id,
                'location': batch.origin_place,
                'quantity_delta': batch.initial_quantity,
                'notes': batch.notes,
            })
        batches._propagate_lineage_visibility()
        return batches

    def write(self, vals):
        locked = {'origin_party_id', 'product_id', 'initial_quantity', 'public_token', 'name', 'parent_ids', 'holder_id'}
        if locked & set(vals) and not self.env.su:
            raise UserError(self.env._(
                "Origin, product, quantity, code, lineage and custody cannot be edited. "
                "Record a correction event or a transfer instead."))
        return super().write(vals)

    def unlink(self):
        raise UserError(self.env._("Batches cannot be deleted because their history must be kept. Recall or archive instead."))

    def _refresh_state(self):
        for batch in self.sudo():
            if batch.state == 'active' and batch.quantity_remaining <= EPSILON:
                batch.state = 'consumed'
            elif batch.state == 'consumed' and batch.quantity_remaining > EPSILON:
                batch.state = 'active'

    def _set_holder(self, party):
        """Change custody (used by transfers). Runs privileged and shares the history with the new holder."""
        for batch in self.sudo():
            batch.holder_id = party
        self._grant_visibility(party)

    # ------------------------------------------------------------------ actions
    def action_add_event(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Add event"),
            'res_model': 'trace.event',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_batch_id': self.id},
        }

    def action_recall(self):
        user = self.env.user
        for batch in self:
            if not (user.has_group('trace_base.group_trace_manager') or batch.origin_party_id == user.trace_party_id):
                raise UserError(self.env._("Only the origin party or a chain manager can recall a batch."))
        targets = (self | self.get_downstream()).sudo()
        reason = self.env.context.get('trace_recall_reason') or self.env._("Recalled by %s", user.trace_party_id.name)
        for target in targets.filtered(lambda b: b.state != 'recalled'):
            self.env['trace.event'].sudo().with_context(trace_system_event=True).create({
                'batch_id': target.id, 'event_type': 'recall', 'notes': reason})
            target.state = 'recalled'
        return True

    def action_verify_chain(self):
        self.ensure_one()
        ok, bad = self.verify_chain()
        if ok:
            message, kind = self.env._("History is intact: every event matches its hash."), 'success'
        else:
            message, kind = self.env._(
                "History was altered: event #%(seq)s no longer matches its hash.", seq=bad.sequence), 'danger'
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': self.env._("Verify history"), 'message': message, 'type': kind, 'sticky': not ok},
        }

    def verify_chain(self):
        """Recompute the hash chain. Returns ``(ok, first_broken_event)``."""
        self.ensure_one()
        Event = self.env['trace.event'].sudo()
        Event.invalidate_model()  # read what is really in the database
        previous_hash, expected = Event.GENESIS, 1
        for event in Event.search([('batch_id', '=', self.id)], order='sequence'):
            if (event.sequence != expected or event.previous_hash != previous_hash
                    or event.hash != event._compute_hash()):
                return False, event
            previous_hash, expected = event.hash, expected + 1
        return True, Event.browse()

    @api.model
    def _cron_verify_chains(self):
        for batch in self.sudo().search([]):
            ok, bad = batch.verify_chain()
            batch.write({'chain_checked_ok': ok, 'chain_checked_on': fields.Datetime.now()})
            if not ok:
                _logger.error("Supply chain history of %s was altered at event #%s", batch.name, bad.sequence)
                batch.message_post(body=self.env._(
                    "Integrity alert: event #%s no longer matches its hash.", bad.sequence))
