from odoo import fields, models


class MedicalPatient(models.Model):
    _inherit = 'medical.patient'

    lab_order_ids = fields.One2many('medical.lab.order', 'patient_id', string='Lab Orders')

    def _history_models(self):
        return super()._history_models() + ['medical.lab.order']
