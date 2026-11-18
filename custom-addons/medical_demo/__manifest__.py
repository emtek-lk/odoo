{
    'name': 'Medical Demo Data',
    'summary': 'Demo institutions, people and records for the medical modules. Never install in production.',
    'description': """
Demo institutions (hospital, lab, pharmacy, clinic), staff, patients and a patient history
that spans all of them. Logins use the login as the password.
""",
    'category': 'Healthcare',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Shamil Suraweera',
    'depends': ['medical_base', 'medical_prescription', 'medical_lab', 'medical_portal'],
    'data': ['data/medical_demo.xml'],
}
