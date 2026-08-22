from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSmqRisk(TransactionCase):
    """Registre générique smq.risk : identification, source, évaluation,
    calculs, liaison avec mgmtsystem.action (réutilisation pure OCA),
    workflow et permissions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.process = cls.env["smq.process"].create(
            {"code": "PR-RISK", "name": "Processus test"}
        )
        cls.stakeholder = cls.env["smq.stakeholder"].create(
            {"name": "Client test", "category": "customer"}
        )
        cls.source_process = cls.env.ref("smq_risk.smq_risk_source_type_process")
        cls.source_stakeholder = cls.env.ref("smq_risk.smq_risk_source_type_stakeholder")
        cls.source_context = cls.env.ref("smq_risk.smq_risk_source_type_context")
        cls.prob_low = cls.env.ref("smq_risk.smq_risk_probability_1")
        cls.prob_high = cls.env.ref("smq_risk.smq_risk_probability_5")
        cls.impact_low = cls.env.ref("smq_risk.smq_risk_impact_1")
        cls.impact_high = cls.env.ref("smq_risk.smq_risk_impact_5")
        # base.group_user (Internal User) est requis pour les droits de base
        # (ex. lecture de ir.sequence) - un vrai utilisateur SMQ est toujours
        # un utilisateur interne, en plus de son groupe métier SMQ.
        cls.employee = cls.env["res.users"].create(
            {
                "name": "Employé SMQ Test",
                "login": "smq_risk_employee_test",
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
                "login": "smq_risk_writer_test",
                "groups_id": [
                    (6, 0, [
                        cls.env.ref("base.group_user").id,
                        cls.env.ref("smq_quality.group_smq_writer").id,
                    ])
                ],
            }
        )

    def _create_risk(self, **extra):
        vals = {
            "name": "Risque test",
            "source_type_id": self.source_process.id,
            "process_id": self.process.id,
            "probability_id": self.prob_low.id,
            "impact_id": self.impact_low.id,
        }
        vals.update(extra)
        return self.env["smq.risk"].create(vals)

    # ------------------------------------------------------------------
    # 1. Création d'un risque
    # ------------------------------------------------------------------
    def test_01_create_risk(self):
        risk = self._create_risk()
        self.assertEqual(risk.nature, "risk")
        self.assertEqual(risk.state, "nouveau")

    # ------------------------------------------------------------------
    # 2. Génération de la référence
    # ------------------------------------------------------------------
    def test_02_reference_sequence(self):
        risk1 = self._create_risk()
        risk2 = self._create_risk()
        self.assertTrue(risk1.reference.startswith("RISK-"))
        self.assertNotEqual(risk1.reference, risk2.reference)

    # ------------------------------------------------------------------
    # 3. Création d'une opportunité
    # ------------------------------------------------------------------
    def test_03_create_opportunity(self):
        risk = self._create_risk(nature="opportunity")
        self.assertEqual(risk.nature, "opportunity")

    # ------------------------------------------------------------------
    # 4. Rattachement à un processus
    # ------------------------------------------------------------------
    def test_04_process_link(self):
        risk = self._create_risk()
        self.assertEqual(risk.process_id, self.process)
        self.assertEqual(
            self.env["smq.risk"].search_count([("process_id", "=", self.process.id)]),
            1,
        )

    # ------------------------------------------------------------------
    # 5. Source = Processus
    # ------------------------------------------------------------------
    def test_05_source_process(self):
        risk = self._create_risk(
            source_type_id=self.source_process.id, process_id=self.process.id
        )
        self.assertEqual(risk.source_type_id.code, "process")

    # ------------------------------------------------------------------
    # 6. Source = Partie intéressée
    # ------------------------------------------------------------------
    def test_06_source_stakeholder(self):
        risk = self._create_risk(
            source_type_id=self.source_stakeholder.id,
            stakeholder_id=self.stakeholder.id,
        )
        self.assertEqual(risk.stakeholder_id, self.stakeholder)

    # ------------------------------------------------------------------
    # 7. Validation des contraintes de source
    # ------------------------------------------------------------------
    def test_07_source_constraint_stakeholder_required(self):
        with self.assertRaises(ValidationError):
            self._create_risk(
                source_type_id=self.source_stakeholder.id, stakeholder_id=False
            )

    def test_07_source_constraint_context_description_required(self):
        with self.assertRaises(ValidationError):
            self._create_risk(
                source_type_id=self.source_context.id, source_description=False
            )

    def test_07_source_constraint_satisfied_passes(self):
        risk = self._create_risk(
            source_type_id=self.source_context.id,
            source_description="Nouvelle réglementation sectorielle.",
        )
        self.assertTrue(risk)

    # ------------------------------------------------------------------
    # 8. Calcul probability x impact
    # ------------------------------------------------------------------
    def test_08_risk_score_computation(self):
        risk = self._create_risk(
            probability_id=self.prob_high.id, impact_id=self.impact_high.id
        )
        self.assertEqual(
            risk.risk_score, self.prob_high.value * self.impact_high.value
        )

    # ------------------------------------------------------------------
    # 9. Calcul de la criticité
    # ------------------------------------------------------------------
    def test_09_criticality_level_computation(self):
        low_risk = self._create_risk(
            probability_id=self.prob_low.id, impact_id=self.impact_low.id
        )
        high_risk = self._create_risk(
            probability_id=self.prob_high.id, impact_id=self.impact_high.id
        )
        self.assertTrue(low_risk.criticality_level_id)
        self.assertTrue(high_risk.criticality_level_id)
        self.assertNotEqual(low_risk.criticality_level_id, high_risk.criticality_level_id)
        self.assertEqual(
            high_risk.criticality_level_id,
            self.env.ref("smq_risk.smq_risk_criticality_critical"),
        )

    # ------------------------------------------------------------------
    # 10. Calcul du risque résiduel
    # ------------------------------------------------------------------
    def test_10_residual_risk_computation(self):
        risk = self._create_risk(
            probability_id=self.prob_high.id,
            impact_id=self.impact_high.id,
            residual_probability_id=self.prob_low.id,
            residual_impact_id=self.impact_low.id,
        )
        self.assertEqual(
            risk.residual_risk_score, self.prob_low.value * self.impact_low.value
        )
        self.assertLess(risk.residual_risk_score, risk.risk_score)

    def test_10_residual_risk_empty_when_not_assessed(self):
        risk = self._create_risk()
        self.assertFalse(risk.residual_risk_score)

    # ------------------------------------------------------------------
    # 11. Liaison avec mgmtsystem.action (M2M, pas de moteur parallèle)
    # ------------------------------------------------------------------
    def test_11_action_link(self):
        risk = self._create_risk()
        action = self.env["mgmtsystem.action"].create(
            {"name": "Action liée", "type_action": "prevention"}
        )
        risk.action_ids = [(4, action.id)]
        self.assertIn(risk, action.risk_ids)
        self.assertEqual(action.risk_count, 1)
        self.assertEqual(risk.action_count, 1)

    # ------------------------------------------------------------------
    # 12/13. Création d'une action depuis un risque -> type_action=prevention
    # ------------------------------------------------------------------
    def test_12_13_create_action_from_risk_is_prevention(self):
        risk = self._create_risk(nature="risk")
        risk.action_create_treatment_action()
        self.assertEqual(risk.action_count, 1)
        self.assertEqual(risk.action_ids.type_action, "prevention")

    # ------------------------------------------------------------------
    # 14. Création d'une action depuis une opportunité -> type_action=improvement
    # ------------------------------------------------------------------
    def test_14_create_action_from_opportunity_is_improvement(self):
        risk = self._create_risk(nature="opportunity")
        risk.action_create_treatment_action()
        self.assertEqual(risk.action_ids.type_action, "improvement")

    # ------------------------------------------------------------------
    # 15. Permissions (employé lecture seule, rédacteur crée mais ne
    # supprime pas, cf. conception validée section 10/16)
    # ------------------------------------------------------------------
    def test_15_employee_can_read(self):
        risk = self._create_risk()
        self.assertTrue(risk.with_user(self.employee).read(["name"]))

    def test_15_employee_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env["smq.risk"].with_user(self.employee).create(
                {
                    "name": "Risque interdit",
                    "source_type_id": self.source_process.id,
                    "process_id": self.process.id,
                    "probability_id": self.prob_low.id,
                    "impact_id": self.impact_low.id,
                }
            )

    def test_15_writer_can_create_but_not_unlink(self):
        risk = self.env["smq.risk"].with_user(self.writer).create(
            {
                "name": "Risque via rédacteur",
                "source_type_id": self.source_process.id,
                "process_id": self.process.id,
                "probability_id": self.prob_low.id,
                "impact_id": self.impact_low.id,
            }
        )
        self.assertTrue(risk)
        with self.assertRaises(AccessError):
            risk.with_user(self.writer).unlink()

    # ------------------------------------------------------------------
    # 16. Workflow (transitions simples, statut atteignable jusqu'à clôture)
    # ------------------------------------------------------------------
    def test_16_workflow_transitions(self):
        risk = self._create_risk()
        self.assertEqual(risk.state, "nouveau")
        risk.write({"state": "en_traitement"})
        risk.write({"state": "sous_surveillance"})
        risk.write({"state": "cloture"})
        self.assertEqual(risk.state, "cloture")

    # ------------------------------------------------------------------
    # 17. Archivage/désactivation des niveaux de référence
    # ------------------------------------------------------------------
    def test_17_probability_can_be_archived(self):
        custom_level = self.env["smq.risk.probability"].create(
            {"name": "Niveau temporaire", "value": 9, "sequence": 99}
        )
        custom_level.active = False
        self.assertNotIn(
            custom_level, self.env["smq.risk.probability"].search([])
        )
        self.assertIn(
            custom_level,
            self.env["smq.risk.probability"].with_context(active_test=False).search([]),
        )
