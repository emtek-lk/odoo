{
    'name': 'Supply Chain Demo Data (Extended)',
    'summary': 'A larger demo dataset: more parties and about forty extra batch journeys.',
    'description': """
Adds parties with logins, products and randomised batch journeys (transfers, processing, splits, merges,
losses, a few recalls and pending hand-overs) on top of trace_demo. Never install in production.
""",
    'category': 'Supply Chain',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Shamil Suraweera',
    'depends': ['trace_demo'],
    'data': ['data/trace_demo_extra.xml'],
}
