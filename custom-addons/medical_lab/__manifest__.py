{
    'name': 'Medical Lab',
    'summary': 'Lab orders and results shared across institutions',
    'category': 'Healthcare',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Shamil Suraweera',
    'application': True,
    'depends': ['medical_base'],
    'data': [
        'security/medical_lab_security.xml',
        'security/ir.access.csv',
        'views/medical_lab_views.xml',
        'views/medical_lab_menus.xml',
    ],
}
