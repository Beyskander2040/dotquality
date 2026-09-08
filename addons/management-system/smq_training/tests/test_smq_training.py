from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSmqTraining(TransactionCase):
    """Formations : identification, participants/compétences (référence
    pure à hr.employee/hr.skill), liaison avec mgmtsystem.action
    (réutilisation pure OCA), workflow, permissions et dashboard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.process = cls.env["smq.process"].create(
            {"code": "PR-TRAINING", "name": "Processus test"}
        )
        cls.employee = cls.env["hr.employee"].create({"name": "Employé test"})
        cls.skill_type = cls.env["hr.skill.type"].create({"name": "Type compétence test"})
        cls.skill = cls.env["hr.skill"].create(
            {"name": "Compétence test", "skill_type_id": cls.skill_type.id}
        )
        cls.smq_employee = cls.env["res.users"].create(
            {
                "name": "Employé SMQ Test",
                "login": "smq_training_employee_test",
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
                "login": "smq_training_writer_test",
                "groups_id": [
                    (6, 0, [
                        cls.env.ref("base.group_user").id,
                        cls.env.ref("smq_quality.group_smq_writer").id,
                    ])
                ],
            }
        )

    def _create_training(self, **extra):
        vals = {"name": "Formation test"}
        vals.update(extra)
        return self.env["smq.training"].create(vals)

    # ------------------------------------------------------------------
    # Création / référence
    # ------------------------------------------------------------------
    def test_01_create_training(self):
        training = self._create_training()
        self.assertEqual(training.state, "identifiee")
        self.assertEqual(training.training_type, "interne")

    def test_02_reference_sequence(self):
        training1 = self._create_training()
        training2 = self._create_training()
        self.assertTrue(training1.reference.startswith("FORM-"))
        self.assertNotEqual(training1.reference, training2.reference)

    # ------------------------------------------------------------------
    # Participants et compétences — référence pure hr.employee/hr.skill
    # ------------------------------------------------------------------
    def test_03_employees_and_skills_link(self):
        training = self._create_training(
            employee_ids=[(4, self.employee.id)], skill_ids=[(4, self.skill.id)]
        )
        self.assertIn(self.employee, training.employee_ids)
        self.assertIn(self.skill, training.skill_ids)
        # Aucune donnée dupliquée : ce sont les enregistrements RH existants.
        self.assertEqual(training.employee_ids.id, self.employee.id)

    def test_04_process_link_optional(self):
        training = self._create_training(process_id=self.process.id)
        self.assertEqual(training.process_id, self.process)
        training_no_process = self._create_training()
        self.assertFalse(training_no_process.process_id)

    # ------------------------------------------------------------------
    # Actions (mgmtsystem.action — réutilisation pure)
    # ------------------------------------------------------------------
    def test_05_action_link(self):
        training = self._create_training()
        action = self.env["mgmtsystem.action"].create(
            {"name": "Action liée", "type_action": "improvement"}
        )
        training.action_ids = [(4, action.id)]
        self.assertIn(training, action.training_ids)
        self.assertEqual(action.training_count, 1)
        self.assertEqual(training.action_count, 1)

    def test_06_create_action_from_training_is_improvement(self):
        training = self._create_training()
        training.action_create_treatment_action()
        self.assertEqual(training.action_count, 1)
        self.assertEqual(training.action_ids.type_action, "improvement")

    # ------------------------------------------------------------------
    # Évaluation d'efficacité (globale à la session)
    # ------------------------------------------------------------------
    def test_07_efficacy_evaluation(self):
        training = self._create_training()
        training.write(
            {
                "state": "evaluee",
                "efficacy_result": "effective",
                "efficacy_user_id": self.env.user.id,
            }
        )
        self.assertEqual(training.efficacy_result, "effective")

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def test_08_workflow_transitions(self):
        training = self._create_training()
        self.assertEqual(training.state, "identifiee")
        training.write({"state": "planifiee"})
        training.write({"state": "realisee"})
        training.write({"state": "evaluee"})
        self.assertEqual(training.state, "evaluee")

    def test_09_invalid_state_rejected(self):
        training = self._create_training()
        with self.assertRaises(ValueError):
            training.write({"state": "etat_invalide"})

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------
    def test_10_employee_can_read(self):
        training = self._create_training()
        self.assertTrue(training.with_user(self.smq_employee).read(["name"]))

    def test_11_employee_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env["smq.training"].with_user(self.smq_employee).create(
                {"name": "Formation interdite"}
            )

    def test_12_writer_can_create_but_not_unlink(self):
        training = self.env["smq.training"].with_user(self.writer).create(
            {"name": "Formation via rédacteur"}
        )
        self.assertTrue(training)
        with self.assertRaises(AccessError):
            training.with_user(self.writer).unlink()

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def test_13_dashboard_tile_reflects_open_trainings(self):
        tile = self.env.ref("smq_training.smq_dashboard_tile_training")
        self.assertEqual(tile.kind, "module")
        before = self.env["smq.training"].search_count([("state", "!=", "annulee")])
        self._create_training()
        self.assertEqual(tile.count, before + 1)
        self.assertEqual(tile._get_action_xmlid(), "smq_training.action_smq_training")
