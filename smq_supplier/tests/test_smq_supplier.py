from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSmqSupplier(TransactionCase):
    """Évaluation fournisseur : le fournisseur reste res.partner (aucune
    fiche recréée), critères pondérés, score global et niveau de
    qualification calculés, liaison avec mgmtsystem.action (réutilisation
    pure OCA), permissions et dashboard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Fournisseur test"})
        cls.stakeholder = cls.env["smq.stakeholder"].create(
            {"name": "Fournisseur test (partie intéressée)", "category": "supplier", "partner_id": cls.partner.id}
        )
        cls.criterion_a = cls.env["smq.supplier.criterion"].create(
            {"name": "Critère A", "weight": 3}
        )
        cls.criterion_b = cls.env["smq.supplier.criterion"].create(
            {"name": "Critère B", "weight": 1}
        )
        cls.employee = cls.env["res.users"].create(
            {
                "name": "Employé SMQ Test",
                "login": "smq_supplier_employee_test",
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
                "login": "smq_supplier_writer_test",
                "groups_id": [
                    (6, 0, [
                        cls.env.ref("base.group_user").id,
                        cls.env.ref("smq_quality.group_smq_writer").id,
                    ])
                ],
            }
        )

    def _create_evaluation(self, **extra):
        vals = {"partner_id": self.partner.id}
        vals.update(extra)
        return self.env["smq.supplier.evaluation"].create(vals)

    # ------------------------------------------------------------------
    # Création / référence / identité fournisseur
    # ------------------------------------------------------------------
    def test_01_create_evaluation(self):
        evaluation = self._create_evaluation()
        self.assertEqual(evaluation.state, "draft")
        self.assertEqual(evaluation.partner_id, self.partner)

    def test_02_reference_sequence(self):
        eval1 = self._create_evaluation()
        eval2 = self._create_evaluation()
        self.assertTrue(eval1.reference.startswith("SUPP-"))
        self.assertNotEqual(eval1.reference, eval2.reference)

    def test_03_partner_not_duplicated(self):
        evaluation = self._create_evaluation(stakeholder_id=self.stakeholder.id)
        # L'identité du fournisseur vient uniquement de res.partner —
        # aucune copie de nom/adresse sur l'évaluation elle-même.
        self.assertEqual(evaluation.partner_id.id, self.partner.id)
        self.assertEqual(evaluation.stakeholder_id.partner_id, self.partner)

    # ------------------------------------------------------------------
    # Calcul du score pondéré et du niveau de qualification
    # ------------------------------------------------------------------
    def test_04_global_score_weighted_average(self):
        evaluation = self._create_evaluation()
        self.env["smq.supplier.evaluation.line"].create(
            {"evaluation_id": evaluation.id, "criterion_id": self.criterion_a.id, "score": 4}
        )
        self.env["smq.supplier.evaluation.line"].create(
            {"evaluation_id": evaluation.id, "criterion_id": self.criterion_b.id, "score": 2}
        )
        # (4*3 + 2*1) / (3+1) = 14/4 = 3.5 -> arrondi à 4 (round-half-to-even
        # Python : round(3.5) == 4)
        self.assertEqual(evaluation.global_score, 4)

    def test_05_qualification_level_from_score(self):
        evaluation = self._create_evaluation()
        self.env["smq.supplier.evaluation.line"].create(
            {"evaluation_id": evaluation.id, "criterion_id": self.criterion_a.id, "score": 5}
        )
        self.assertEqual(
            evaluation.qualification_level_id,
            self.env.ref("smq_supplier.smq_supplier_qualification_approved"),
        )

    def test_06_no_qualification_level_without_lines(self):
        evaluation = self._create_evaluation()
        self.assertFalse(evaluation.qualification_level_id)

    def test_07_invalid_score_rejected(self):
        evaluation = self._create_evaluation()
        with self.assertRaises(ValidationError):
            self.env["smq.supplier.evaluation.line"].create(
                {"evaluation_id": evaluation.id, "criterion_id": self.criterion_a.id, "score": 9}
            )

    # ------------------------------------------------------------------
    # Actions (mgmtsystem.action — réutilisation pure)
    # ------------------------------------------------------------------
    def test_09_action_link(self):
        evaluation = self._create_evaluation()
        action = self.env["mgmtsystem.action"].create(
            {"name": "Action liée", "type_action": "correction"}
        )
        evaluation.action_ids = [(4, action.id)]
        self.assertIn(evaluation, action.supplier_evaluation_ids)
        self.assertEqual(action.supplier_evaluation_count, 1)
        self.assertEqual(evaluation.action_count, 1)

    def test_10_create_action_from_evaluation(self):
        evaluation = self._create_evaluation()
        evaluation.action_create_treatment_action()
        self.assertEqual(evaluation.action_count, 1)
        self.assertEqual(evaluation.action_ids.type_action, "correction")

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def test_11_validate_evaluation(self):
        evaluation = self._create_evaluation()
        evaluation.action_validate()
        self.assertEqual(evaluation.state, "done")

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------
    def test_12_employee_can_read(self):
        evaluation = self._create_evaluation()
        self.assertTrue(evaluation.with_user(self.employee).read(["reference"]))

    def test_13_employee_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env["smq.supplier.evaluation"].with_user(self.employee).create(
                {"partner_id": self.partner.id}
            )

    def test_14_writer_can_create_but_not_unlink(self):
        evaluation = self.env["smq.supplier.evaluation"].with_user(self.writer).create(
            {"partner_id": self.partner.id}
        )
        self.assertTrue(evaluation)
        with self.assertRaises(AccessError):
            evaluation.with_user(self.writer).unlink()

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def test_15_dashboard_tile_reflects_evaluation_count(self):
        tile = self.env.ref("smq_supplier.smq_dashboard_tile_supplier")
        before = self.env["smq.supplier.evaluation"].search_count([])
        self._create_evaluation()
        self.assertEqual(tile.count, before + 1)
        self.assertEqual(
            tile._get_action_xmlid(), "smq_supplier.action_smq_supplier_evaluation"
        )
