{
    'name': 'Supply Chain Public Trace Page',
    'summary': 'QR code and a public page where consumers see the journey of a batch',
    'category': 'Supply Chain',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Shamil Suraweera',
    'depends': ['trace_base', 'portal'],
    'data': [
        'views/trace_batch_views.xml',
        'views/trace_public_templates.xml',
    ],
}
