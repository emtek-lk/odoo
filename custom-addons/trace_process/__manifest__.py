{
    'name': 'Supply Chain Processing',
    'summary': 'Turn batches into new batches: processing, splits and merges with full lineage',
    'category': 'Supply Chain',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Shamil Suraweera',
    'depends': ['trace_base'],
    'data': [
        'security/ir.access.csv',
        'data/trace_process_data.xml',
        'views/trace_process_views.xml',
        'views/trace_process_menus.xml',
    ],
}
