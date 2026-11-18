from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestMedicalPortal(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hospital = cls.env['res.company'].create({'name': 'Portal Hospital', 'medical_type': 'hospital'})
        cls.clinic = cls.env['res.company'].create({'name': 'Portal Clinic', 'medical_type': 'clinic'})
        cls.patient = cls.env['medical.patient'].with_company(cls.hospital).create({'name': 'Portal Patient'})
        cls.user = cls.env['res.users'].create({
            'name': 'Portal Patient', 'login': 'portal_patient', 'password': 'portal_patient',
            'partner_id': cls.patient.partner_id.id,
            'company_id': cls.hospital.id, 'company_ids': [(6, 0, cls.hospital.ids)],
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id,
                                   cls.env.ref('medical_base.group_medical_patient').id])]})
        doctor_user = cls.env['res.users'].create({
            'name': 'Portal Doctor', 'login': 'portal_doctor', 'company_id': cls.hospital.id,
            'company_ids': [(6, 0, cls.hospital.ids)],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                   cls.env.ref('medical_base.group_medical_practitioner').id])]})
        doctor = cls.env['medical.practitioner'].create({
            'name': 'Portal Doctor', 'user_id': doctor_user.id, 'institution_ids': [(6, 0, cls.hospital.ids)]})
        cls.encounter = cls.env['medical.encounter'].with_user(doctor_user).with_company(cls.hospital).create({
            'patient_id': cls.patient.id, 'practitioner_id': doctor.id, 'diagnosis': 'Seasonal flu'})
        cls.encounter.action_done()

    def test_patient_sees_history_and_manages_consent(self):
        self.authenticate('portal_patient', 'portal_patient')
        page = self.url_open('/my/health')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Seasonal flu', page.text)

        response = self.url_open('/my/health/consents/grant', data={
            'csrf_token': self.csrf_token(), 'grantee': 'company:%s' % self.clinic.id, 'scope': 'lab'})
        self.assertEqual(response.status_code, 200)
        consent = self.patient.consent_ids
        self.assertEqual(len(consent), 1)
        self.assertEqual(consent.grantee_company_id, self.clinic)
        self.assertEqual(consent.method, 'portal')

        response = self.url_open('/my/health/consents/%s/revoke' % consent.id, data={'csrf_token': self.csrf_token()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(consent.state, 'revoked')

    def test_anonymous_user_is_redirected(self):
        response = self.url_open('/my/health', allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))

