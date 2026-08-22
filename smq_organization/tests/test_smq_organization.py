from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase


class TestSmqOrganization(TransactionCase):
    def test_site_code_is_unique(self):
        self.env["smq.site"].create({"name": "Site A", "code": "SITE-TEST"})
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["smq.site"].create({"name": "Site B", "code": "SITE-TEST"})

    def test_process_can_be_linked_to_site_department_and_activities(self):
        site = self.env["smq.site"].create({"name": "Site A"})
        department = self.env["hr.department"].create({"name": "Qualité"})
        activity = self.env["smq.activity"].create({"name": "Activité A"})
        process = self.env["smq.process"].create(
            {
                "code": "PR-ORG-TEST",
                "name": "Test",
                "site_id": site.id,
                "department_id": department.id,
                "smq_activity_ids": [(4, activity.id)],
            }
        )
        self.assertEqual(process.site_id, site)
        self.assertEqual(process.department_id, department)
        self.assertIn(activity, process.smq_activity_ids)

    def test_scope_aggregates_sites_activities_and_processes(self):
        site = self.env["smq.site"].create({"name": "Site A"})
        activity = self.env["smq.activity"].create({"name": "Activité A"})
        process = self.env["smq.process"].create({"code": "PR-ORG-TEST2", "name": "Test"})
        scope = self.env["smq.scope"].create(
            {
                "name": "Périmètre test",
                "site_ids": [(4, site.id)],
                "activity_ids": [(4, activity.id)],
                "process_ids": [(4, process.id)],
            }
        )
        self.assertIn(site, scope.site_ids)
        self.assertIn(activity, scope.activity_ids)
        self.assertIn(process, scope.process_ids)

    def test_stakeholder_requires_category(self):
        stakeholder = self.env["smq.stakeholder"].create({"name": "Client X", "category": "customer"})
        self.assertEqual(stakeholder.category, "customer")
