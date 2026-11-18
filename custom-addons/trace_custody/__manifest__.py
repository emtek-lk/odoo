{
    'name': 'Supply Chain Custody Transfers',
    'summary': 'Hand a batch to the next party, who accepts or rejects it',
    'category': 'Supply Chain',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Shamil Suraweera',
    'depends': ['trace_base'],
    'data': [
        'security/ir.access.csv',
        'data/trace_custody_data.xml',
        'views/trace_transfer_views.xml',
        'views/trace_custody_menus.xml',
    ],
}
