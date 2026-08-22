from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

# LOT 11 : action_approve() exige désormais un <bpmn:process> identifiable
# (précondition §11) — le fixture doit donc envelopper la tâche dans un
# process, plus seulement déclarer le namespace comme au LOT 10.
_XML_TASK_A = (
    "<?xml version='1.0'?>"
    "<bpmn:definitions xmlns:bpmn='http://www.omg.org/spec/BPMN/20100524/MODEL'>"
    "<bpmn:process id='Process_1'>"
    "<bpmn:task id='Task_A' name='Créer document'/>"
    "</bpmn:process>"
    "</bpmn:definitions>"
)


class TestSmqBpmnTaskMapping(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")
        cls.employee = cls.env["res.users"].create(
            {
                "name": "Employé Mapping Test",
                "login": "smq_bpmn_mapping_employee_test",
                "email": "smq_bpmn_mapping_employee_test@example.com",
                "groups_id": [(6, 0, [cls.env.ref("smq_quality.group_smq_employee").id])],
            }
        )
        cls.writer = cls.env["res.users"].create(
            {
                "name": "Rédacteur Mapping Test",
                "login": "smq_bpmn_mapping_writer_test",
                "email": "smq_bpmn_mapping_writer_test@example.com",
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
                "name": "Responsable Qualité Mapping Test",
                "login": "smq_bpmn_mapping_manager_test",
                "email": "smq_bpmn_mapping_manager_test@example.com",
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
            {"code": "PROC-MAPPING-TEST", "name": "Processus test mapping"}
        )
        cls.model_smq_process = cls.env.ref("smq_quality.model_smq_process")
        cls.model_smq_process_version = cls.env.ref("smq_bpmn.model_smq_process_version")

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.admin)

    def _new_version(self, version="V1", **vals):
        values = {"process_id": self.process.id, "version": version}
        values.update(vals)
        return self.env["smq.process.version"].create(values)

    def _new_mapping(self, version=None, bpmn_element_id="Task_A", **vals):
        version = version or self._new_version()
        values = {"process_version_id": version.id, "bpmn_element_id": bpmn_element_id}
        values.update(vals)
        return self.env["smq.bpmn.task.mapping"].create(values)

    # ------------------------------------------------------------------
    # A. Création et unicité
    # ------------------------------------------------------------------

    def test_a1_create_minimal_mapping(self):
        mapping = self._new_mapping()
        self.assertTrue(mapping.active)

    def test_a2_mapping_appears_in_version_relation(self):
        version = self._new_version("VA2")
        mapping = self._new_mapping(version, "Task_A2")
        self.assertIn(mapping, version.mapping_ids)

    def test_a3_duplicate_element_id_same_version_rejected(self):
        version = self._new_version("VA3")
        self._new_mapping(version, "Task_DUP")
        with self.assertRaises(Exception):
            self._new_mapping(version, "Task_DUP")
            self.env.flush_all()

    def test_a4_same_element_id_different_versions_allowed(self):
        v1 = self._new_version("VA4A")
        v2 = self._new_version("VA4B")
        self._new_mapping(v1, "Task_SHARED")
        self._new_mapping(v2, "Task_SHARED")
        self.env.flush_all()

    def test_a5_active_can_be_disabled(self):
        mapping = self._new_mapping(active=False)
        self.assertFalse(mapping.active)

    # ------------------------------------------------------------------
    # B. Verrouillage — suit l'état de la version (§25-26), aucune exception
    # pour Manager.
    # ------------------------------------------------------------------

    def test_b1_create_on_draft_version_allowed(self):
        version = self._new_version("VB1")
        mapping = self._new_mapping(version, "Task_B1")
        self.assertTrue(mapping)

    def test_b2_create_on_approved_version_refused(self):
        version = self._new_version("VB2", bpmn_xml=_XML_TASK_A)
        version.action_submit_review()
        version.action_approve()
        with self.assertRaises(ValidationError):
            self._new_mapping(version, "Task_B2")

    def test_b3_write_on_approved_version_refused(self):
        version = self._new_version("VB3")
        # Élément "Task_A" : doit correspondre à _XML_TASK_A, sous peine
        # d'être détecté "orphelin" et de bloquer action_approve() pour une
        # raison différente de celle testée ici (le verrouillage).
        mapping = self._new_mapping(version, "Task_A")
        version.write({"bpmn_xml": _XML_TASK_A})
        version.action_submit_review()
        version.action_approve()
        with self.assertRaises(ValidationError):
            mapping.write({"task_type": "document"})

    def test_b4_unlink_on_approved_refused_but_draft_allowed(self):
        version = self._new_version("VB4")
        mapping = self._new_mapping(version, "Task_B4")
        mapping.unlink()  # draft : autorisé

        version2 = self._new_version("VB4-bis", bpmn_xml=_XML_TASK_A)
        mapping2 = self._new_mapping(version2, "Task_A")
        version2.action_submit_review()
        version2.action_approve()
        with self.assertRaises(ValidationError):
            mapping2.unlink()

    def test_b5_manager_cannot_bypass_lock_on_approved(self):
        # §26 : même Manager ne peut pas modifier le mapping d'une version
        # approuvée.
        version = self._new_version("VB5", bpmn_xml=_XML_TASK_A)
        mapping = self._new_mapping(version, "Task_A")
        version.action_submit_review()
        version.action_approve()
        with self.assertRaises(ValidationError):
            mapping.with_user(self.manager).write({"task_type": "approval"})

    # ------------------------------------------------------------------
    # C. Sécurité Viewer / Editor / Manager
    # ------------------------------------------------------------------

    def test_c1_viewer_can_read(self):
        mapping = self._new_mapping()
        mapping.with_user(self.employee).read(["bpmn_element_id"])

    def test_c2_viewer_cannot_create(self):
        version = self._new_version("VC2")
        with self.assertRaises(Exception):
            self.env["smq.bpmn.task.mapping"].with_user(self.employee).create(
                {"process_version_id": version.id, "bpmn_element_id": "Task_C2"}
            )

    def test_c3_editor_can_create_on_draft(self):
        version = self._new_version("VC3")
        mapping = self.env["smq.bpmn.task.mapping"].with_user(self.writer).create(
            {"process_version_id": version.id, "bpmn_element_id": "Task_C3"}
        )
        self.assertTrue(mapping)

    def test_c4_manager_can_create_on_draft(self):
        version = self._new_version("VC4")
        mapping = self.env["smq.bpmn.task.mapping"].with_user(self.manager).create(
            {"process_version_id": version.id, "bpmn_element_id": "Task_C4"}
        )
        self.assertTrue(mapping)

    # ------------------------------------------------------------------
    # D. Validation modèle / méthode / action (§27-29)
    # ------------------------------------------------------------------

    def test_d1_valid_model_accepted(self):
        mapping = self._new_mapping(odoo_model_id=self.model_smq_process.id)
        self.assertEqual(mapping.odoo_model, "smq.process")

    def test_d2_valid_model_and_method_accepted(self):
        mapping = self._new_mapping(
            odoo_model_id=self.model_smq_process_version.id, odoo_method="action_submit_review"
        )
        self.assertEqual(mapping.odoo_method, "action_submit_review")

    def test_d3_invalid_method_rejected(self):
        with self.assertRaises(ValidationError):
            self._new_mapping(
                odoo_model_id=self.model_smq_process.id,
                odoo_method="this_method_does_not_exist",
            )

    def test_d4_method_without_model_rejected(self):
        with self.assertRaises(ValidationError):
            self._new_mapping(odoo_method="action_submit_review")

    def test_d5_method_never_executed(self):
        # La validation utilise getattr/callable uniquement — jamais
        # d'appel réel. Si action_approve() avait été exécutée, la version
        # source ne serait plus en draft.
        version = self._new_version("VD5")
        self._new_mapping(
            version, "Task_D5",
            odoo_model_id=self.model_smq_process_version.id,
            odoo_method="action_approve",
        )
        self.assertEqual(version.state, "draft")

    def test_d6_action_compatible_with_model_accepted(self):
        action = self.env.ref("smq_bpmn.action_smq_process_version")
        self._new_mapping(
            odoo_model_id=self.model_smq_process_version.id, odoo_action_id=action.id
        )

    def test_d7_action_incompatible_with_model_rejected(self):
        process_action = self.env.ref("smq_quality.action_smq_process")
        with self.assertRaises(ValidationError):
            self._new_mapping(
                odoo_model_id=self.model_smq_process_version.id,
                odoo_action_id=process_action.id,
            )

    def test_d8_writer_can_set_model_without_technical_group(self):
        # ir.model est réservé à base.group_system : un Editor SMQ ordinaire
        # (sans ce groupe technique) doit néanmoins pouvoir configurer
        # odoo_model_id sans AccessError — vérifie que les lectures
        # internes (compute + contraintes) utilisent bien sudo().
        self.assertFalse(self.writer.has_group("base.group_system"))
        version = self._new_version("VD8")
        mapping = self.env["smq.bpmn.task.mapping"].with_user(self.writer).create(
            {
                "process_version_id": version.id,
                "bpmn_element_id": "Task_D8",
                "odoo_model_id": self.model_smq_process.id,
                "odoo_method": "action_view_process_versions",
            }
        )
        self.assertEqual(mapping.with_user(self.writer).odoo_model, "smq.process")

    def test_d9_writer_can_use_reference_data_lookups(self):
        self.assertFalse(self.writer.has_group("base.group_system"))
        Mapping = self.env["smq.bpmn.task.mapping"].with_user(self.writer)
        models = Mapping.get_available_models()
        self.assertTrue(any(m["model"] == "smq.process" for m in models))
        actions = Mapping.get_available_actions()
        self.assertIsInstance(actions, list)

    # ------------------------------------------------------------------
    # E. Mappings orphelins (§39)
    # ------------------------------------------------------------------

    def test_e1_not_orphaned_when_element_present_in_xml(self):
        version = self._new_version("VE1", bpmn_xml=_XML_TASK_A)
        mapping = self._new_mapping(version, "Task_A")
        self.assertFalse(mapping.is_orphaned)

    def test_e2_orphaned_when_element_missing_from_xml(self):
        version = self._new_version("VE2", bpmn_xml=_XML_TASK_A)
        mapping = self._new_mapping(version, "Task_REMOVED")
        self.assertTrue(mapping.is_orphaned)

    def test_e3_orphaned_becomes_true_after_bpmn_xml_changes(self):
        version = self._new_version("VE3", bpmn_xml=_XML_TASK_A)
        mapping = self._new_mapping(version, "Task_A")
        self.assertFalse(mapping.is_orphaned)
        version.write({"bpmn_xml": "<?xml version='1.0'?><bpmn:definitions/>"})
        self.assertTrue(mapping.is_orphaned)

    def test_e4_get_mapping_for_element_not_found(self):
        version = self._new_version("VE4")
        result = self.env["smq.bpmn.task.mapping"].get_mapping_for_element(version.id, "Task_X")
        self.assertFalse(result["found"])

    def test_e5_get_mapping_for_element_found_with_orphan_flag(self):
        version = self._new_version("VE5", bpmn_xml=_XML_TASK_A)
        mapping = self._new_mapping(version, "Task_REMOVED", task_type="document")
        result = self.env["smq.bpmn.task.mapping"].get_mapping_for_element(
            version.id, "Task_REMOVED"
        )
        self.assertTrue(result["found"])
        self.assertEqual(result["id"], mapping.id)
        self.assertTrue(result["is_orphaned"])

    # ------------------------------------------------------------------
    # F. Sauvegarde combinée (§37-38)
    # ------------------------------------------------------------------

    def test_f1_combined_save_creates_mapping_and_updates_xml(self):
        version = self._new_version("VF1")
        version.action_save_bpmn_and_mappings(
            _XML_TASK_A,
            [{"bpmn_element_id": "Task_A", "task_type": "document",
              "odoo_model_id": self.model_smq_process.id}],
        )
        self.assertEqual(version.bpmn_xml, _XML_TASK_A)
        mapping = version.mapping_ids
        self.assertEqual(len(mapping), 1)
        self.assertEqual(mapping.task_type, "document")

    def test_f2_combined_save_updates_existing_mapping(self):
        version = self._new_version("VF2", bpmn_xml=_XML_TASK_A)
        mapping = self._new_mapping(version, "Task_A", task_type="document")
        version.action_save_bpmn_and_mappings(
            _XML_TASK_A, [{"id": mapping.id, "task_type": "approval"}]
        )
        self.assertEqual(mapping.task_type, "approval")
        self.assertEqual(len(version.mapping_ids), 1)

    def test_f3_combined_save_rolls_back_atomically_on_mapping_error(self):
        version = self._new_version("VF3", bpmn_xml="<xml>original</xml>")
        original_checksum = version.bpmn_checksum
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                version.action_save_bpmn_and_mappings(
                    "<xml>updated</xml>",
                    [{"bpmn_element_id": "Task_X", "odoo_model_id": self.model_smq_process.id,
                      "odoo_method": "this_method_does_not_exist"}],
                )
        version.invalidate_recordset()
        self.assertEqual(version.bpmn_xml, "<xml>original</xml>")
        self.assertEqual(version.bpmn_checksum, original_checksum)
        self.assertFalse(
            self.env["smq.bpmn.task.mapping"].search([("bpmn_element_id", "=", "Task_X")])
        )

    def test_f4_combined_save_refused_on_locked_version(self):
        version = self._new_version("VF4", bpmn_xml=_XML_TASK_A)
        version.action_submit_review()
        version.action_approve()
        with self.assertRaises(ValidationError):
            version.action_save_bpmn_and_mappings("<xml>hack</xml>", [])

    # ------------------------------------------------------------------
    # G. Contrôle de cohérence explicite (§40)
    # ------------------------------------------------------------------

    def test_g1_check_mappings_clean_returns_success_notification(self):
        version = self._new_version("VG1", bpmn_xml=_XML_TASK_A)
        self._new_mapping(version, "Task_A", task_type="document")
        result = version.action_check_mappings()
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "success")

    def test_g2_check_mappings_detects_orphan(self):
        version = self._new_version("VG2", bpmn_xml=_XML_TASK_A)
        self._new_mapping(version, "Task_MISSING")
        with self.assertRaises(UserError):
            version.action_check_mappings()

    def test_g3_check_mappings_detects_business_config_on_non_mappable_type(self):
        version = self._new_version("VG3", bpmn_xml=_XML_TASK_A)
        self._new_mapping(
            version, "Task_A", element_type="start_event", task_type="document"
        )
        with self.assertRaises(UserError):
            version.action_check_mappings()
