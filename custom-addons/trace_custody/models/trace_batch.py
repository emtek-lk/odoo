from odoo import models


class TraceBatch(models.Model):
    _inherit = 'trace.batch'

    def action_hand_over(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Hand over %s", self.name),
            'res_model': 'trace.transfer',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_source_batch_id': self.id, 'default_quantity': self.quantity_remaining},
        }
