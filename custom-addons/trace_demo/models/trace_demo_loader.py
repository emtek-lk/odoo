import random
from datetime import timedelta

from odoo import api, fields, models


class _Story:
    """Plays supply chain journeys through the real workflows, as the real users, with a moving clock."""

    def __init__(self, env):
        self.env = env
        self.rnd = random.Random(7)
        self.clock = fields.Datetime.now()
        self.users = {u.login[len('trace_'):]: u for u in env['res.users'].search([('login', '=like', 'trace\\_%')])}
        self.parties = {key: env.ref('trace_demo.party_%s' % key) for key in self.users}
        self.products = {p: env.ref('trace_demo.product_%s' % p) for p in (
            'tomato', 'carrot', 'paddy', 'rice', 'sauce', 'tealeaf', 'blacktea', 'cinnamon', 'cinnamon_ground')}

    def start(self, days_ago):
        self.clock = fields.Datetime.now() - timedelta(days=days_ago)

    def tick(self, hours=None):
        self.clock += timedelta(hours=hours or self.rnd.randint(5, 30))
        return self.clock

    def as_user(self, key, model):
        return self.env[model].with_user(self.users[key]).with_context(trace_event_date=self.tick())

    def harvest(self, key, product, qty, place, harvester=None, notes=None):
        return self.as_user(key, 'trace.batch').create({
            'product_id': self.products[product].id, 'initial_quantity': qty, 'origin_place': place,
            'harvest_date': self.clock.date(), 'harvester_id': self.parties[harvester].id if harvester else False,
            'plot': 'Plot %s' % self.rnd.randint(1, 12), 'notes': notes})

    def event(self, batch, key, event_type, notes=None, location=None, delta=0.0, **extra):
        return self.as_user(key, 'trace.event').create(dict({
            'batch_id': batch.id, 'event_type': event_type, 'notes': notes, 'location': location,
            'quantity_delta': delta}, **extra))

    def hand_over(self, batch, from_key, to_key, qty=None, accept=True, price=None):
        transfer = self.as_user(from_key, 'trace.transfer').create({
            'source_batch_id': batch.id, 'to_party_id': self.parties[to_key].id, 'quantity': qty or batch.quantity_remaining,
            'price': price or 0.0, 'reference': 'DN-%05d' % self.rnd.randint(1, 99999)})
        if accept:
            transfer.with_user(self.users[to_key]).with_context(trace_event_date=self.tick()).action_accept()
        return transfer.batch_id

    def process(self, key, kind, inputs, outputs, description):
        run = self.as_user(key, 'trace.process').create({
            'process_type': kind, 'description': description, 'location': self.parties[key].trace_region,
            'input_ids': [(0, 0, {'batch_id': b.id, 'quantity': q}) for b, q in inputs],
            'output_ids': [(0, 0, {'product_id': self.products[p].id, 'quantity': q}) for p, q in outputs]})
        run.with_context(trace_event_date=self.tick()).action_confirm()
        return run.output_ids.batch_id


