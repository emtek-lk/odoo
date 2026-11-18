{
    'name': 'Medical Demo Data (Extended)',
    'summary': 'A larger demo dataset: more institutions, patients, encounters, prescriptions, lab orders and consents.',
    'description': """
Adds a second hospital, pharmacy and lab, about 25 more patients and their visits, prescriptions,
dispensing, lab results and consents on top of medical_demo. Demo logins use the login as the password.
Never install in production.
""",
    'category': 'Healthcare',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Shamil Suraweera',
    'depends': ['medical_demo'],
    'data': [
        'data/medical_demo_extra.xml',
        'data/medical_demo_admin.xml',
    ],
}
