from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestMgmtsystemNonconformityBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.quality_manager = cls.env.ref("base.user_admin")
        cls.process = cls.env["smq.process"].create({"code": "PR-BRIDGE", "name": "Test"})
        cls.doc_type = cls.env["smq.document.type"].create(
            {"name": "Formulaire Bridge", "code_prefix": "FBRIDGE"}
        )
        cls.document = cls.env["smq.document"].create(
            {"name": "Doc Bridge", "document_type_id": cls.doc_type.id}
        )
        cls.origin = cls.env.ref("mgmtsystem_nonconformity.nc_origin_process")

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.quality_manager)

    def _new_nc(self, **extra):
        vals = {
            "name": "NC test",
            "description": "Description de test",
            "quality_process_id": self.process.id,
            "smq_document_ids": [(4, self.document.id)],
            "origin_ids": [(4, self.origin.id)],
        }
        vals.update(extra)
        return self.env["mgmtsystem.nonconformity"].create(vals)

    def test_ref_uses_nc_prefix_sequence(self):
        nc = self._new_nc()
        self.assertTrue(nc.ref.startswith("NC-"))

    def test_linked_to_process_and_document(self):
        nc = self._new_nc()
        self.assertEqual(nc.quality_process_id, self.process)
        self.assertIn(nc, self.document.nonconformity_ids)
        self.assertEqual(self.process.nonconformity_count, 1)
        self.assertEqual(self.document.nonconformity_count, 1)

    def test_partner_and_manager_defaulted(self):
        nc = self._new_nc()
        self.assertTrue(nc.partner_id)
        self.assertTrue(nc.responsible_user_id)
        self.assertTrue(nc.manager_user_id)

    def test_full_workflow_to_closed(self):
        nc = self._new_nc()
        nc.action_start_analysis()
        self.assertEqual(nc.state, "analysis")

        with self.assertRaises(UserError):
            nc.action_start_treatment()
        nc.action_comments = "Plan d'action de test"
        nc.action_start_treatment()
        self.assertEqual(nc.state, "open")

        action = self.env["mgmtsystem.action"].create(
            {
                "name": "Action corrective test",
                "type_action": "correction",
                "user_id": self.quality_manager.id,
            }
        )
        nc.action_ids = [(4, action.id)]
        self.assertEqual(nc.action_count, 1)

        with self.assertRaises(UserError):
            nc.action_mark_resolved()
        action.stage_id = self.env.ref("mgmtsystem_action.stage_close").id
        nc.action_mark_resolved()
        self.assertEqual(nc.state, "resolved")

        with self.assertRaises(UserError):
            nc.action_close()
        action.efficacy_result = "effective"
        nc.evaluation_comments = "Vérification concluante"
        nc.action_close()
        self.assertEqual(nc.state, "done")
        self.assertTrue(nc.closing_date)
        self.assertEqual(nc.closed_by_id, self.quality_manager)

    def test_efficacy_result_syncs_efficacy_value(self):
        action = self.env["mgmtsystem.action"].create(
            {"name": "Action", "type_action": "correction", "user_id": self.quality_manager.id}
        )
        action.efficacy_result = "partial"
        self.assertEqual(action.efficacy_value, 50)
        action.efficacy_value = 0
        self.assertEqual(action.efficacy_result, "ineffective")

    def test_employee_cannot_start_treatment(self):
        nc = self._new_nc()
        nc.action_start_analysis()
        nc.action_comments = "Plan"
        employee_only = self.env["res.users"].create(
            {
                "name": "Employé Bridge",
                "login": "employe.bridge@example.com",
                "groups_id": [(6, 0, [self.env.ref("smq_quality.group_smq_employee").id])],
            }
        )
        with self.assertRaises(Exception):
            nc.with_user(employee_only).action_start_treatment()

    def test_cannot_close_without_action_comments_evaluation(self):
        nc = self._new_nc()
        nc.action_start_analysis()
        nc.action_comments = "Plan"
        nc.action_start_treatment()
        with self.assertRaises(ValidationError):
            nc.write({"stage_id": self.env.ref("mgmtsystem_nonconformity.stage_done").id})
