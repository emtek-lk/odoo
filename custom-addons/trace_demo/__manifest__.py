{
    'name': 'Supply Chain Demo Data',
    'summary': 'Demo parties, logins and batch journeys for the supply chain modules. Never install in production.',
    'description': """
Farmers, harvesters, processors, transporters, distributors and retailers, each with a login, and a dozen
batches that travel through the chain using the real workflows (transfers, processing, splits, a recall).
Demo logins use the login as the password.
""",
    'category': 'Supply Chain',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Shamil Suraweera',
    'depends': ['trace_base', 'trace_custody', 'trace_process', 'trace_public'],
    'data': ['data/trace_demo.xml'],
}
