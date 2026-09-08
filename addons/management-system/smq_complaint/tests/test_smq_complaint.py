from psycopg2 import IntegrityError

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestSmqComplaint(TransactionCase):
    """Registre des réclamations clients : identification, réponse,
    liaison avec mgmtsystem.action (réutilisation pure OCA), workflow,
    permissions et intégration au dashboard SMQ."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.process = cls.env["smq.process"].create(
            {"code": "PR-COMPLAINT", "name": "Processus test"}
        )
        cls.partner = cls.env["res.partner"].create({"name": "Client test"})
        cls.stakeholder = cls.env["smq.stakeholder"].create(
            {"name": "Grand Client SA", "category": "customer", "partner_id": cls.partner.id}
        )
        cls.employee = cls.env["res.users"].create(
            {
                "name": "Employé SMQ Test",
                "login": "smq_complaint_employee_test",
                "groups_id": [
                    (6, 0, [
                        cls.env.ref("base.group_user").id,
                        cls.env.ref("smq_quality.group_smq_employee").id,
                    ])
                ],
            }
        )
        cls.writer = cls.env["res.users"].create(
            {
                "name": "Rédacteur SMQ Test",
                "login": "smq_complaint_writer_test",
                "groups_id": [
                    (6, 0, [
                        cls.env.ref("base.group_user").id,
                        cls.env.ref("smq_quality.group_smq_writer").id,
                    ])
                ],
            }
        )

    def _create_complaint(self, **extra):
        vals = {
            "name": "Réclamation test",
            "partner_id": self.partner.id,
            "description": "Le produit livré ne correspond pas à la commande.",
        }
        vals.update(extra)
        return self.env["smq.complaint"].create(vals)

    # ------------------------------------------------------------------
    # Création / référence
    # ------------------------------------------------------------------
    def test_01_create_complaint(self):
        complaint = self._create_complaint()
        self.assertEqual(complaint.state, "nouvelle")
        self.assertEqual(complaint.channel, "email")

    def test_02_reference_sequence(self):
        complaint1 = self._create_complaint()
        complaint2 = self._create_complaint()
        self.assertTrue(complaint1.reference.startswith("RC-"))
        self.assertNotEqual(complaint1.reference, complaint2.reference)

    def test_03_partner_required(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["smq.complaint"].create(
                {"name": "Sans client", "description": "Test", "partner_id": False}
            )

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------
    def test_04_stakeholder_link(self):
        complaint = self._create_complaint(stakeholder_id=self.stakeholder.id)
        self.assertEqual(complaint.stakeholder_id.category, "customer")

    def test_05_process_link_optional(self):
        complaint = self._create_complaint(process_id=self.process.id)
        self.assertEqual(complaint.process_id, self.process)
        complaint_no_process = self._create_complaint()
        self.assertFalse(complaint_no_process.process_id)

    # ------------------------------------------------------------------
    # Actions (mgmtsystem.action — réutilisation pure)
    # ------------------------------------------------------------------
    def test_06_action_link(self):
        complaint = self._create_complaint()
        action = self.env["mgmtsystem.action"].create(
            {"name": "Action liée", "type_action": "correction"}
        )
        complaint.action_ids = [(4, action.id)]
        self.assertIn(complaint, action.complaint_ids)
        self.assertEqual(action.complaint_count, 1)
        self.assertEqual(complaint.action_count, 1)

    def test_07_create_action_from_complaint(self):
        complaint = self._create_complaint()
        complaint.action_create_treatment_action()
        self.assertEqual(complaint.action_count, 1)
        self.assertEqual(complaint.action_ids.type_action, "correction")

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def test_08_workflow_transitions(self):
        complaint = self._create_complaint()
        self.assertEqual(complaint.state, "nouvelle")
        complaint.write({"state": "qualification"})
        complaint.write({"state": "traitement"})
        complaint.write({"state": "reponse_envoyee"})
        complaint.write({"state": "cloturee"})
        self.assertEqual(complaint.state, "cloturee")

    def test_09_invalid_state_rejected(self):
        complaint = self._create_complaint()
        with self.assertRaises(ValueError):
            complaint.write({"state": "etat_invalide"})

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------
    def test_10_employee_can_read(self):
        complaint = self._create_complaint()
        self.assertTrue(complaint.with_user(self.employee).read(["name"]))

    def test_11_employee_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env["smq.complaint"].with_user(self.employee).create(
                {
                    "name": "Réclamation interdite",
                    "partner_id": self.partner.id,
                    "description": "Test",
                }
            )

    def test_12_writer_can_create_but_not_unlink(self):
        complaint = self.env["smq.complaint"].with_user(self.writer).create(
            {
                "name": "Réclamation via rédacteur",
                "partner_id": self.partner.id,
                "description": "Test",
            }
        )
        self.assertTrue(complaint)
        with self.assertRaises(AccessError):
            complaint.with_user(self.writer).unlink()

    # ------------------------------------------------------------------
    # Recherche
    # ------------------------------------------------------------------
    def test_13_search_overdue_response(self):
        overdue = self._create_complaint(response_due_date="2000-01-01")
        not_overdue = self._create_complaint(response_due_date="2999-01-01")
        found = self.env["smq.complaint"].search(
            [
                ("response_due_date", "<", "2026-08-13"),
                ("state", "!=", "cloturee"),
            ]
        )
        self.assertIn(overdue, found)
        self.assertNotIn(not_overdue, found)

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def test_14_dashboard_tile_reflects_open_complaints(self):
        tile = self.env.ref("smq_complaint.smq_dashboard_tile_complaint")
        self.assertEqual(tile.kind, "module")
        before = self.env["smq.complaint"].search_count([("state", "!=", "cloturee")])
        self._create_complaint()
        self.assertEqual(tile.count, before + 1)
        self.assertEqual(tile._get_action_xmlid(), "smq_complaint.action_smq_complaint")
