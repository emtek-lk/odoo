from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMedicalAccess(TransactionCase):
    """Builds its own institutions and people, so it does not need demo data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.hospital_a = Company.create({'name': 'Hospital A', 'medical_type': 'hospital'})
        cls.hospital_b = Company.create({'name': 'Hospital B', 'medical_type': 'hospital'})
        group_pract = cls.env.ref('medical_base.group_medical_practitioner')
        group_patient = cls.env.ref('medical_base.group_medical_patient')
        base_user = cls.env.ref('base.group_user')

        def make_doctor(name, company):
            user = cls.env['res.users'].create({
                'name': name, 'login': name.lower().replace(' ', '_').replace('.', ''),
                'company_id': company.id, 'company_ids': [(6, 0, company.ids)],
                'group_ids': [(6, 0, [base_user.id, group_pract.id])],
            })
            return user, cls.env['medical.practitioner'].create({
                'name': name, 'user_id': user.id, 'institution_ids': [(6, 0, company.ids)]})

        cls.user_a, cls.doctor_a = make_doctor('Doctor A', cls.hospital_a)
        cls.user_b, cls.doctor_b = make_doctor('Doctor B', cls.hospital_b)
        cls.patient = cls.env['medical.patient'].with_company(cls.hospital_a).create({
            'name': 'Pat Ient', 'national_id': 'NID-1'})
        # the patient's login shares the patient's contact
        cls.patient_user = cls.env['res.users'].create({
            'name': 'Pat Ient', 'login': 'pat_ient', 'partner_id': cls.patient.partner_id.id,
            'company_id': cls.hospital_a.id, 'company_ids': [(6, 0, cls.hospital_a.ids)],
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id, group_patient.id])],
        })
        cls.other_patient = cls.env['medical.patient'].with_company(cls.hospital_b).create({
            'name': 'Other Person', 'national_id': 'NID-2'})
        cls.encounter = cls._encounter(cls.doctor_a, cls.hospital_a, cls.patient, finish=True)

    @classmethod
    def _encounter(cls, doctor, company, patient, finish=False):
        enc = cls.env['medical.encounter'].with_user(doctor.user_id).with_company(company).create({
            'patient_id': patient.id, 'practitioner_id': doctor.id, 'complaint': 'Fever'})
        if finish:
            enc.action_done()
        return enc

    def _consent(self, **vals):
        values = {'patient_id': self.patient.id, 'scope': 'all', 'practitioner_id': self.doctor_b.id}
        values.update(vals)
        return self.env['medical.consent'].create(values)

    def test_patient_code_generated(self):
        self.assertTrue(self.patient.patient_code.startswith('MP'))

    def test_unique_national_id(self):
        with self.assertRaises(Exception), self.cr.savepoint():
            self.env['medical.patient'].create({'name': 'Dup', 'national_id': 'NID-1'})

    def test_other_institution_blocked_without_consent(self):
        with self.assertRaises(AccessError):
            self.encounter.with_user(self.user_b).with_company(self.hospital_b).read(['name'])
        self.assertFalse(self.env['medical.patient'].with_user(self.user_b).search([('id', '=', self.patient.id)]))

    def test_consent_grants_read(self):
        self._consent()
        enc = self.encounter.with_user(self.user_b).with_company(self.hospital_b)
        self.assertTrue(enc.search([('id', '=', self.encounter.id)]))
        self.assertTrue(self.env['medical.patient'].with_user(self.user_b).search([('id', '=', self.patient.id)]))

    def test_consent_scope_limits_access(self):
        self._consent(scope='lab')
        found = self.env['medical.encounter'].with_user(self.user_b).search([('id', '=', self.encounter.id)])
        self.assertFalse(found)

    def test_institution_consent(self):
        self._consent(practitioner_id=False, grantee_company_id=self.hospital_b.id, scope='encounter')
        found = self.env['medical.encounter'].with_user(self.user_b).search([('id', '=', self.encounter.id)])
        self.assertTrue(found)

    def test_revoked_consent_blocks(self):
        consent = self._consent()
        consent.action_revoke()
        found = self.env['medical.encounter'].with_user(self.user_b).search([('id', '=', self.encounter.id)])
        self.assertFalse(found)

    def test_expired_consent_blocks_and_cron_expires(self):
        today = fields.Date.context_today(self.env['medical.consent'])
        consent = self._consent(date_from=today - timedelta(days=10), date_to=today - timedelta(days=1))
        found = self.env['medical.encounter'].with_user(self.user_b).search([('id', '=', self.encounter.id)])
        self.assertFalse(found)
        self.env['medical.consent']._cron_expire_consents()
        self.assertEqual(consent.state, 'expired')

    def test_draft_encounter_not_shared(self):
        draft = self._encounter(self.doctor_a, self.hospital_a, self.patient)
        self._consent()
        found = self.env['medical.encounter'].with_user(self.user_b).search([('id', '=', draft.id)])
        self.assertFalse(found)

    def test_consent_never_grants_write(self):
        self._consent()
        self.assertTrue(self.encounter.with_user(self.user_b).has_access('read'))
        self.assertFalse(self.encounter.with_user(self.user_b).has_access('write'))
        addendum = self.env['medical.encounter.addendum'].with_user(self.user_b)
        with self.assertRaises(AccessError):
            addendum.create({'encounter_id': self.encounter.id, 'note': 'not mine'})

    def test_patient_sees_only_own_data(self):
        enc = self.env['medical.encounter'].with_user(self.patient_user).search([])
        self.assertEqual(enc, self.encounter)
        other = self.env['medical.patient'].with_user(self.patient_user).search([])
        self.assertEqual(other, self.patient)

    def test_cross_institution_read_is_logged(self):
        self._consent()
        enc = self.encounter.with_user(self.user_b).with_company(self.hospital_b)
        enc.web_read({'name': {}})
        log = self.env['medical.access.log'].search([('res_id', '=', self.encounter.id)])
        self.assertEqual(log.user_id, self.user_b)
        self.assertEqual(log.owner_company_id, self.hospital_a)
        # own institution reads are not logged
        count = self.env['medical.access.log'].search_count([])
        self.encounter.with_user(self.user_a).with_company(self.hospital_a).web_read({'name': {}})
        self.assertEqual(self.env['medical.access.log'].search_count([]), count)

    def test_done_encounter_locked_but_addendum_allowed(self):
        with self.assertRaises(UserError):
            self.encounter.write({'diagnosis': 'changed'})
        self.env['medical.encounter.addendum'].with_user(self.user_a).create({
            'encounter_id': self.encounter.id, 'note': 'Late result received'})
        self.assertEqual(len(self.encounter.addendum_ids), 1)

    def test_encounter_cannot_be_deleted(self):
        with self.assertRaises(UserError):
            self.encounter.unlink()

    def test_in_person_consent_needs_evidence(self):
        with self.assertRaises(ValidationError):
            self._consent(method='in_person')

    def test_consent_needs_exactly_one_grantee(self):
        with self.assertRaises(ValidationError):
            self._consent(grantee_company_id=self.hospital_b.id)

    def test_history_respects_consent(self):
        self._consent()
        patient = self.env['medical.patient'].with_user(self.user_b).browse(self.patient.id)
        history = patient.get_history()
        self.assertEqual([h['res_id'] for h in history], [self.encounter.id])

    def test_lookup_returns_minimal_data(self):
        result = self.env['medical.patient'].with_user(self.user_b).lookup_minimal('NID-1')
        self.assertEqual(set(result), {'id', 'name', 'patient_code'})
