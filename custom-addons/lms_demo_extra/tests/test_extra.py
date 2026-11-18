from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLmsExtraDemo(TransactionCase):

    def test_volume(self):
        self.assertGreaterEqual(self.env['lms.course'].search_count([]), 20)
        self.assertGreaterEqual(self.env['lms.lesson'].search_count([]), 70)
        self.assertGreaterEqual(self.env['lms.enrollment'].search_count([]), 70)
        self.assertGreaterEqual(self.env['res.users'].search_count([('login', '=like', 'lms\\_%')]), 30)

    def test_seat_limits_are_respected(self):
        for course in self.env['lms.course'].search([('max_students', '>', 0)]):
            taken = len(course.enrollment_ids.filtered(lambda e: e.state != 'dropped'))
            self.assertLessEqual(taken, course.max_students, '%s is over its seat limit' % course.name)

    def test_grades_and_progress(self):
        done = self.env['lms.enrollment'].search([('state', '=', 'completed')])
        self.assertTrue(done)
        self.assertTrue(all(e.grade_letter and e.progress == 100.0 for e in done))
