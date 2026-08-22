from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase


class TestSmqProcess(TransactionCase):
    def test_code_is_unique(self):
        self.env["smq.process"].create({"code": "PR-TEST", "name": "Test"})
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["smq.process"].create({"code": "PR-TEST", "name": "Autre"})

    def test_default_status_is_draft(self):
        process = self.env["smq.process"].create({"code": "PR-TEST2", "name": "Test"})
        self.assertEqual(process.status, "draft")
