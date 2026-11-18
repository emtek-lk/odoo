from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestExtraDemo(TransactionCase):

    def test_volume_and_integrity(self):
        batches = self.env['trace.batch'].search([])
        self.assertGreaterEqual(len(batches), 60)
        self.assertGreaterEqual(self.env['trace.event'].search_count([]), 250)
        for batch in batches:
            self.assertTrue(batch.verify_chain()[0], '%s history does not verify' % batch.name)
            dates = batch.event_ids.sorted('sequence').mapped('date')
            self.assertEqual(dates, sorted(dates), '%s has events out of date order' % batch.name)

    def test_variety(self):
        Batch = self.env['trace.batch']
        self.assertGreaterEqual(len(Batch.search([('state', '=', 'recalled')])), 3)
        self.assertTrue(Batch.search([('state', '=', 'in_transit')]))
        self.assertGreaterEqual(len(self.env['trace.product'].search([])), 14)
        self.assertGreaterEqual(self.env['res.partner'].search_count([('is_trace_party', '=', True)]), 28)

    def test_runs_once(self):
        before = self.env['trace.batch'].search_count([])
        self.env['trace.demo.extra.loader'].load_demo()
        self.assertEqual(self.env['trace.batch'].search_count([]), before)
