from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPublicPage(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        role = lambda code: cls.env.ref('trace_base.role_%s' % code)  # noqa: E731
        groups = [cls.env.ref('base.group_user').id, cls.env.ref('trace_base.group_trace_user').id]
        cls.farm = Partner.create({'name': 'Pub Farm', 'is_company': True, 'trace_region': 'Nuwara Eliya',
                                   'trace_role_ids': [(6, 0, role('farmer').ids)]})
        contact = Partner.create({'name': 'Secret Person', 'parent_id': cls.farm.id})
        cls.farm_user = cls.env['res.users'].create({
            'name': 'Secret Person', 'login': 'secretfarmlogin', 'partner_id': contact.id,
            'group_ids': [(6, 0, groups)]})
        product = cls.env['trace.product'].create({'name': 'Public Tea', 'unit': 'kg'})
        cls.batch = cls.env['trace.batch'].with_user(cls.farm_user).create({
            'product_id': product.id, 'initial_quantity': 12345.5, 'origin_place': 'SECRETPLOT',
            'notes': 'SECRETNOTE origin'})
        Event = cls.env['trace.event'].with_user(cls.farm_user)
        Event.create({'batch_id': cls.batch.id, 'event_type': 'inspected', 'notes': 'SECRETINSPECTION',
                      'location': 'Visible Gate', 'is_public': True})
        Event.create({'batch_id': cls.batch.id, 'event_type': 'stored', 'notes': 'SECRETSTORE',
                      'location': 'HIDDENWAREHOUSE', 'is_public': False})

    def test_page_shows_journey_but_no_private_details(self):
        page = self.url_open('/trace/%s' % self.batch.public_token)
        self.assertEqual(page.status_code, 200)
        text = page.text
        self.assertIn('Public Tea', text)
        self.assertIn('Pub Farm', text)
        self.assertIn('Nuwara Eliya', text)
        self.assertIn('Harvested', text)
        self.assertIn('Inspected', text)
        self.assertIn('History verified', text)
        self.assertNotIn('Stored', text, "events marked non-public are hidden")
        for secret in ('SECRETNOTE', 'SECRETINSPECTION', 'SECRETSTORE', 'HIDDENWAREHOUSE', 'SECRETPLOT',
                       'secretfarmlogin', 'Secret Person', '12345', 'previous_hash'):
            self.assertNotIn(secret, text, '%r leaked on the public page' % secret)
        self.assertNotIn(self.batch.event_ids[0].hash, text)

    def test_unknown_token_is_404(self):
        self.assertEqual(self.url_open('/trace/not-a-real-token').status_code, 404)

    def test_tampered_history_is_flagged(self):
        self.env.cr.execute("UPDATE trace_event SET notes = 'edited later' WHERE batch_id = %s", [self.batch.id])
        text = self.url_open('/trace/%s' % self.batch.public_token).text
        self.assertIn('could not be verified', text)
        self.assertNotIn('History verified', text)

    def test_recall_is_shown(self):
        self.batch.with_user(self.farm_user).action_recall()
        text = self.url_open('/trace/%s' % self.batch.public_token).text
        self.assertIn('has been recalled', text)

    def test_upstream_journey_is_included(self):
        child = self.batch._split_off(100)
        text = self.url_open('/trace/%s' % child.public_token).text
        self.assertIn('Harvested', text, "the origin of the parent appears on the child's page")

    def test_qr_and_url_on_batch(self):
        self.assertIn('/trace/%s' % self.batch.public_token, self.batch.public_url)
        self.assertIn('/report/barcode/QR/', self.batch.qr_code_html)
