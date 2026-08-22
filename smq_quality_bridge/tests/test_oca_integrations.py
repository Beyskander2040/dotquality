from odoo.tests.common import TransactionCase


class TestOcaIntegrations(TransactionCase):
    """Vérifie les intégrations OCA REUSE/EXTEND (pas de nouveau modèle) :
    Action Templates, typologie NC, lien NC/RH, Revue de direction,
    Compétences (hr_skills)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.quality_manager = cls.env.ref("base.user_admin")
        cls.process = cls.env["smq.process"].create({"code": "PR-OCA", "name": "Test"})
        cls.origin = cls.env.ref("mgmtsystem_nonconformity.nc_origin_process")

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.quality_manager)

    # ------------------------------------------------------------------
    # Action Templates (mgmtsystem_action_template) — REUSE pur.
    # ------------------------------------------------------------------
    def test_action_can_reference_existing_template(self):
        # Le pré-remplissage (nom/type/description/responsable/tags) est un
        # onchange OCA déclenché côté client (formulaire), pas testable via
        # un .create() serveur direct : on vérifie ici que la référence au
        # template — la partie persistée — fonctionne bien de bout en bout.
        template = self.env["mgmtsystem.action.template"].create(
            {"name": "Vérifier calibrage équipement", "type_action": "correction"}
        )
        action = self.env["mgmtsystem.action"].create(
            {
                "name": "Action test",
                "type_action": "correction",
                "template_id": template.id,
            }
        )
        self.assertEqual(action.template_id, template)

    def test_action_template_menu_targets_existing_oca_action(self):
        # Le menu SMQ doit pointer vers l'action OCA existante, pas une
        # action recréée.
        menu = self.env.ref("smq_quality_bridge.menu_smq_action_template")
        action = self.env.ref(
            "mgmtsystem_action_template.mgmtsystem_action_template_act_window"
        )
        self.assertEqual(menu.action.id, action.id)
        self.assertEqual(menu.action.res_model, "mgmtsystem.action.template")

    # ------------------------------------------------------------------
    # Typologie NC (mgmtsystem_nonconformity_type) — champ OCA existant.
    # ------------------------------------------------------------------
    def test_nonconformity_type_field_available_and_relabelled(self):
        nc = self.env["mgmtsystem.nonconformity"].create(
            {
                "name": "NC typologie",
                "description": "Test",
                "quality_process_id": self.process.id,
                "origin_ids": [(4, self.origin.id)],
                "nc_type": "supplier",
            }
        )
        self.assertEqual(nc.nc_type, "supplier")
        field_label = nc._fields["nc_type"].get_description(self.env)["string"]
        self.assertEqual(field_label, "Type")

    # ------------------------------------------------------------------
    # Lien NC / RH (mgmtsystem_nonconformity_hr) — champ OCA existant.
    # ------------------------------------------------------------------
    def test_nonconformity_department_field_available(self):
        department = self.env["hr.department"].create({"name": "Production test"})
        nc = self.env["mgmtsystem.nonconformity"].create(
            {
                "name": "NC département",
                "description": "Test",
                "quality_process_id": self.process.id,
                "origin_ids": [(4, self.origin.id)],
                "department_id": department.id,
            }
        )
        self.assertEqual(nc.department_id, department)

    # ------------------------------------------------------------------
    # Revue de direction (mgmtsystem_review) — moteur OCA bridgé, pas de
    # nouveau modèle smq.management.review.
    # ------------------------------------------------------------------
    def test_management_review_uses_oca_model_with_french_labels(self):
        review = self.env["mgmtsystem.review"].create(
            {"name": "Revue de direction — test", "date": "2026-06-01 09:00:00"}
        )
        self.assertTrue(review.reference)
        self.assertEqual(review.state, "open")
        state_label = dict(review._fields["state"].selection)["open"]
        self.assertEqual(state_label, "Ouverte")

    def test_management_review_line_can_reference_existing_nonconformity(self):
        nc = self.env["mgmtsystem.nonconformity"].create(
            {
                "name": "NC pour revue",
                "description": "Test",
                "quality_process_id": self.process.id,
                "origin_ids": [(4, self.origin.id)],
            }
        )
        review = self.env["mgmtsystem.review"].create({"name": "Revue", "date": "2026-06-01 09:00:00"})
        line = self.env["mgmtsystem.review.line"].create(
            {
                "review_id": review.id,
                "name": "Examen NC",
                "type": "nonconformity",
                "nonconformity_id": nc.id,
                "decision": "Clôturée, efficace.",
            }
        )
        self.assertIn(line, review.line_ids)
        self.assertEqual(line.nonconformity_id, nc)

    def test_management_review_menu_gated_to_quality_manager(self):
        menu = self.env.ref("smq_quality_bridge.menu_smq_management_review")
        self.assertIn(
            self.env.ref("smq_quality.group_smq_quality_manager"), menu.groups_id
        )

    # ------------------------------------------------------------------
    # Compétences (hr_skills) — lecture des données RH existantes, aucune
    # duplication.
    # ------------------------------------------------------------------
    def test_employee_skill_action_reads_existing_hr_data_without_duplication(self):
        employee = self.env["hr.employee"].create({"name": "Employé test"})
        skill_type = self.env["hr.skill.type"].create({"name": "Type compétence test"})
        skill = self.env["hr.skill"].create(
            {"name": "Compétence test", "skill_type_id": skill_type.id}
        )
        level = self.env["hr.skill.level"].create(
            {
                "name": "Niveau test",
                "skill_type_id": skill_type.id,
                "level_progress": 50,
            }
        )
        employee_skill = self.env["hr.employee.skill"].create(
            {
                "employee_id": employee.id,
                "skill_type_id": skill_type.id,
                "skill_id": skill.id,
                "skill_level_id": level.id,
            }
        )
        action = self.env.ref("smq_quality_bridge.action_smq_employee_skill")
        self.assertEqual(action.res_model, "hr.employee.skill")
        found = self.env["hr.employee.skill"].search([("id", "=", employee_skill.id)])
        self.assertEqual(found.employee_id, employee)
