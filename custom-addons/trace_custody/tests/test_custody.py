from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCustody(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        role = lambda code: cls.env.ref('trace_base.role_%s' % code)  # noqa: E731
        groups = [cls.env.ref('base.group_user').id, cls.env.ref('trace_base.group_trace_user').id]

        def party(name, code):
            return Partner.create({'name': name, 'is_company': True, 'trace_role_ids': [(6, 0, role(code).ids)]})

        def user_for(p, login):
            contact = Partner.create({'name': login, 'parent_id': p.id})
            return cls.env['res.users'].create({
                'name': login, 'login': login, 'partner_id': contact.id, 'group_ids': [(6, 0, groups)]})

        cls.farm = party('Farm', 'farmer')
        cls.trucker = party('Trucker', 'transporter')
        cls.processor = party('Processor', 'processor')
        cls.other = party('Bystander', 'retailer')
        cls.farm_user = user_for(cls.farm, 'c_farm')
        cls.trucker_user = user_for(cls.trucker, 'c_trucker')
        cls.processor_user = user_for(cls.processor, 'c_processor')
        cls.other_user = user_for(cls.other, 'c_other')
        cls.product = cls.env['trace.product'].create({'name': 'Custody Rice', 'unit': 'kg'})
        cls.batch = cls.env['trace.batch'].with_user(cls.farm_user).create({
            'product_id': cls.product.id, 'initial_quantity': 100})

    def _offer(self, to, quantity=None, user=None, **extra):
        vals = {'source_batch_id': self.batch.id, 'to_party_id': to.id}
        if quantity:
            vals['quantity'] = quantity
        vals.update(extra)
        return self.env['trace.transfer'].with_user(user or self.farm_user).create(vals)

    def test_offer_marks_batch_in_transit_and_lets_recipient_inspect(self):
        transfer = self._offer(self.trucker)
        self.assertEqual(transfer.state, 'pending')
        self.assertEqual(self.batch.state, 'in_transit')
        self.assertEqual(self.batch.holder_id, self.farm)
        self.assertEqual(self.batch.event_ids.sorted('sequence')[-1].event_type, 'handed_over')
        seen = self.env['trace.batch'].with_user(self.trucker_user).search([('id', '=', self.batch.id)])
        self.assertTrue(seen, "the recipient can read the history before accepting")

    def test_accept_moves_custody(self):
        transfer = self._offer(self.trucker)
        transfer.with_user(self.trucker_user).action_accept()
        self.assertEqual(transfer.state, 'accepted')
        self.assertEqual(self.batch.holder_id, self.trucker)
        self.assertEqual(self.batch.state, 'active')
        self.assertEqual(self.batch.event_ids.sorted('sequence')[-1].event_type, 'received')
        self.assertTrue(self.batch.verify_chain()[0])
        # the new holder can record events, the old one cannot
        self.env['trace.event'].with_user(self.trucker_user).create({
            'batch_id': self.batch.id, 'event_type': 'transported', 'notes': 'on the road'})
        with self.assertRaises(AccessError):
            self.env['trace.event'].with_user(self.farm_user).create({
                'batch_id': self.batch.id, 'event_type': 'note', 'notes': 'still mine?'})

    def test_reject_keeps_custody(self):
        transfer = self._offer(self.trucker)
        transfer.with_user(self.trucker_user).action_reject()
        self.assertEqual(transfer.state, 'rejected')
        self.assertEqual(self.batch.holder_id, self.farm)
        self.assertEqual(self.batch.state, 'active')

    def test_only_recipient_can_accept_and_only_sender_can_cancel(self):
        transfer = self._offer(self.trucker)
        with self.assertRaises(UserError):
            transfer.with_user(self.farm_user).action_accept()
        with self.assertRaises(UserError):
            transfer.with_user(self.trucker_user).action_cancel()
        transfer.with_user(self.farm_user).action_cancel()
        self.assertEqual(transfer.state, 'cancelled')
        self.assertEqual(self.batch.state, 'active')

    def test_cannot_respond_twice(self):
        transfer = self._offer(self.trucker)
        transfer.with_user(self.trucker_user).action_accept()
        with self.assertRaises(UserError):
            transfer.with_user(self.trucker_user).action_accept()

    def test_only_holder_can_offer(self):
        with self.assertRaises((UserError, AccessError)):
            self._offer(self.processor, user=self.trucker_user)
        with self.assertRaises(UserError):
            self._offer(self.farm)  # to itself

    def test_second_offer_while_pending_is_refused(self):
        self._offer(self.trucker)
        with self.assertRaises(UserError):
            self._offer(self.processor)

    def test_partial_quantity_splits_a_child_batch(self):
        transfer = self._offer(self.trucker, quantity=40)
        moved = transfer.batch_id
        self.assertNotEqual(moved, self.batch)
        self.assertEqual(moved.parent_ids, self.batch)
        self.assertEqual(moved.quantity_remaining, 40)
        self.assertEqual(self.batch.quantity_remaining, 60)
        self.assertEqual(moved.state, 'in_transit')
        self.assertEqual(self.batch.state, 'active')
        transfer.with_user(self.trucker_user).action_accept()
        self.assertEqual(moved.holder_id, self.trucker)
        self.assertEqual(self.batch.holder_id, self.farm)
        self.assertTrue(moved.verify_chain()[0] and self.batch.verify_chain()[0])

    def test_quantity_limits(self):
        with self.assertRaises(UserError):
            self._offer(self.trucker, quantity=500)

    def test_price_is_private_to_the_two_parties(self):
        transfer = self._offer(self.trucker, price=1234.0, reference='INV-1')
        Transfer = self.env['trace.transfer']
        self.assertTrue(Transfer.with_user(self.farm_user).search([('id', '=', transfer.id)]))
        self.assertTrue(Transfer.with_user(self.trucker_user).search([('id', '=', transfer.id)]))
        self.assertFalse(Transfer.with_user(self.other_user).search([('id', '=', transfer.id)]))
        self.assertFalse(Transfer.with_user(self.processor_user).search([]))

    def test_recall_during_transit_stays_recalled(self):
        transfer = self._offer(self.trucker)
        self.batch.with_user(self.farm_user).action_recall()
        transfer.with_user(self.trucker_user).action_accept()
        self.assertEqual(self.batch.state, 'recalled')

    def test_chain_of_custody_end_to_end(self):
        self._offer(self.trucker).with_user(self.trucker_user).action_accept()
        self.env['trace.transfer'].with_user(self.trucker_user).create({
            'source_batch_id': self.batch.id, 'to_party_id': self.processor.id}).with_user(self.processor_user).action_accept()
        self.assertEqual(self.batch.holder_id, self.processor)
        journey = self.batch.with_user(self.processor_user).event_ids.sorted('sequence').mapped('event_type')
        self.assertEqual(journey, ['harvested', 'handed_over', 'received', 'handed_over', 'received'])
        self.assertTrue(self.batch.verify_chain()[0])
