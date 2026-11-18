from odoo import http
from odoo.http import request


class TracePublic(http.Controller):

    @http.route('/trace/<string:token>', type='http', auth='public', sitemap=False)
    def trace_page(self, token, **kw):
        # sudo: the public has no account; only fields chosen in _public_journey() ever reach the page
        batch = request.env['trace.batch'].sudo().search([('public_token', '=', token)], limit=1)
        if not batch:
            return request.not_found()
        return request.render('trace_public.trace_page', {
            'batch': batch,
            'journey': batch._public_journey(),
            'intact': batch._public_history_intact(),
            'recalled': batch.state == 'recalled',
        })
