import random

from odoo import api, models
from odoo.addons.trace_demo.models.trace_demo_loader import _Story


class TraceDemoExtraLoader(models.AbstractModel):
    _name = 'trace.demo.extra.loader'
    _description = 'Supply Chain Extended Demo Loader'

    @api.model
    def load_demo(self):
        if self.env.ref('trace_demo_extra.demo_loaded', raise_if_not_found=False):
            return
        s = _Story(self.env)
        s.rnd = random.Random(2026)
        for key in ('potato', 'onion', 'banana', 'coconut', 'coconutoil', 'chilli', 'chillipowder', 'juice'):
            s.products[key] = self.env.ref('trace_demo_extra.product_%s' % key)
        by_role = {}
        for key, party in s.parties.items():
            for code in party.sudo().trace_role_ids.mapped('code'):
                by_role.setdefault(code, []).append(key)
        farmers, harvesters = by_role['farmer'], by_role['harvester']
        carriers, processors = by_role['transporter'], by_role['processor']
        distributors, retailers = by_role['distributor'], by_role['retailer']

        # crop -> (processed product, which processors can handle it, typical yield)
        crops = {
            'tomato': ('sauce', ['freshfoods'], 0.55), 'carrot': (None, [], 1), 'paddy': ('rice', ['mill'], 0.7),
            'tealeaf': ('blacktea', ['teafactory'], 0.22), 'cinnamon': ('cinnamon_ground', ['spiceroute', 'freshfoods'], 0.75),
            'potato': (None, [], 1), 'onion': (None, [], 1), 'banana': ('juice', ['tropic'], 0.5),
            'coconut': ('coconutoil', ['oilmills'], 0.3), 'chilli': ('chillipowder', ['spiceroute'], 0.2),
        }
        places = ['North block', 'Terrace 2', 'River field', 'Lower slope', 'Plot 14', 'Hill garden', 'East paddock']
        crop_names = list(crops)
        recall_journeys = {9, 27}

        for n in range(40):
            crop = crop_names[n % len(crop_names)]
            processed, proc_options, yield_ratio = crops[crop]
            farm = s.rnd.choice(farmers)
            s.start(s.rnd.randint(30, 160))
            qty = s.rnd.choice([200, 300, 400, 500, 800, 1000, 1500])
            batch = s.harvest(farm, crop, qty, '%s, %s' % (s.rnd.choice(places), s.parties[farm].trace_region),
                              harvester=s.rnd.choice(harvesters) if s.rnd.random() < 0.4 else None)
            root = batch
            s.event(batch, farm, 'inspected', s.rnd.choice(['Grade A', 'Grade B', 'Passed visual check', 'Moisture within limits']), 'Packing shed')
            if s.rnd.random() < 0.5:
                s.event(batch, farm, 'stored', 'Held before dispatch', 'Farm store', temperature=round(s.rnd.uniform(8, 24), 1))
            holder = farm
            carrier = s.rnd.choice(carriers)
            batch = s.hand_over(batch, holder, carrier, price=round(qty * s.rnd.uniform(60, 220)))
            holder = carrier
            s.event(batch, holder, 'transported', 'Road transport', 'Highway', temperature=round(s.rnd.uniform(10, 28), 1))
            if s.rnd.random() < 0.45:
                s.event(batch, holder, 'loss', 'Damaged in transit', delta=-round(batch.quantity_remaining * s.rnd.uniform(0.01, 0.05), 1))

            if processed and s.rnd.random() < 0.85:
                proc = s.rnd.choice(proc_options)
                batch = s.hand_over(batch, holder, proc, price=round(qty * s.rnd.uniform(70, 240)))
                holder = proc
                s.event(batch, holder, 'quality_check', 'Incoming inspection passed', 'Factory lab')
                use = round(batch.quantity_remaining * s.rnd.uniform(0.7, 1.0), 1)
                batch = s.process(holder, 'process', [(batch, use)], [(processed, round(use * yield_ratio, 1))],
                                  s.rnd.choice(['cleaned and processed', 'processed and packed', 'milled and refined']))
                if s.rnd.random() < 0.5 and batch.quantity_remaining > 20:
                    half = round(batch.quantity_remaining / 2, 1)
                    parts = s.process(holder, 'split', [(batch, batch.quantity_remaining)],
                                      [(processed, half), (processed, round(batch.quantity_remaining - half, 4))], 'packed into lots')
                    batch = parts[0]
                    if s.rnd.random() < 0.3:
                        s.hand_over(parts[1], holder, s.rnd.choice(distributors), accept=False)  # waiting for acceptance
                s.event(batch, holder, 'packed', 'Labelled for retail', 'Packing line')

            dist = s.rnd.choice(distributors)
            batch = s.hand_over(batch, holder, dist, price=round(qty * s.rnd.uniform(90, 300)))
            holder = dist
            for shop in s.rnd.sample(retailers, s.rnd.randint(1, 2)):
                remaining = batch.quantity_remaining
                if remaining < 20:
                    break
                share = round(remaining * s.rnd.uniform(0.3, 0.6), 1)
                accept = s.rnd.random() > 0.08
                moved = s.hand_over(batch, holder, shop, share, price=round(share * s.rnd.uniform(100, 350)), accept=accept)
                if accept:
                    s.event(moved, shop, 'stored', 'On shelf', 'Store')
                    if s.rnd.random() < 0.7:
                        s.event(moved, shop, 'sold', 'Sold to customers', delta=-round(moved.quantity_remaining * s.rnd.uniform(0.2, 0.7), 1))
            if n in recall_journeys:
                self.env['trace.batch'].with_user(s.users[farm]).with_context(
                    trace_recall_reason='Quality alert on this harvest', trace_event_date=s.tick()).browse(root.id).action_recall()

        product = self.env.ref('trace_demo_extra.product_potato')
        self.env['ir.model.data'].create({
            'module': 'trace_demo_extra', 'name': 'demo_loaded', 'model': 'trace.product', 'res_id': product.id, 'noupdate': True})
