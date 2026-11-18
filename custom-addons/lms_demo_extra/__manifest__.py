{
    'name': 'Institute LMS Demo Data (Extended)',
    'summary': 'A larger demo dataset: more instructors, students, courses, lessons and enrollments.',
    'description': """
Adds instructors, students, courses, lessons and enrollments on top of the demo data of the Institute LMS.
Demo logins use the login as the password. Never install in production.
""",
    'category': 'Education',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Shamil Suraweera',
    'depends': ['lms_institute'],
    'data': ['data/lms_demo_extra.xml'],
}
