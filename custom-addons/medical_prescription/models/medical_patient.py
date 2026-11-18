from odoo import fields, models


class MedicalPatient(models.Model):
    _inherit = 'medical.patient'

    prescription_ids = fields.One2many('medical.prescription', 'patient_id', string='Prescriptions')

    def _history_models(self):
        return super()._history_models() + ['medical.prescription', 'medical.dispense']