class TraceDemoLoader(models.AbstractModel):
    _name = 'trace.demo.loader'
    _description = 'Supply Chain Demo Loader'

    @api.model
    def load_demo(self):
        if self.env.ref('trace_demo.demo_loaded', raise_if_not_found=False):
            return  # journeys are created once; updating the module must not duplicate them
        s = _Story(self.env)

        # 1. Tomatoes: farm -> cold chain -> FreshFoods -> sauce split into packs -> wholesale -> shops
        s.start(30)
        tomatoes = s.harvest('green_valley', 'tomato', 500, 'Terrace 4, Nuwara Eliya', harvester='crew')
        s.event(tomatoes, 'green_valley', 'inspected', 'Visual and sugar-level check passed', 'Green Valley packing shed')
        s.event(tomatoes, 'green_valley', 'stored', 'Cooled to 12 C', 'Green Valley cold room', temperature=12.0)
        tomatoes = s.hand_over(tomatoes, 'green_valley', 'coldchain', price=62000)
        s.event(tomatoes, 'coldchain', 'transported', 'Refrigerated truck, Nuwara Eliya to Colombo', 'A5 highway', temperature=11.5)
        s.event(tomatoes, 'coldchain', 'loss', '12 kg bruised in transit', 'Colombo depot', delta=-12)
        tomatoes = s.hand_over(tomatoes, 'coldchain', 'freshfoods', price=68000)
        s.event(tomatoes, 'freshfoods', 'quality_check', 'Brix 5.2, accepted', 'FreshFoods lab')
        sauce = s.process('freshfoods', 'process', [(tomatoes, 400)], [('sauce', 260)], 'washed, cooked, strained')
        packs = s.process('freshfoods', 'split', [(sauce, 260)], [('sauce', 130), ('sauce', 80), ('sauce', 50)], 'packed into cases')
        s.event(packs[0], 'freshfoods', 'packed', 'Glass jars, 12 per case', 'FreshFoods line 2')
        to_wholesale = s.hand_over(packs[0], 'freshfoods', 'wholesale', price=91000)
        to_citymart = s.hand_over(to_wholesale, 'wholesale', 'citymart', 60, price=48000)
        s.event(to_citymart, 'citymart', 'stored', 'On shelf, aisle 6', 'CityMart Colombo 03')
        s.event(to_citymart, 'citymart', 'sold', '25 jars sold', delta=-25)
        s.hand_over(packs[1], 'freshfoods', 'metro', price=52000, accept=False)  # waiting for acceptance

        # 2. Carrots with a simple route
        s.start(20)
        carrots = s.harvest('sunrise', 'carrot', 300, 'Orchard block B, Kandy')
        s.event(carrots, 'sunrise', 'inspected', 'Size grading A', 'Sunrise packing shed')
        carrots = s.hand_over(carrots, 'sunrise', 'swift', price=24000)
        s.event(carrots, 'swift', 'transported', 'Kandy to Colombo', 'A1 highway')
        carrots = s.hand_over(carrots, 'swift', 'wholesale', price=26500)
        shop = s.hand_over(carrots, 'wholesale', 'cornershop', 120, price=12000)
        s.event(shop, 'cornershop', 'sold', 'Sold loose', delta=-40)

        # 3. Paddy to rice, one recalled lot
        s.start(45)
        paddy = s.harvest('lotus', 'paddy', 1000, 'Field 7, Polonnaruwa')
        s.event(paddy, 'lotus', 'quality_check', 'Moisture 13%', 'Lotus drying yard')
        paddy = s.hand_over(paddy, 'lotus', 'mill', price=210000)
        rice = s.process('mill', 'process', [(paddy, 1000)], [('rice', 700)], 'dried, hulled and polished')
        bags = s.process('mill', 'split', [(rice, 700)], [('rice', 350), ('rice', 350)], 'packed into 25 kg bags')
        a = s.hand_over(bags[0], 'mill', 'metro', price=185000)
        s.hand_over(a, 'metro', 'supersaver', price=190000)
        bad = s.hand_over(bags[1], 'mill', 'metro', price=185000)
        s.event(bad, 'metro', 'stored', 'Warehouse 2', 'Metro Kandy')
        s.start(10)
        paddy_lot = s.harvest('lotus', 'paddy', 400, 'Field 9, Polonnaruwa')
        s.event(paddy_lot, 'lotus', 'quality_check', 'Aflatoxin test failed', 'Lotus drying yard')
        paddy_lot = s.hand_over(paddy_lot, 'lotus', 'mill', price=80000)
        rice_lot = s.process('mill', 'process', [(paddy_lot, 400)], [('rice', 280)], 'dried, hulled and polished')
        rice_lot = s.hand_over(rice_lot, 'mill', 'metro', price=74000)
        self.env['trace.batch'].with_user(s.users['lotus']).with_context(
            trace_recall_reason='Failed aflatoxin test: do not sell', trace_event_date=s.tick()).browse(
            paddy_lot.id).action_recall()

        # 4. Tea
        s.start(25)
        leaf = s.harvest('highland', 'tealeaf', 800, 'Ridge estate, Nuwara Eliya', harvester='crew')
        s.event(leaf, 'highland', 'inspected', 'Two leaves and a bud', 'Highland weighing shed')
        leaf = s.hand_over(leaf, 'highland', 'teafactory', price=96000)
        tea = s.process('teafactory', 'process', [(leaf, 800)], [('blacktea', 180)], 'withered, rolled, fermented and fired')
        s.event(tea, 'teafactory', 'quality_check', 'Cup tasting grade BOP', 'Ceylon Tea Factory lab')
        tea = s.hand_over(tea, 'teafactory', 'metro', price=252000)
        s.hand_over(tea, 'metro', 'cornershop', 60, price=95000)

        # 5. Cinnamon: merged from two lots
        s.start(35)
        c1 = s.harvest('spice', 'cinnamon', 120, 'Garden 2, Matale')
        c2 = s.harvest('spice', 'cinnamon', 90, 'Garden 5, Matale')
        c1 = s.hand_over(c1, 'spice', 'freshfoods', price=84000)
        c2 = s.hand_over(c2, 'spice', 'freshfoods', price=63000)
        merged = s.process('freshfoods', 'merge', [(c1, 120), (c2, 90)], [('cinnamon', 210)], 'blended lot')
        ground = s.process('freshfoods', 'process', [(merged, 210)], [('cinnamon_ground', 160)], 'dried and ground')
        s.hand_over(ground, 'freshfoods', 'supersaver', 100, price=140000)

        # mark done
        product = self.env.ref('trace_demo.product_tomato')
        self.env['ir.model.data'].create({
            'module': 'trace_demo', 'name': 'demo_loaded', 'model': 'trace.product', 'res_id': product.id, 'noupdate': True})
