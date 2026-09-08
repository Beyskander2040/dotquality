from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestSmqProcessTemplate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")
        cls.employee = cls.env["res.users"].create(
            {
                "name": "Employé Template Test",
                "login": "smq_bpmn_template_employee_test",
                "email": "smq_bpmn_template_employee_test@example.com",
                "groups_id": [(6, 0, [cls.env.ref("smq_quality.group_smq_employee").id])],
            }
        )
        cls.writer = cls.env["res.users"].create(
            {
                "name": "Rédacteur Template Test",
                "login": "smq_bpmn_template_writer_test",
                "email": "smq_bpmn_template_writer_test@example.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("smq_quality.group_smq_writer").id,
                        ],
                    )
                ],
            }
        )
        cls.smq_admin = cls.env["res.users"].create(
            {
                "name": "Administrateur SMQ Template Test",
                "login": "smq_bpmn_template_admin_test",
                "email": "smq_bpmn_template_admin_test@example.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("smq_quality.group_smq_admin").id,
                        ],
                    )
                ],
            }
        )

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.smq_admin)

    def _new_template(self, name="Modèle test", **vals):
        values = {"name": name}
        values.update(vals)
        return self.env["smq.process.template"].create(values)

    def _add_template_step(self, template, code, name, step_type, **vals):
        values = {"template_id": template.id, "code": code, "name": name, "step_type": step_type}
        values.update(vals)
        return self.env["smq.process.template.step"].create(values)

    def _add_template_transition(self, template, source, target, **vals):
        values = {
            "template_id": template.id,
            "source_step_id": source.id,
            "target_step_id": target.id,
        }
        values.update(vals)
        return self.env["smq.process.template.step.transition"].create(values)

    def _linear_template(self, template):
        start = self._add_template_step(template, "START", "Début", "start")
        task = self._add_template_step(template, "TASK", "Traiter", "manual")
        end = self._add_template_step(template, "END", "Fin", "end")
        self._add_template_transition(template, start, task)
        self._add_template_transition(template, task, end)
        return start, task, end

    # ------------------------------------------------------------------
    # A. Sécurité — gestion des modèles réservée à l'Administrateur SMQ.
    # ------------------------------------------------------------------

    def test_a1_admin_can_create_template(self):
        template = self._new_template()
        self.assertTrue(template.id)

    def test_a2_writer_cannot_create_template(self):
        with self.assertRaises(AccessError):
            self.env["smq.process.template"].with_user(self.writer).create({"name": "Interdit"})

    def test_a3_writer_cannot_edit_template(self):
        template = self._new_template()
        with self.assertRaises(AccessError):
            template.with_user(self.writer).write({"name": "Modifié"})

    # ------------------------------------------------------------------
    # B. Intégrité de la description.
    # ------------------------------------------------------------------

    def test_b1_code_unique_per_template(self):
        template = self._new_template()
        self._add_template_step(template, "DUP", "Un", "manual")
        with self.assertRaises(Exception):
            self._add_template_step(template, "DUP", "Deux", "manual")
            self.env.flush_all()

    def test_b2_same_code_allowed_on_different_template(self):
        t1, t2 = self._new_template("T1"), self._new_template("T2")
        self._add_template_step(t1, "DUP", "Un", "manual")
        self._add_template_step(t2, "DUP", "Deux", "manual")
        self.env.flush_all()

    def test_b3_transition_across_templates_rejected(self):
        t1, t2 = self._new_template("T1"), self._new_template("T2")
        step_a = self._add_template_step(t1, "A", "A", "start")
        step_b = self._add_template_step(t2, "B", "B", "end")
        with self.assertRaises(ValidationError):
            self._add_template_transition(t1, step_a, step_b)

    def test_b4_missing_start_detected(self):
        template = self._new_template()
        self._add_template_step(template, "END", "Fin", "end")
        issues = template._get_description_issues()
        self.assertTrue(any("Début" in i for i in issues))

    def test_b5_unreachable_step_detected(self):
        template = self._new_template()
        start, task, end = self._linear_template(template)
        isolated = self._add_template_step(template, "ISOLATED", "Isolée", "manual")
        issues = template._get_description_issues()
        self.assertTrue(any("Isolée" in i for i in issues))

    # ------------------------------------------------------------------
    # C. Import — crée un Processus + une Version réels et indépendants.
    # ------------------------------------------------------------------

    def test_c1_writer_can_import(self):
        template = self._new_template()
        self._linear_template(template)
        process = template.with_user(self.writer).action_import("PROC-IMP1", "Importé 1")
        self.assertEqual(process.code, "PROC-IMP1")
        self.assertEqual(len(process.version_ids), 1)
        version = process.version_ids
        self.assertEqual(version.state, "draft")
        self.assertEqual(version.version, "1.0")
        self.assertEqual(len(version.step_ids), 3)
        self.assertEqual(len(version.transition_ids), 2)
        self.assertTrue(version.bpmn_xml)

    def test_c2_employee_cannot_import(self):
        template = self._new_template()
        self._linear_template(template)
        with self.assertRaises(UserError):
            template.with_user(self.employee).action_import("PROC-IMP2", "Importé 2")

    def test_c3_import_rejects_existing_process_code(self):
        template = self._new_template()
        self._linear_template(template)
        self.env["smq.process"].create({"code": "PROC-DUP", "name": "Déjà là"})
        with self.assertRaises(UserError):
            template.action_import("PROC-DUP", "Nouveau")

    def test_c4_import_rejects_invalid_template(self):
        template = self._new_template()
        self._add_template_step(template, "END", "Fin", "end")
        with self.assertRaises(ValidationError):
            template.action_import("PROC-IMP4", "Importé 4")

    def test_c5_two_imports_are_fully_independent(self):
        template = self._new_template()
        self._linear_template(template)
        process_a = template.action_import("PROC-IMP5A", "A")
        process_b = template.action_import("PROC-IMP5B", "B")
        self.assertFalse(set(process_a.version_ids.step_ids.ids) & set(process_b.version_ids.step_ids.ids))

    def test_c6_imported_step_documentation_link_readable(self):
        # Vérifie que le diagramme importé est bien auto-cohérent avec le
        # tableau d'activités (mêmes id que ceux calculés par
        # smq.process.step._compute_documentation_links).
        template = self._new_template()
        start, task, end = self._linear_template(template)
        process = template.action_import("PROC-IMP6", "Importé 6")
        version = process.version_ids
        imported_task = version.step_ids.filtered(lambda s: s.code == "TASK")
        self.assertIn(f"Step_{imported_task.id}", version.bpmn_xml)

    def test_c7_import_wizard_opens_the_imported_version_directly(self):
        # Régression : ouvrir la fiche du processus (et non de la version)
        # après import donnait l'impression que rien n'avait été importé —
        # les activités/le diagramme ne sont visibles que sur la version.
        template = self._new_template()
        self._linear_template(template)
        wizard = self.env["smq.process.template.import.wizard"].with_user(self.writer).create(
            {"template_id": template.id, "process_code": "PROC-IMP7", "process_name": "Importé 7"}
        )
        action = wizard.action_confirm()
        self.assertEqual(action["res_model"], "smq.process.version")
        version = self.env["smq.process.version"].browse(action["res_id"])
        self.assertEqual(len(version.step_ids), 3)
        self.assertTrue(version.bpmn_xml)

    # ------------------------------------------------------------------
    # D. Enregistrer une version comme modèle.
    # ------------------------------------------------------------------

    def test_d1_admin_can_save_version_as_template(self):
        process = self.env["smq.process"].create({"code": "PROC-SAT1", "name": "SAT1"})
        version = self.env["smq.process.version"].create({"process_id": process.id, "version": "1.0"})
        Step = self.env["smq.process.step"]
        start = Step.create({"process_version_id": version.id, "code": "START", "name": "Début", "step_type": "start"})
        end = Step.create({"process_version_id": version.id, "code": "END", "name": "Fin", "step_type": "end"})
        self.env["smq.process.step.transition"].create(
            {"process_version_id": version.id, "source_step_id": start.id, "target_step_id": end.id}
        )
        wizard = self.env["smq.process.version.save.as.template.wizard"].create(
            {"version_id": version.id, "template_name": "Nouveau modèle"}
        )
        action = wizard.action_confirm()
        template = self.env["smq.process.template"].browse(action["res_id"])
        self.assertEqual(len(template.template_step_ids), 2)
        self.assertEqual(len(template.template_transition_ids), 1)

    def test_d2_writer_cannot_save_as_template(self):
        process = self.env["smq.process"].create({"code": "PROC-SAT2", "name": "SAT2"})
        version = self.env["smq.process.version"].create({"process_id": process.id, "version": "1.0"})
        with self.assertRaises(AccessError):
            self.env["smq.process.version.save.as.template.wizard"].with_user(self.writer).create(
                {"version_id": version.id, "template_name": "Interdit"}
            )

    def test_d3_version_without_steps_cannot_be_saved(self):
        process = self.env["smq.process"].create({"code": "PROC-SAT3", "name": "SAT3"})
        version = self.env["smq.process.version"].create({"process_id": process.id, "version": "1.0"})
        wizard = self.env["smq.process.version.save.as.template.wizard"].create(
            {"version_id": version.id, "template_name": "Vide"}
        )
        with self.assertRaises(ValidationError):
            wizard.action_confirm()

    # ------------------------------------------------------------------
    # E. Modèle pré-chargé (données de démonstration du module).
    # ------------------------------------------------------------------

    def test_e1_seeded_complaint_template_is_importable(self):
        template = self.env.ref("smq_bpmn.smq_process_template_complaint")
        self.assertEqual(len(template.template_step_ids), 8)
        process = template.with_user(self.writer).action_import("PROC-SEED1", "Depuis modèle")
        self.assertTrue(process.version_ids.bpmn_xml)
        self.assertFalse(template._get_description_issues())
