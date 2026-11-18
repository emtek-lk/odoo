from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProcess(TransactionCase):

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

        cls.farm = party('P Farm', 'farmer')
        cls.factory = party('P Factory', 'processor')
        cls.shop = party('P Shop', 'retailer')
        cls.farm_user = user_for(cls.farm, 'p_farm')
        cls.factory_user = user_for(cls.factory, 'p_factory')
        cls.shop_user = user_for(cls.shop, 'p_shop')
        P = cls.env['trace.product']
        cls.tomato = P.create({'name': 'Proc Tomato', 'category': 'crop', 'unit': 'kg'})
        cls.sauce = P.create({'name': 'Proc Sauce', 'category': 'processed', 'unit': 'kg'})
        cls.tomato_batch = cls.env['trace.batch'].with_user(cls.farm_user).create({
            'product_id': cls.tomato.id, 'initial_quantity': 100})
        cls.tomato_batch._set_holder(cls.factory)  # the factory bought the tomatoes

    def _process(self, user, process_type='process', inputs=(), outputs=()):
        return self.env['trace.process'].with_user(user).create({
            'process_type': process_type,
            'input_ids': [(0, 0, {'batch_id': b.id, 'quantity': q}) for b, q in inputs],
            'output_ids': [(0, 0, {'product_id': p.id, 'quantity': q}) for p, q in outputs]})

    def test_processing_builds_lineage_and_balances_quantities(self):
        run = self._process(self.factory_user, inputs=[(self.tomato_batch, 60)], outputs=[(self.sauce, 25)])
        run.action_confirm()
        self.assertEqual(run.state, 'done')
        sauce_batch = run.output_ids.batch_id
        self.assertEqual(sauce_batch.parent_ids, self.tomato_batch)
        self.assertEqual(sauce_batch.holder_id, self.factory)
        self.assertEqual(sauce_batch.event_ids.event_type, 'produced')
        self.assertEqual(sauce_batch.quantity_remaining, 25)
        self.assertEqual(self.tomato_batch.quantity_remaining, 40)
        self.assertEqual(self.tomato_batch.event_ids.sorted('sequence')[-1].event_type, 'consumed')
        self.assertTrue(self.tomato_batch.verify_chain()[0] and sauce_batch.verify_chain()[0])

    def test_downstream_party_sees_origin_through_the_new_batch(self):
        run = self._process(self.factory_user, inputs=[(self.tomato_batch, 100)], outputs=[(self.sauce, 50)])
        run.action_confirm()
        sauce_batch = run.output_ids.batch_id
        self.assertEqual(self.tomato_batch.state, 'consumed')
        sauce_batch._set_holder(self.shop)
        journey = sauce_batch.with_user(self.shop_user).journey_event_ids
        self.assertEqual(set(journey.batch_id.ids), {self.tomato_batch.id, sauce_batch.id})
        self.assertTrue(self.env['trace.batch'].with_user(self.farm_user).search([('id', '=', sauce_batch.id)]),
                        "the farm can follow its harvest forward")

    def test_only_processors_can_produce(self):
        self.tomato_batch._set_holder(self.shop)
        run = self._process(self.shop_user, inputs=[(self.tomato_batch, 10)], outputs=[(self.sauce, 5)])
        with self.assertRaises(ValidationError):
            run.action_confirm()

    def test_inputs_must_be_held_and_available(self):
        other = self.env['trace.batch'].with_user(self.farm_user).create({'product_id': self.tomato.id, 'initial_quantity': 5})
        run = self._process(self.factory_user, inputs=[(other, 5)], outputs=[(self.sauce, 2)])
        with self.assertRaises((UserError, AccessError)):
            run.action_confirm()
        too_much = self._process(self.factory_user, inputs=[(self.tomato_batch, 500)], outputs=[(self.sauce, 2)])
        with self.assertRaises(UserError):
            too_much.action_confirm()

    def test_only_the_party_can_confirm(self):
        run = self._process(self.factory_user, inputs=[(self.tomato_batch, 10)], outputs=[(self.sauce, 5)])
        with self.assertRaises((UserError, AccessError)):
            run.with_user(self.shop_user).action_confirm()

    def test_split_keeps_product_and_balances(self):
        run = self._process(self.factory_user, 'split', inputs=[(self.tomato_batch, 100)],
                            outputs=[(self.tomato, 30), (self.tomato, 70)])
        run.action_confirm()
        children = run.output_ids.batch_id
        self.assertEqual(len(children), 2)
        self.assertEqual(sorted(children.mapped('quantity_remaining')), [30, 70])
        self.assertEqual(set(children.mapped('parent_ids').ids), {self.tomato_batch.id})
        self.assertEqual(children[0].event_ids.event_type, 'split')

    def test_split_must_balance_and_keep_product(self):
        unbalanced = self._process(self.factory_user, 'split', inputs=[(self.tomato_batch, 100)],
                                   outputs=[(self.tomato, 30), (self.tomato, 60)])
        with self.assertRaises(ValidationError):
            unbalanced.action_confirm()
        other_product = self._process(self.factory_user, 'split', inputs=[(self.tomato_batch, 100)],
                                      outputs=[(self.sauce, 100)])
        with self.assertRaises(ValidationError):
            other_product.action_confirm()

    def test_merge_combines_batches(self):
        second = self.env['trace.batch'].with_user(self.farm_user).create({'product_id': self.tomato.id, 'initial_quantity': 50})
        second._set_holder(self.factory)
        run = self._process(self.factory_user, 'merge', inputs=[(self.tomato_batch, 100), (second, 50)],
                            outputs=[(self.tomato, 150)])
        run.action_confirm()
        merged = run.output_ids.batch_id
        self.assertEqual(merged.parent_ids, self.tomato_batch | second)
        self.assertEqual(merged.quantity_remaining, 150)
        self.assertEqual(merged.event_ids.event_type, 'merged')
        self.assertEqual(merged.get_upstream(), self.tomato_batch | second)

    def test_merge_needs_two_inputs(self):
        run = self._process(self.factory_user, 'merge', inputs=[(self.tomato_batch, 100)], outputs=[(self.tomato, 100)])
        with self.assertRaises(ValidationError):
            run.action_confirm()

    def test_recall_follows_processing(self):
        run = self._process(self.factory_user, inputs=[(self.tomato_batch, 100)], outputs=[(self.sauce, 50)])
        run.action_confirm()
        self.tomato_batch.with_user(self.farm_user).action_recall()
        self.assertEqual(run.output_ids.batch_id.state, 'recalled')

    def test_finished_run_is_locked(self):
        run = self._process(self.factory_user, inputs=[(self.tomato_batch, 10)], outputs=[(self.sauce, 5)])
        run.action_confirm()
        with self.assertRaises(UserError):
            run.with_user(self.factory_user).write({'notes': 'changed'})
        with self.assertRaises(UserError):
            run.with_user(self.factory_user).unlink()
        with self.assertRaises(UserError):
            run.with_user(self.factory_user).action_confirm()
