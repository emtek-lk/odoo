import os

from odoo import api, fields, models
from odoo.modules import get_module_path

# Modules living in a directory with one of these names count as custom.
CUSTOM_ADDONS_DIRS = ('custom-addons',)


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    module_source = fields.Selection(
        [('official', 'Odoo Modules'), ('custom', 'Custom Modules')],
        string='Source', compute='_compute_module_source', store=True)

    @api.depends('name')
    def _compute_module_source(self):
        for module in self:
            path = get_module_path(module.name, display_warning=False)
            parent = os.path.basename(os.path.dirname(path)) if path else ''
            module.module_source = 'custom' if parent in CUSTOM_ADDONS_DIRS else 'official'

    @api.model
    def update_list(self):
        res = super().update_list()
        self._fill_missing_module_source()
        return res

    def _register_hook(self):
        super()._register_hook()
        self._fill_missing_module_source()

    @api.model
    def _fill_missing_module_source(self):
        """Modules registered while installing from the command line can miss the stored compute."""
        missing = self.sudo().search([('module_source', '=', False)])
        if missing:
            missing._compute_module_source()
