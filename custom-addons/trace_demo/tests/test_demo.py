from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDemo(TransactionCase):

    def test_journeys_were_loaded_and_histories_verify(self):
        batches = self.env['trace.batch'].search([])
        self.assertGreaterEqual(len(batches), 20)
        for batch in batches:
            self.assertTrue(batch.verify_chain()[0], '%s history does not verify' % batch.name)

    def test_expected_situations_exist(self):
        Batch = self.env['trace.batch']
        self.assertTrue(Batch.search([('state', '=', 'recalled')]), "a recalled lot")
        self.assertTrue(Batch.search([('state', '=', 'in_transit')]), "a batch waiting for acceptance")
        self.assertTrue(Batch.search([('state', '=', 'consumed')]), "a fully used batch")
        self.assertTrue(self.env['trace.transfer'].search([('state', '=', 'pending')]))
        processes = self.env['trace.process'].search([])
        self.assertEqual(set(processes.mapped('process_type')), {'process', 'split', 'merge'})

    def test_events_are_in_date_order(self):
        for batch in self.env['trace.batch'].search([]):
            dates = batch.event_ids.sorted('sequence').mapped('date')
            self.assertEqual(dates, sorted(dates), '%s has events out of date order' % batch.name)

    def test_retailer_sees_origin_through_the_chain(self):
        citymart = self.env.ref('trace_demo.user_citymart')
        batches = self.env['trace.batch'].with_user(citymart).search([('holder_id', '=', citymart.trace_party_id.id)])
        self.assertTrue(batches)
        farms = batches.get_upstream().mapped('origin_party_id')
        self.assertIn(self.env.ref('trace_demo.party_green_valley'), farms)
        journey = batches[0].journey_event_ids
        self.assertIn('harvested', journey.mapped('event_type'))

    def test_demo_runs_only_once(self):
        before = self.env['trace.batch'].search_count([])
        self.env['trace.demo.loader'].load_demo()
        self.assertEqual(self.env['trace.batch'].search_count([]), before)
