{
    'name': 'Medical Base',
    'summary': 'Patients, practitioners, institutions, consent and encounters shared across institutions',
    'description': """
Core of the medical records suite.

* Institutions (hospitals, clinics, labs, pharmacies) are companies
* Patients and practitioners with a cross-institution patient code
* Patient consent grants with scope and expiry
* Audit log of every cross-institution read
* Encounters and a combined patient history
""",
    'category': 'Healthcare',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Shamil Suraweera',
    'application': True,
    'depends': ['base', 'mail'],
    'data': [
        'security/medical_security.xml',
        'security/ir.access.csv',
        'data/medical_data.xml',
        'views/res_company_views.xml',
        'views/medical_patient_views.xml',
        'views/medical_practitioner_views.xml',
        'views/medical_consent_views.xml',
        'views/medical_encounter_views.xml',
        'views/medical_access_log_views.xml',
        'views/medical_menus.xml',
    ],
}
