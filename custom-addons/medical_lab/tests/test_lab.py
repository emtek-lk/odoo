from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLab(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.hospital = Company.create({'name': 'Hospital', 'medical_type': 'hospital'})
        cls.lab = Company.create({'name': 'Lab', 'medical_type': 'lab'})
        cls.other_lab = Company.create({'name': 'Other Lab', 'medical_type': 'lab'})
        base = cls.env.ref('base.group_user')

        def user(name, company, group):
            return cls.env['res.users'].create({
                'name': name, 'login': name.lower().replace(' ', '_'), 'company_id': company.id,
                'company_ids': [(6, 0, company.ids)],
                'group_ids': [(6, 0, [base.id, cls.env.ref(group).id])]})

        cls.doctor_user = user('Lab Doctor', cls.hospital, 'medical_base.group_medical_practitioner')
        cls.doctor = cls.env['medical.practitioner'].create({
            'name': 'Lab Doctor', 'user_id': cls.doctor_user.id, 'institution_ids': [(6, 0, cls.hospital.ids)]})
        cls.tech = user('Lab Tech', cls.lab, 'medical_lab.group_medical_lab_tech')
        cls.other_tech = user('Other Tech', cls.other_lab, 'medical_lab.group_medical_lab_tech')
        cls.patient = cls.env['medical.patient'].with_company(cls.hospital).create({'name': 'Lab Patient'})
        cls.test = cls.env['medical.lab.test'].create({
            'name': 'Hemoglobin', 'unit': 'g/dL', 'ref_min': 12.0, 'ref_max': 16.0})
        cls.order = cls.env['medical.lab.order'].with_user(cls.doctor_user).with_company(cls.hospital).create({
            'patient_id': cls.patient.id, 'practitioner_id': cls.doctor.id, 'lab_company_id': cls.lab.id,
            'line_ids': [(0, 0, {'test_id': cls.test.id})]})

    def test_lab_only_sees_ordered_orders_sent_to_it(self):
        Order = self.env['medical.lab.order']
        self.assertFalse(Order.with_user(self.tech).search([('id', '=', self.order.id)]), "draft is hidden")
        self.order.action_order()
        self.assertTrue(Order.with_user(self.tech).search([('id', '=', self.order.id)]))
        self.assertFalse(Order.with_user(self.other_tech).search([('id', '=', self.order.id)]))

    def test_cannot_order_without_tests(self):
        empty = self.env['medical.lab.order'].create({'patient_id': self.patient.id})
        with self.assertRaises(UserError):
            empty.action_order()

    def test_results_flag_and_release(self):
        self.order.action_order()
        order = self.order.with_user(self.tech)
        with self.assertRaises(UserError):
            order.action_done()  # no result entered yet
        order.line_ids.write({'value': '9.5', 'numeric_value': 9.5})
        self.assertEqual(order.line_ids.flag, 'low')
        order.line_ids.write({'numeric_value': 14.0})
        self.assertEqual(order.line_ids.flag, 'normal')
        order.action_done()
        self.assertEqual(self.order.state, 'done')

    def test_released_results_are_locked_for_lab(self):
        self.order.action_order()
        order = self.order.with_user(self.tech)
        order.line_ids.write({'value': '13', 'numeric_value': 13.0})
        order.action_done()
        self.assertFalse(order.line_ids.has_access('write'))

    def test_consent_shares_released_results_only(self):
        self.order.action_order()
        base = self.env.ref('base.group_user')
        other_company = self.env['res.company'].create({'name': 'Clinic', 'medical_type': 'clinic'})
        other_user = self.env['res.users'].create({
            'name': 'Clinic Doctor', 'login': 'clinic_doctor', 'company_id': other_company.id,
            'company_ids': [(6, 0, other_company.ids)],
            'group_ids': [(6, 0, [base.id, self.env.ref('medical_base.group_medical_practitioner').id])]})
        self.env['medical.practitioner'].create({'name': 'Clinic Doctor', 'user_id': other_user.id})
        self.env['medical.consent'].create({
            'patient_id': self.patient.id, 'grantee_company_id': other_company.id, 'scope': 'lab'})
        Order = self.env['medical.lab.order'].with_user(other_user)
        self.assertFalse(Order.search([('id', '=', self.order.id)]), "ordered but not released")
        tech_order = self.order.with_user(self.tech)
        tech_order.line_ids.write({'value': '13', 'numeric_value': 13.0})
        tech_order.action_done()
        self.assertTrue(Order.search([('id', '=', self.order.id)]))

    def test_history_includes_lab_order(self):
        self.assertEqual([h['res_model'] for h in self.patient.get_history()], ['medical.lab.order'])
