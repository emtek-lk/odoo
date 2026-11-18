from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTrace(TransactionCase):
    """Builds its own parties and users, so it does not need demo data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        role = lambda code: cls.env.ref('trace_base.role_%s' % code)  # noqa: E731
        Partner = cls.env['res.partner']

        def party(name, role_code):
            return Partner.create({'name': name, 'is_company': True, 'trace_role_ids': [(6, 0, role(role_code).ids)]})

        group_user = cls.env.ref('base.group_user')
        group_trace = cls.env.ref('trace_base.group_trace_user')

        def user_for(party_record, login):
            contact = Partner.create({'name': login, 'parent_id': party_record.id})
            return cls.env['res.users'].create({
                'name': login, 'login': login, 'partner_id': contact.id,
                'group_ids': [(6, 0, [group_user.id, group_trace.id])]})

        cls.farm = party('Green Farm', 'farmer')
        cls.processor = party('Fresh Foods', 'processor')
        cls.trucker = party('Fast Trucks', 'transporter')
        cls.shop = party('Corner Shop', 'retailer')
        cls.farm_user = user_for(cls.farm, 'farm_user')
        cls.processor_user = user_for(cls.processor, 'processor_user')
        cls.trucker_user = user_for(cls.trucker, 'trucker_user')
        cls.shop_user = user_for(cls.shop, 'shop_user')
        cls.tomato = cls.env['trace.product'].create({'name': 'Test Tomato', 'category': 'crop', 'unit': 'kg'})
        cls.sauce = cls.env['trace.product'].create({'name': 'Test Sauce', 'category': 'processed', 'unit': 'kg'})
        cls.batch = cls._batch(cls.farm_user, cls.tomato, 100)

    @classmethod
    def _batch(cls, user, product, qty, **extra):
        vals = {'product_id': product.id, 'initial_quantity': qty, 'origin_place': 'North plot'}
        vals.update(extra)
        return cls.env['trace.batch'].with_user(user).create(vals)

    def _add(self, batch, user, event_type='stored', **vals):
        values = {'batch_id': batch.id, 'event_type': event_type, 'notes': 'ok'}
        values.update(vals)
        return self.env['trace.event'].with_user(user).create(values)

    # ---------------------------------------------------------------- batch and events
    def test_batch_starts_with_origin_event(self):
        events = self.batch.event_ids
        self.assertEqual(len(events), 1)
        self.assertEqual(events.event_type, 'harvested')
        self.assertEqual(events.party_id, self.farm)
        self.assertEqual(events.sequence, 1)
        self.assertEqual(self.batch.holder_id, self.farm)
        self.assertEqual(self.batch.origin_party_id, self.farm)
        self.assertEqual(self.batch.quantity_remaining, 100)
        self.assertTrue(self.batch.name.startswith('TB-'))

    def test_sequence_is_contiguous_and_chained(self):
        self._add(self.batch, self.farm_user, 'inspected')
        self._add(self.batch, self.farm_user, 'packed')
        events = self.batch.event_ids.sorted('sequence')
        self.assertEqual(events.mapped('sequence'), [1, 2, 3])
        self.assertEqual(events[1].previous_hash, events[0].hash)
        self.assertEqual(events[2].previous_hash, events[1].hash)

    def test_events_are_append_only(self):
        event = self.batch.event_ids
        with self.assertRaises(UserError):
            event.write({'notes': 'tampered'})
        with self.assertRaises(UserError):
            event.sudo().unlink()

    def test_system_events_cannot_be_typed_in(self):
        with self.assertRaises(UserError):
            self._add(self.batch, self.farm_user, 'harvested')

    def test_role_rule_for_origin_events(self):
        with self.assertRaises(ValidationError):
            self.env['trace.event'].sudo().with_context(trace_system_event=True).create({
                'batch_id': self.batch.id, 'event_type': 'harvested', 'party_id': self.trucker.id})

    def test_quantity_cannot_go_negative(self):
        with self.assertRaises(ValidationError):
            self._add(self.batch, self.farm_user, 'loss', quantity_delta=-101)
        self._add(self.batch, self.farm_user, 'loss', quantity_delta=-10)
        self.assertEqual(self.batch.quantity_remaining, 90)

    def test_correction_needs_target(self):
        with self.assertRaises(ValidationError):
            self._add(self.batch, self.farm_user, 'correction')
        self._add(self.batch, self.farm_user, 'correction', corrects_event_id=self.batch.event_ids.id)

    def test_batch_cannot_be_deleted_or_rewritten(self):
        with self.assertRaises(UserError):
            self.batch.sudo().unlink()
        with self.assertRaises(UserError):
            self.batch.with_user(self.farm_user).write({'holder_id': self.processor.id})
        with self.assertRaises(UserError):
            self.batch.with_user(self.farm_user).write({'initial_quantity': 5})

    # ---------------------------------------------------------------- hash chain
    def test_chain_verifies_and_detects_tampering(self):
        self._add(self.batch, self.farm_user, 'inspected')
        self._add(self.batch, self.farm_user, 'packed')
        self.assertEqual(self.batch.verify_chain()[0], True)
        second = self.batch.event_ids.sorted('sequence')[1]
        self.env.cr.execute("UPDATE trace_event SET notes = 'edited later' WHERE id = %s", [second.id])
        ok, bad = self.batch.verify_chain()
        self.assertFalse(ok)
        self.assertEqual(bad, second)

    def test_chain_detects_removed_event(self):
        self._add(self.batch, self.farm_user, 'inspected')
        self._add(self.batch, self.farm_user, 'packed')
        middle = self.batch.event_ids.sorted('sequence')[1]
        self.env.cr.execute("DELETE FROM trace_event WHERE id = %s", [middle.id])
        self.assertFalse(self.batch.verify_chain()[0])

    def test_cron_flags_altered_history(self):
        self.env.cr.execute("UPDATE trace_event SET notes = 'edited' WHERE batch_id = %s", [self.batch.id])
        self.env['trace.batch']._cron_verify_chains()
        self.assertFalse(self.batch.chain_checked_ok)

    # ---------------------------------------------------------------- access
    def test_only_holder_can_add_events(self):
        self._add(self.batch, self.farm_user, 'inspected')
        with self.assertRaises(AccessError):
            self._add(self.batch, self.trucker_user, 'transported')
        # even after seeing the batch, a party that is not the holder cannot record on it
        self.batch._grant_visibility(self.trucker)
        with self.assertRaises(AccessError):
            self._add(self.batch, self.trucker_user, 'transported')

    def test_party_cannot_record_as_someone_else(self):
        with self.assertRaises(AccessError):
            self._add(self.batch, self.farm_user, 'inspected', party_id=self.processor.id)

    def test_unrelated_party_sees_nothing(self):
        found = self.env['trace.batch'].with_user(self.shop_user).search([('id', '=', self.batch.id)])
        self.assertFalse(found)
        events = self.env['trace.event'].with_user(self.shop_user).search([('batch_id', '=', self.batch.id)])
        self.assertFalse(events)

    def test_new_holder_gets_full_history(self):
        self._add(self.batch, self.farm_user, 'inspected')
        self.batch._set_holder(self.processor)
        batch = self.batch.with_user(self.processor_user)
        self.assertEqual(batch.holder_id, self.processor)
        self.assertEqual(len(batch.event_ids), 2)
        self._add(self.batch, self.processor_user, 'stored')  # the new holder can now record events
        with self.assertRaises(AccessError):
            self._add(self.batch, self.farm_user, 'stored')  # the previous holder cannot any more

    def test_downstream_sees_upstream_and_origin_sees_downstream(self):
        self.batch._set_holder(self.processor)
        child = self._batch(self.processor_user, self.sauce, 40, origin_party_id=self.processor.id,
                            parent_ids=[(6, 0, self.batch.ids)])
        # the processor holds both; the farm (origin of the parent) can follow the child
        self.assertIn(self.farm, child.visible_party_ids)
        found = self.env['trace.batch'].with_user(self.farm_user).search([('id', '=', child.id)])
        self.assertTrue(found)
        # a shop that later receives only the child sees the parent history too
        child._set_holder(self.shop)
        journey = child.with_user(self.shop_user).journey_event_ids
        self.assertIn(self.batch.event_ids, journey)
        self.assertEqual(set(journey.batch_id.ids), {self.batch.id, child.id})

    def test_lineage_traversal(self):
        child = self._batch(self.farm_user, self.sauce, 40, parent_ids=[(6, 0, self.batch.ids)])
        grandchild = self._batch(self.farm_user, self.sauce, 10, parent_ids=[(6, 0, child.ids)])
        self.assertEqual(grandchild.get_upstream(), self.batch | child)
        self.assertEqual(self.batch.get_downstream(), child | grandchild)
        self.assertEqual(child.get_upstream(include_self=True), self.batch | child)

    # ---------------------------------------------------------------- recall
    def test_recall_reaches_every_descendant(self):
        child = self._batch(self.farm_user, self.sauce, 40, parent_ids=[(6, 0, self.batch.ids)])
        grandchild = self._batch(self.farm_user, self.sauce, 10, parent_ids=[(6, 0, child.ids)])
        self.batch.with_user(self.farm_user).action_recall()
        for batch in (self.batch, child, grandchild):
            self.assertEqual(batch.state, 'recalled')
            self.assertEqual(batch.event_ids.sorted('sequence')[-1].event_type, 'recall')
        self.assertTrue(grandchild.verify_chain()[0])

    def test_only_origin_or_manager_can_recall(self):
        self.batch._set_holder(self.processor)
        with self.assertRaises(UserError):
            self.batch.with_user(self.processor_user).action_recall()
        self.batch.sudo().action_recall()  # superuser is a chain manager
        self.assertEqual(self.batch.state, 'recalled')

    def test_fully_used_batch_changes_state(self):
        self._add(self.batch, self.farm_user, 'sold', quantity_delta=-100)
        self.assertEqual(self.batch.state, 'consumed')
