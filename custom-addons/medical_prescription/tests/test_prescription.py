from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPrescription(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.hospital = Company.create({'name': 'Hospital', 'medical_type': 'hospital'})
        cls.pharmacy = Company.create({'name': 'Pharmacy', 'medical_type': 'pharmacy'})
        cls.other_pharmacy = Company.create({'name': 'Other Pharmacy', 'medical_type': 'pharmacy'})
        base = cls.env.ref('base.group_user')

        def user(name, company, group):
            return cls.env['res.users'].create({
                'name': name, 'login': name.lower().replace(' ', '_'), 'company_id': company.id,
                'company_ids': [(6, 0, company.ids)],
                'group_ids': [(6, 0, [base.id, cls.env.ref(group).id])]})

        cls.doctor_user = user('Rx Doctor', cls.hospital, 'medical_base.group_medical_practitioner')
        cls.doctor = cls.env['medical.practitioner'].create({
            'name': 'Rx Doctor', 'user_id': cls.doctor_user.id, 'institution_ids': [(6, 0, cls.hospital.ids)]})
        cls.pharmacist = user('Rx Pharmacist', cls.pharmacy, 'medical_prescription.group_medical_pharmacist')
        cls.other_pharmacist = user('Other Pharmacist', cls.other_pharmacy, 'medical_prescription.group_medical_pharmacist')
        cls.patient = cls.env['medical.patient'].with_company(cls.hospital).create({'name': 'Rx Patient'})
        cls.med = cls.env['medical.medication'].create({'name': 'Paracetamol', 'strength': '500 mg'})
        cls.rx = cls.env['medical.prescription'].with_user(cls.doctor_user).with_company(cls.hospital).create({
            'patient_id': cls.patient.id, 'practitioner_id': cls.doctor.id,
            'pharmacy_company_id': cls.pharmacy.id,
            'line_ids': [(0, 0, {'medication_id': cls.med.id, 'quantity': 10, 'dosage': '1 tablet 3 times a day'})],
        })

    def _dispense(self, qty, user=None):
        user = user or self.pharmacist
        rx = self.env['medical.prescription'].with_user(user).browse(self.rx.id)
        return self.env['medical.dispense'].with_user(user).create({
            'prescription_id': rx.id,
            'line_ids': [(0, 0, {'prescription_line_id': rx.line_ids.id, 'quantity': qty})]})

    def test_cannot_issue_empty(self):
        empty = self.env['medical.prescription'].create({'patient_id': self.patient.id, 'practitioner_id': self.doctor.id})
        with self.assertRaises(UserError):
            empty.action_issue()

    def test_pharmacy_sees_only_issued_prescriptions_sent_to_it(self):
        found = self.env['medical.prescription'].with_user(self.pharmacist).search([('id', '=', self.rx.id)])
        self.assertFalse(found, "a draft is not visible to the pharmacy")
        self.rx.action_issue()
        found = self.env['medical.prescription'].with_user(self.pharmacist).search([('id', '=', self.rx.id)])
        self.assertTrue(found)
        other = self.env['medical.prescription'].with_user(self.other_pharmacist).search([('id', '=', self.rx.id)])
        self.assertFalse(other)

    def test_partial_then_full_dispensing(self):
        self.rx.action_issue()
        first = self._dispense(4)
        first.action_done()
        self.assertEqual(self.rx.state, 'partial')
        self.assertEqual(self.rx.line_ids.quantity_dispensed, 4)
        second = self._dispense(6)
        second.action_done()
        self.assertEqual(self.rx.state, 'dispensed')

    def test_cannot_over_dispense(self):
        self.rx.action_issue()
        self._dispense(7).action_done()
        with self.assertRaises(ValidationError):
            self._dispense(4)

    def test_draft_cannot_be_dispensed(self):
        with self.assertRaises((AccessError, UserError)):
            self._dispense(1).action_done()

    def test_pharmacy_cannot_edit_prescription(self):
        self.rx.action_issue()
        rx = self.rx.with_user(self.pharmacist)
        self.assertFalse(rx.has_access('write'))

    def test_issued_prescription_locked(self):
        self.rx.action_issue()
        with self.assertRaises(UserError):
            self.rx.write({'line_ids': [(5, 0, 0)]})

    def test_dispensed_cannot_be_cancelled(self):
        self.rx.action_issue()
        self._dispense(10).action_done()
        with self.assertRaises(UserError):
            self.rx.action_cancel()

    def test_history_shows_prescription_and_dispensing(self):
        self.rx.action_issue()
        self._dispense(2).action_done()
        history = self.patient.get_history()
        kinds = {h['res_model'] for h in history}
        self.assertEqual(kinds, {'medical.prescription', 'medical.dispense'})

    def _outsider(self):
        """A doctor at another hospital with no consent."""
        company = self.env['res.company'].create({'name': 'Other Hospital', 'medical_type': 'hospital'})
        return self.env['res.users'].create({
            'name': 'Outsider', 'login': 'rx_outsider', 'company_id': company.id,
            'company_ids': [(6, 0, company.ids)],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                   self.env.ref('medical_base.group_medical_practitioner').id])]})

    def test_child_records_do_not_leak(self):
        self.rx.action_issue()
        self._dispense(4).action_done()
        outsider = self._outsider()
        for model in ('medical.prescription', 'medical.prescription.line', 'medical.dispense', 'medical.dispense.line'):
            self.assertFalse(self.env[model].with_user(outsider).search([]), '%s leaked to an outsider' % model)
        # a pharmacy the prescription was not sent to sees none of it either
        for model in ('medical.prescription', 'medical.prescription.line', 'medical.dispense', 'medical.dispense.line'):
            self.assertFalse(self.env[model].with_user(self.other_pharmacist).search([]), '%s leaked to another pharmacy' % model)
        # the right parties still see them
        for model in ('medical.prescription.line', 'medical.dispense', 'medical.dispense.line'):
            self.assertTrue(self.env[model].with_user(self.pharmacist).search([]), model)
        self.assertTrue(self.env['medical.prescription.line'].with_user(self.doctor_user).search([]))
