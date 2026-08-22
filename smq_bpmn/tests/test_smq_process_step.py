import xml.etree.ElementTree as ET

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

_BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
_BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"


def _tags(root, local_name, ns=_BPMN_NS):
    return root.findall(f".//{{{ns}}}{local_name}")


class TestSmqProcessStep(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")
        cls.employee = cls.env["res.users"].create(
            {
                "name": "Employé Step Test",
                "login": "smq_bpmn_step_employee_test",
                "email": "smq_bpmn_step_employee_test@example.com",
                "groups_id": [(6, 0, [cls.env.ref("smq_quality.group_smq_employee").id])],
            }
        )
        cls.writer = cls.env["res.users"].create(
            {
                "name": "Rédacteur Step Test",
                "login": "smq_bpmn_step_writer_test",
                "email": "smq_bpmn_step_writer_test@example.com",
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
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Responsable Qualité Step Test",
                "login": "smq_bpmn_step_manager_test",
                "email": "smq_bpmn_step_manager_test@example.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("smq_quality.group_smq_quality_manager").id,
                        ],
                    )
                ],
            }
        )
        cls.process = cls.env["smq.process"].with_user(cls.admin).create(
            {"code": "PROC-STEP-TEST", "name": "Processus test description structurée"}
        )

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.admin)

    def _new_version(self, version="V1", process=None):
        process = process or self.process
        return self.env["smq.process.version"].create(
            {"process_id": process.id, "version": version}
        )

    def _add_step(self, version, code, name, step_type, **vals):
        values = {
            "process_version_id": version.id,
            "code": code,
            "name": name,
            "step_type": step_type,
        }
        values.update(vals)
        return self.env["smq.process.step"].create(values)

    def _add_transition(self, version, source, target, **vals):
        values = {
            "process_version_id": version.id,
            "source_step_id": source.id,
            "target_step_id": target.id,
        }
        values.update(vals)
        return self.env["smq.process.step.transition"].create(values)

    def _linear_description(self, version):
        """Début -> Réception -> Vérifier -> Fin (exemple §3 simplifié)."""
        start = self._add_step(version, "START", "Début", "start")
        receive = self._add_step(version, "RECEIVE", "Réception de la demande", "manual")
        verify = self._add_step(version, "VERIFY", "Vérifier la conformité", "manual")
        end = self._add_step(version, "END", "Fin", "end")
        self._add_transition(version, start, receive)
        self._add_transition(version, receive, verify)
        self._add_transition(version, verify, end)
        return start, receive, verify, end

    # ------------------------------------------------------------------
    # A. Modèle smq.process.step
    # ------------------------------------------------------------------

    def test_a1_create_step(self):
        version = self._new_version("VA1")
        step = self._add_step(version, "S1", "Étape 1", "manual")
        self.assertTrue(step)

    def test_a2_code_required(self):
        version = self._new_version("VA2")
        with self.assertRaises(Exception):
            self.env["smq.process.step"].create(
                {"process_version_id": version.id, "name": "Sans code", "step_type": "manual"}
            )

    def test_a3_code_unique_per_version(self):
        version = self._new_version("VA3")
        self._add_step(version, "DUP", "Première", "manual")
        with self.assertRaises(Exception):
            self._add_step(version, "DUP", "Deuxième", "manual")
            self.env.flush_all()

    def test_a4_same_code_allowed_on_different_version(self):
        v1 = self._new_version("VA4A")
        v2 = self._new_version("VA4B")
        self._add_step(v1, "SHARED", "Étape", "manual")
        self._add_step(v2, "SHARED", "Étape", "manual")
        self.env.flush_all()

    def test_a5_invalid_type_rejected(self):
        version = self._new_version("VA5")
        with self.assertRaises(Exception):
            self.env["smq.process.step"].create(
                {
                    "process_version_id": version.id,
                    "code": "S5",
                    "name": "Type invalide",
                    "step_type": "not_a_real_type",
                }
            )

    def test_a6_step_appears_in_version_relation(self):
        version = self._new_version("VA6")
        step = self._add_step(version, "S6", "Étape 6", "manual")
        self.assertIn(step, version.step_ids)

    # ------------------------------------------------------------------
    # B. Transitions
    # ------------------------------------------------------------------

    def test_b1_simple_transition_a_to_b(self):
        version = self._new_version("VB1")
        a = self._add_step(version, "A", "A", "manual")
        b = self._add_step(version, "B", "B", "manual")
        transition = self._add_transition(version, a, b)
        self.assertEqual(transition.source_step_id, a)
        self.assertEqual(transition.target_step_id, b)

    def test_b2_branching_a_to_b_and_c(self):
        version = self._new_version("VB2")
        a = self._add_step(version, "A", "A", "gateway")
        b = self._add_step(version, "B", "B", "manual")
        c = self._add_step(version, "C", "C", "manual")
        self._add_transition(version, a, b, condition="conforme")
        self._add_transition(version, a, c, condition="non conforme")
        self.assertEqual(len(version.transition_ids), 2)

    def test_b3_merge_b_and_c_into_d(self):
        version = self._new_version("VB3")
        b = self._add_step(version, "B", "B", "manual")
        c = self._add_step(version, "C", "C", "manual")
        d = self._add_step(version, "D", "D", "manual")
        self._add_transition(version, b, d)
        self._add_transition(version, c, d)
        incoming_d = version.transition_ids.filtered(lambda t: t.target_step_id == d)
        self.assertEqual(len(incoming_d), 2)

    def test_b4_simple_loop_allowed(self):
        version = self._new_version("VB4")
        a = self._add_step(version, "A", "A", "manual")
        gw = self._add_step(version, "GW", "Gateway", "gateway")
        b = self._add_step(version, "B", "B", "manual")
        self._add_transition(version, a, gw)
        self._add_transition(version, gw, b)
        self._add_transition(version, gw, a, condition="retour")  # boucle B... -> A
        self.assertEqual(len(version.transition_ids), 3)

    def test_b5_self_loop_forbidden(self):
        version = self._new_version("VB5")
        a = self._add_step(version, "A", "A", "manual")
        with self.assertRaises(ValidationError):
            self._add_transition(version, a, a)

    def test_b6_cross_version_transition_forbidden(self):
        v1 = self._new_version("VB6A")
        v2 = self._new_version("VB6B")
        a = self._add_step(v1, "A", "A", "manual")
        b = self._add_step(v2, "B", "B", "manual")
        with self.assertRaises(ValidationError):
            self.env["smq.process.step.transition"].create(
                {"process_version_id": v1.id, "source_step_id": a.id, "target_step_id": b.id}
            )

    def test_b7_locked_outside_draft(self):
        version = self._new_version("VB7", process=self.process)
        start, receive, verify, end = self._linear_description(version)
        version.action_submit_review()
        with self.assertRaises(ValidationError):
            self._add_step(version, "NEW", "Nouvelle étape", "manual")
        with self.assertRaises(ValidationError):
            start.write({"name": "Renommée"})
        with self.assertRaises(ValidationError):
            version.transition_ids[0].unlink()

    # ------------------------------------------------------------------
    # C. Validation (§13)
    # ------------------------------------------------------------------

    def test_c1_no_steps_invalid(self):
        version = self._new_version("VC1")
        with self.assertRaises(UserError):
            version.action_validate_process_description()

    def test_c2_no_start_invalid(self):
        version = self._new_version("VC2")
        self._add_step(version, "A", "A", "manual")
        self._add_step(version, "END", "Fin", "end")
        with self.assertRaises(UserError):
            version.action_validate_process_description()

    def test_c3_multiple_starts_invalid(self):
        version = self._new_version("VC3")
        self._add_step(version, "S1", "Début 1", "start")
        self._add_step(version, "S2", "Début 2", "start")
        self._add_step(version, "END", "Fin", "end")
        with self.assertRaises(UserError):
            version.action_validate_process_description()

    def test_c4_no_end_invalid(self):
        version = self._new_version("VC4")
        self._add_step(version, "START", "Début", "start")
        self._add_step(version, "A", "A", "manual")
        with self.assertRaises(UserError):
            version.action_validate_process_description()

    def test_c5_isolated_step_invalid(self):
        version = self._new_version("VC5")
        start, receive, verify, end = self._linear_description(version)
        self._add_step(version, "ISOLATED", "Étape isolée", "manual")
        with self.assertRaises(UserError):
            version.action_validate_process_description()

    def test_c6_valid_description_passes(self):
        version = self._new_version("VC6")
        self._linear_description(version)
        result = version.action_validate_process_description()
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "success")

    def test_c7_branching_and_merge_description_valid(self):
        version = self._new_version("VC7")
        start = self._add_step(version, "START", "Début", "start")
        gw = self._add_step(version, "GW", "Conforme ?", "gateway")
        ok = self._add_step(version, "OK", "Valider", "approval")
        fix = self._add_step(version, "FIX", "Corriger", "manual")
        end = self._add_step(version, "END", "Fin", "end")
        self._add_transition(version, start, gw)
        self._add_transition(version, gw, ok, condition="conforme")
        self._add_transition(version, gw, fix, condition="non conforme")
        self._add_transition(version, fix, gw)  # boucle vers la passerelle
        self._add_transition(version, ok, end)
        version.action_validate_process_description()  # ne doit pas lever

    # ------------------------------------------------------------------
    # D. Génération BPMN (§14-21)
    # ------------------------------------------------------------------

    def test_d1_generate_produces_well_formed_xml(self):
        version = self._new_version("VD1")
        self._linear_description(version)
        version.action_generate_bpmn_from_description()
        ET.fromstring(version.bpmn_xml)  # lève si mal formé

    def test_d2_process_element_present(self):
        version = self._new_version("VD2")
        self._linear_description(version)
        version.action_generate_bpmn_from_description()
        root = ET.fromstring(version.bpmn_xml)
        self.assertEqual(len(_tags(root, "process")), 1)

    def test_d3_start_and_end_present(self):
        version = self._new_version("VD3")
        self._linear_description(version)
        version.action_generate_bpmn_from_description()
        root = ET.fromstring(version.bpmn_xml)
        self.assertEqual(len(_tags(root, "startEvent")), 1)
        self.assertEqual(len(_tags(root, "endEvent")), 1)

    def test_d4_tasks_present_with_correct_bpmn_tags(self):
        version = self._new_version("VD4")
        start = self._add_step(version, "START", "Début", "start")
        manual = self._add_step(version, "M", "Manuel", "manual")
        document = self._add_step(version, "DOC", "Document", "document")
        approval = self._add_step(version, "APP", "Approbation", "approval")
        notif = self._add_step(version, "NOTIF", "Notification", "notification")
        end = self._add_step(version, "END", "Fin", "end")
        for a, b in [(start, manual), (manual, document), (document, approval), (approval, notif), (notif, end)]:
            self._add_transition(version, a, b)
        version.action_generate_bpmn_from_description()
        root = ET.fromstring(version.bpmn_xml)
        self.assertEqual(len(_tags(root, "userTask")), 3)  # manual + document + approval
        self.assertEqual(len(_tags(root, "serviceTask")), 1)  # notification

    def test_d5_gateway_present(self):
        version = self._new_version("VD5")
        self._add_step(version, "START", "Début", "start")
        gw = self._add_step(version, "GW", "Décision", "gateway")
        end = self._add_step(version, "END", "Fin", "end")
        self._add_transition(version, version.step_ids.filtered(lambda s: s.code == "START"), gw)
        self._add_transition(version, gw, end)
        version.action_generate_bpmn_from_description()
        root = ET.fromstring(version.bpmn_xml)
        self.assertEqual(len(_tags(root, "exclusiveGateway")), 1)

    def test_d6_sequence_flows_present(self):
        version = self._new_version("VD6")
        self._linear_description(version)
        version.action_generate_bpmn_from_description()
        root = ET.fromstring(version.bpmn_xml)
        self.assertEqual(len(_tags(root, "sequenceFlow")), 3)

    def test_d7_bpmndi_present(self):
        version = self._new_version("VD7")
        self._linear_description(version)
        version.action_generate_bpmn_from_description()
        root = ET.fromstring(version.bpmn_xml)
        self.assertEqual(len(_tags(root, "BPMNDiagram", _BPMNDI_NS)), 1)
        self.assertEqual(len(_tags(root, "BPMNPlane", _BPMNDI_NS)), 1)
        self.assertEqual(len(_tags(root, "BPMNShape", _BPMNDI_NS)), 4)
        self.assertEqual(len(_tags(root, "BPMNEdge", _BPMNDI_NS)), 3)

    def test_d8_checksum_recomputed_after_generation(self):
        version = self._new_version("VD8")
        self._linear_description(version)
        self.assertFalse(version.bpmn_checksum)
        version.action_generate_bpmn_from_description()
        self.assertTrue(version.bpmn_checksum)

    def test_d9_returns_true_not_a_client_action(self):
        # Bug constaté en usage réel : renvoyer une action
        # ir.actions.client/display_notification depuis ce bouton empêche le
        # rechargement automatique de l'enregistrement (vérifié dans le code
        # source réel du client web) — le formulaire continuait alors
        # d'afficher l'ancien diagramme (vide) malgré un bpmn_xml pourtant
        # bien généré et enregistré en base. Corrigé en renvoyant True, ce
        # qui déclenche le rechargement standard d'Odoo après un bouton objet.
        version = self._new_version("VD9")
        self._linear_description(version)
        result = version.action_generate_bpmn_from_description()
        self.assertIs(result, True)

    # ------------------------------------------------------------------
    # E. Déterminisme (§28 — "très important")
    # ------------------------------------------------------------------

    def test_e1_generation_is_deterministic_across_calls(self):
        from odoo.addons.smq_bpmn.models.smq_bpmn_generator import generate_bpmn_xml

        version = self._new_version("VE1")
        self._linear_description(version)
        xml1 = generate_bpmn_xml(version)
        xml2 = generate_bpmn_xml(version)
        self.assertEqual(xml1, xml2)

    def test_e2_element_ids_based_on_stable_record_id_not_name(self):
        from odoo.addons.smq_bpmn.models.smq_bpmn_generator import generate_bpmn_xml

        version = self._new_version("VE2")
        start, receive, verify, end = self._linear_description(version)
        xml1 = generate_bpmn_xml(version)
        receive.write({"name": "Nom complètement différent"})
        xml2 = generate_bpmn_xml(version)
        # Les IDs (Step_<id>) sont inchangés malgré le renommage — seul
        # l'attribut "name" de l'élément change.
        self.assertIn(f"Step_{receive.id}", xml1)
        self.assertIn(f"Step_{receive.id}", xml2)

    def test_e3_ids_stable_after_reordering_sequence(self):
        from odoo.addons.smq_bpmn.models.smq_bpmn_generator import generate_bpmn_xml

        version = self._new_version("VE3")
        start, receive, verify, end = self._linear_description(version)
        xml_before = generate_bpmn_xml(version)
        receive.write({"sequence": 999})  # réordonnancement pur
        xml_after = generate_bpmn_xml(version)
        self.assertIn(f"Step_{receive.id}", xml_before)
        self.assertIn(f"Step_{receive.id}", xml_after)

    # ------------------------------------------------------------------
    # F. Documentation (§18)
    # ------------------------------------------------------------------

    def test_f1_description_becomes_bpmn_documentation(self):
        version = self._new_version("VF1")
        start, receive, verify, end = self._linear_description(version)
        receive.write({"description": "Réception via le portail client."})
        version.action_generate_bpmn_from_description()
        self.assertIn("Réception via le portail client.", version.bpmn_xml)
        root = ET.fromstring(version.bpmn_xml)
        self.assertEqual(len(_tags(root, "documentation")), 1)

    def test_f2_no_empty_documentation_when_description_absent(self):
        version = self._new_version("VF2")
        self._linear_description(version)  # aucune description sur aucune étape
        version.action_generate_bpmn_from_description()
        root = ET.fromstring(version.bpmn_xml)
        self.assertEqual(len(_tags(root, "documentation")), 0)

    # ------------------------------------------------------------------
    # G. Conditions (§19)
    # ------------------------------------------------------------------

    def test_g1_condition_becomes_sequence_flow_label(self):
        version = self._new_version("VG1")
        start = self._add_step(version, "START", "Début", "start")
        gw = self._add_step(version, "GW", "Conforme ?", "gateway")
        ok = self._add_step(version, "OK", "Valider", "approval")
        end = self._add_step(version, "END", "Fin", "end")
        self._add_transition(version, start, gw)
        self._add_transition(version, gw, ok, condition="conforme")
        self._add_transition(version, ok, end)
        version.action_generate_bpmn_from_description()
        root = ET.fromstring(version.bpmn_xml)
        flows = _tags(root, "sequenceFlow")
        self.assertTrue(any(f.get("name") == "conforme" for f in flows))

    def test_g2_no_condition_no_name_attribute(self):
        version = self._new_version("VG2")
        self._linear_description(version)
        version.action_generate_bpmn_from_description()
        root = ET.fromstring(version.bpmn_xml)
        flows = _tags(root, "sequenceFlow")
        self.assertTrue(all(f.get("name") is None for f in flows))

    # ------------------------------------------------------------------
    # H. Workflow (§22, §26)
    # ------------------------------------------------------------------

    def test_h1_generate_blocked_outside_draft(self):
        version = self._new_version("VH1")
        self._linear_description(version)
        version.action_submit_review()
        with self.assertRaises(UserError):
            version.action_generate_bpmn_from_description()

    def test_h2_generate_allowed_in_draft(self):
        version = self._new_version("VH2")
        self._linear_description(version)
        version.action_generate_bpmn_from_description()
        self.assertTrue(version.bpmn_xml)

    def test_h3_generation_never_changes_state(self):
        version = self._new_version("VH3")
        self._linear_description(version)
        version.action_generate_bpmn_from_description()
        self.assertEqual(version.state, "draft")

    def test_h4_generate_requires_writer_group(self):
        version = self._new_version("VH4")
        self._linear_description(version)
        with self.assertRaises(UserError):
            version.with_user(self.employee).action_generate_bpmn_from_description()

    # ------------------------------------------------------------------
    # I. Protection des mappings existants (§23)
    # ------------------------------------------------------------------

    def test_i1_generation_refused_when_mappings_exist(self):
        version = self._new_version("VI1")
        self._linear_description(version)
        self.env["smq.bpmn.task.mapping"].create(
            {"process_version_id": version.id, "bpmn_element_id": "Task_existing"}
        )
        with self.assertRaises(ValidationError):
            version.action_generate_bpmn_from_description()

    def test_i2_generation_allowed_when_no_mappings(self):
        version = self._new_version("VI2")
        self._linear_description(version)
        self.assertFalse(version.mapping_ids)
        version.action_generate_bpmn_from_description()
        self.assertTrue(version.bpmn_xml)

    def test_i3_mappings_never_silently_deleted_by_generation_attempt(self):
        version = self._new_version("VI3")
        self._linear_description(version)
        mapping = self.env["smq.bpmn.task.mapping"].create(
            {"process_version_id": version.id, "bpmn_element_id": "Task_existing"}
        )
        with self.assertRaises(ValidationError):
            version.action_generate_bpmn_from_description()
        self.assertTrue(mapping.exists())

    # ------------------------------------------------------------------
    # J. Sécurité
    # ------------------------------------------------------------------

    def test_j1_viewer_cannot_create_step(self):
        version = self._new_version("VJ1")
        with self.assertRaises(Exception):
            self.env["smq.process.step"].with_user(self.employee).create(
                {"process_version_id": version.id, "code": "S1", "name": "S1", "step_type": "manual"}
            )

    def test_j2_editor_can_create_validate_and_generate(self):
        version = self.env["smq.process.version"].with_user(self.writer).create(
            {"process_id": self.process.id, "version": "VJ2"}
        )
        self._linear_description(version)
        version.with_user(self.writer).action_validate_process_description()
        version.with_user(self.writer).action_generate_bpmn_from_description()
        self.assertTrue(version.bpmn_xml)

    def test_j3_manager_can_also_create_and_generate(self):
        version = self.env["smq.process.version"].with_user(self.manager).create(
            {"process_id": self.process.id, "version": "VJ3"}
        )
        self._linear_description(version)
        version.with_user(self.manager).action_generate_bpmn_from_description()
        self.assertTrue(version.bpmn_xml)

    # ------------------------------------------------------------------
    # K. Clonage (extension LOT 11) — la description structurée appartient
    # à la version, comme le BPMN XML et les mappings.
    # ------------------------------------------------------------------

    def test_k1_new_version_clones_steps_and_transitions_independently(self):
        version = self._new_version("VK1")
        self._linear_description(version)
        action = version.with_user(self.writer).action_create_new_version()
        clone = self.env["smq.process.version"].browse(action["res_id"])
        self.assertEqual(len(clone.step_ids), len(version.step_ids))
        self.assertEqual(len(clone.transition_ids), len(version.transition_ids))
        self.assertFalse(set(clone.step_ids.ids) & set(version.step_ids.ids))

    def test_k2_editing_cloned_step_never_touches_original(self):
        version = self._new_version("VK2")
        start, receive, verify, end = self._linear_description(version)
        action = version.with_user(self.writer).action_create_new_version()
        clone = self.env["smq.process.version"].browse(action["res_id"])
        clone_receive = clone.step_ids.filtered(lambda s: s.code == "RECEIVE")
        clone_receive.write({"name": "Nom modifié sur le clone"})
        self.assertEqual(receive.name, "Réception de la demande")
        self.assertEqual(clone_receive.name, "Nom modifié sur le clone")
