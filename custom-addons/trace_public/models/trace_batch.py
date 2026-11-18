from urllib.parse import quote

from odoo import api, fields, models


class TraceBatch(models.Model):
    _inherit = 'trace.batch'

    public_url = fields.Char(compute='_compute_public_url')
    qr_code_html = fields.Html(compute='_compute_public_url', sanitize=False)

    @api.depends('public_token')
    def _compute_public_url(self):
        for batch in self:
            url = '%s/trace/%s' % (batch.get_base_url().rstrip('/'), batch.public_token) if batch.public_token else False
            batch.public_url = url
            batch.qr_code_html = (
                '<img alt="QR code" width="180" height="180" src="/report/barcode/QR/%s?width=360&amp;height=360"/>'
                % quote(url, safe='')) if url else False

    def _public_journey(self):
        """What a consumer may see: public events of this batch and everything it was made from."""
        self.ensure_one()
        batches = self.sudo().get_upstream(include_self=True)
        events = self.env['trace.event'].sudo().search([('batch_id', 'in', batches.ids), ('is_public', '=', True)])
        labels = dict(self.env['trace.event']._fields['event_type'].selection)
        journey = []
        for event in events.sorted(lambda e: (e.date, e.id)):
            journey.append({
                'date': event.date,
                'type': labels.get(event.event_type, event.event_type),
                'party': event.party_id.name,
                'region': event.party_id.trace_region,
                'batch': event.batch_id.name,
            })
        return journey

    def _public_history_intact(self):
        self.ensure_one()
        return all(batch.verify_chain()[0] for batch in self.sudo().get_upstream(include_self=True))
