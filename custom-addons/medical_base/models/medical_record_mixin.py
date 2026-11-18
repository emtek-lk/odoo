from odoo import api, fields, models


class MedicalRecordMixin(models.AbstractModel):
    """Shared by every care record: ties it to a patient and an institution and logs outside reads."""
    _name = 'medical.record.mixin'
    _description = 'Medical Care Record'
    _check_company_auto = True

    patient_id = fields.Many2one('medical.patient', string='Patient', required=True, index=True)
    patient_user_id = fields.Many2one(
        'res.users', related='patient_id.user_id', store=True, index=True, string='Patient User')
    company_id = fields.Many2one(
        'res.company', string='Institution', required=True, index=True, readonly=True,
        default=lambda self: self.env.company)

    company_name = fields.Char(
        related='company_id.name', store=True, string='Institution Name',
        help="Readable even by staff of other institutions the record is shared with.")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # sudo: an institution that records care becomes linked to the patient, whatever its access to patients
        for record in records:
            record.patient_id.sudo().institution_ids = [(4, record.company_id.id)]
        return records

    def web_read(self, specification):
        self._log_outside_access()
        return super().web_read(specification)

    def _log_outside_access(self):
        """Record reads of other institutions' data (not the owner's own staff, nor the patient)."""
        user = self.env.user
        if self.env.su:
            return
        outside = self.filtered(
            lambda r: r.company_id not in user.company_ids and r.patient_user_id != user)
        if outside:
            self.env['medical.access.log'].sudo().create([{
                'user_id': user.id,
                'accessor_company_id': self.env.company.id,
                'owner_company_id': record.company_id.id,
                'patient_id': record.patient_id.id,
                'res_model': record._name,
                'res_id': record.id,
                'summary': record.display_name,
            } for record in outside])

    def _history_entry(self):
        """One line of the patient history; add-on models override ``_history_kind``/``_history_title``."""
        self.ensure_one()
        return {
            'date': self._history_date(),
            'kind': self._history_kind(),
            'title': self._history_title(),
            'institution': self.company_name,
            'res_model': self._name,
            'res_id': self.id,
        }

    def _history_date(self):
        return self.create_date

    def _history_kind(self):
        return self._description

    def _history_title(self):
        return self.display_name
