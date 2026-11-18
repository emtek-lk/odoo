{
    'name': 'Supply Chain Traceability',
    'summary': 'Batch origin and tamper-evident history across farmers, processors and distributors',
    'description': """
Track a crop or product from its origin through every handler.

* Parties (farmers, harvesters, processors, transporters, distributors, retailers) with roles
* Batches with origin, current holder and parent/child lineage
* Append-only event ledger secured with a hash chain
* Downstream parties read the full upstream history
""",
    'category': 'Supply Chain',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Shamil Suraweera',
    'application': True,
    'depends': ['base', 'mail'],
    'data': [
        'security/trace_security.xml',
        'security/ir.access.csv',
        'data/trace_data.xml',
        'views/res_partner_views.xml',
        'views/trace_product_views.xml',
        'views/trace_batch_views.xml',
        'views/trace_event_views.xml',
        'views/trace_menus.xml',
    ],
}
