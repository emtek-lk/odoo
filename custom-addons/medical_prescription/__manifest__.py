{
    'name': 'Medical Prescriptions',
    'summary': 'Prescriptions issued by doctors and dispensed by pharmacies',
    'category': 'Healthcare',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Shamil Suraweera',
    'application': True,
    'depends': ['medical_base'],
    'data': [
        'security/medical_prescription_security.xml',
        'security/ir.access.csv',
        'views/medical_prescription_views.xml',
        'views/medical_prescription_menus.xml',
    ],
}
