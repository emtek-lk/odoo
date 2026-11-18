from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MedicalPatient(models.Model):
    _name = 'medical.patient'
    _description = 'Patient'
    _inherit = ['mail.thread']
    _inherits = {'res.partner': 'partner_id'}
    _order = 'patient_code'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='restrict', auto_join=True, index=True)
    user_id = fields.Many2one(
        'res.users', string='Portal User', compute='_compute_user_id', store=True, index=True,
        help="The login of this patient: the user that shares the patient's contact.")
    patient_code = fields.Char(string='Patient Code', copy=False, readonly=True, index=True, default='New')
    national_id = fields.Char(string='National ID', copy=False, tracking=True)
    birth_date = fields.Date(tracking=True)
    age = fields.Integer(compute='_compute_age')
    sex = fields.Selection([('female', 'Female'), ('male', 'Male'), ('other', 'Other')])
    blood_group = fields.Selection([
        ('a+', 'A+'), ('a-', 'A-'), ('b+', 'B+'), ('b-', 'B-'),
        ('ab+', 'AB+'), ('ab-', 'AB-'), ('o+', 'O+'), ('o-', 'O-')])
    allergies = fields.Text()
    chronic_conditions = fields.Text()
    institution_ids = fields.Many2many(
        'res.company', 'medical_patient_company_rel', 'patient_id', 'company_id',
        string='Institutions', help="Institutions that hold care records of this patient.",
        default=lambda self: [(4, self.env.company.id)])
    consent_ids = fields.One2many('medical.consent', 'patient_id', string='Consents')
    active = fields.Boolean(default=True)
    history_html = fields.Html(compute='_compute_history_html', sanitize=False)

    _national_id_uniq = models.Constraint('unique(national_id)', 'A patient with this national ID already exists.')
    _patient_code_uniq = models.Constraint('unique(patient_code)', 'The patient code must be unique.')

    @api.depends('partner_id.user_ids')
    def _compute_user_id(self):
        for patient in self:
            patient.user_id = patient.partner_id.user_ids[:1]

    @api.depends('birth_date')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for patient in self:
            born = patient.birth_date
            patient.age = today.year - born.year - ((today.month, today.day) < (born.month, born.day)) if born else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('patient_code', 'New') == 'New':
                vals['patient_code'] = self.env['ir.sequence'].next_by_code('medical.patient') or 'New'
        return super().create(vals_list)

    @api.constrains('birth_date')
    def _check_birth_date(self):
        today = fields.Date.context_today(self)
        if any(patient.birth_date and patient.birth_date > today for patient in self):
            raise ValidationError(self.env._("The birth date cannot be in the future."))

    def _history_models(self):
        """Care models listed in the patient history. Add-on modules extend this list."""
        return ['medical.encounter']

    def get_history(self):
        """The patient's care records the current user may read, newest first (access rules apply)."""
        self.ensure_one()
        entries = []
        for model_name in self._history_models():
            model = self.env[model_name]
            if not model.has_access('read'):
                continue
            for record in model.search([('patient_id', '=', self.id)]):
                entries.append(record._history_entry())
        return sorted(entries, key=lambda e: e['date'] or fields.Datetime.now(), reverse=True)

    @api.depends_context('uid')
    @api.depends('patient_code')
    def _compute_history_html(self):
        for patient in self:
            rows = Markup('').join(
                Markup('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>') % (
                    entry['date'] and fields.Datetime.to_string(entry['date']) or '',
                    entry['kind'], entry['title'], entry['institution'])
                for entry in (patient.get_history() if patient.id else []))
            patient.history_html = Markup(
                '<table class="table table-sm"><thead><tr><th>Date</th><th>Type</th>'
                '<th>Summary</th><th>Institution</th></tr></thead><tbody>%s</tbody></table>') % rows

    def lookup_minimal(self, code_or_national_id):
        """Find a patient by code or national ID and return only name and code (no history)."""
        patient = self.sudo().search([
            '|', ('patient_code', '=', code_or_national_id), ('national_id', '=', code_or_national_id)], limit=1)
        return {'id': patient.id, 'name': patient.name, 'patient_code': patient.patient_code} if patient else {}
