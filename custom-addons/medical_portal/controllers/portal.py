from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.http import request


class MedicalPortal(http.Controller):

    def _patient(self):
        return request.env['medical.patient'].search([('user_id', '=', request.env.user.id)], limit=1)

    def _values(self, page_name, **extra):
        values = {'page_name': page_name, 'patient': self._patient()}
        values.update(extra)
        return values

    @http.route('/my/health', type='http', auth='user', website=False)
    def history(self, **kw):
        patient = self._patient()
        history = patient.get_history() if patient else []
        return request.render('medical_portal.portal_history', self._values('health_history', history=history))

    @http.route('/my/health/consents', type='http', auth='user')
    def consents(self, **kw):
        patient = self._patient()
        # sudo: only names are listed so the patient can pick an institution, no records are exposed
        institutions = request.env['res.company'].sudo().search([('medical_type', '!=', False)])
        practitioners = request.env['medical.practitioner'].search([])
        consents = patient.consent_ids if patient else request.env['medical.consent']
        return request.render('medical_portal.portal_consents', self._values(
            'health_consents', consents=consents, institutions=institutions, practitioners=practitioners,
            today=fields.Date.context_today(request.env['medical.consent'])))

    @http.route('/my/health/consents/grant', type='http', auth='user', methods=['POST'])
    def grant(self, grantee='', scope='all', date_to='', **kw):
        patient = self._patient()
        if not patient or ':' not in grantee:
            return request.redirect('/my/health/consents')
        kind, _, record_id = grantee.partition(':')
        values = {'patient_id': patient.id, 'scope': scope, 'method': 'portal', 'date_to': date_to or False}
        if kind == 'practitioner':
            values['practitioner_id'] = int(record_id)
        elif kind == 'company':
            values['grantee_company_id'] = int(record_id)
        else:
            return request.redirect('/my/health/consents')
        try:
            request.env['medical.consent'].create(values)
        except (AccessError, ValueError):
            return request.redirect('/my/health/consents?error=1')
        return request.redirect('/my/health/consents')

    @http.route('/my/health/consents/<int:consent_id>/revoke', type='http', auth='user', methods=['POST'])
    def revoke(self, consent_id, **kw):
        consent = request.env['medical.consent'].browse(consent_id).exists()
        if consent:
            try:
                consent.action_revoke()
            except AccessError:
                pass
        return request.redirect('/my/health/consents')

    @http.route('/my/health/access-log', type='http', auth='user')
    def access_log(self, **kw):
        logs = request.env['medical.access.log'].search([], limit=100)
        return request.render('medical_portal.portal_access_log', self._values('health_access_log', logs=logs))
