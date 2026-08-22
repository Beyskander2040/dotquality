import hashlib

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

# LOT 11 : les préconditions d'approbation (§11) exigent un BPMN XML bien
# formé ET un élément <bpmn:process> identifiable — les anciens fixtures
# LOT 8 ("<bpmn:definitions>V1</bpmn:definitions>", sans namespace ni
# process) ne suffisent donc plus pour atteindre "approved"/"effective".
_VALID_XML = (
    "<?xml version='1.0'?>"
    "<bpmn:definitions xmlns:bpmn='http://www.omg.org/spec/BPMN/20100524/MODEL'>"
    "<bpmn:process id='Process_1'><bpmn:task id='Task_1'/></bpmn:process>"
    "</bpmn:definitions>"
)
_VALID_XML_V2 = (
    "<?xml version='1.0'?>"
    "<bpmn:definitions xmlns:bpmn='http://www.omg.org/spec/BPMN/20100524/MODEL'>"
    "<bpmn:process id='Process_1'>"
    "<bpmn:task id='Task_1'/><bpmn:task id='Task_2'/>"
    "</bpmn:process></bpmn:definitions>"
)
_XML_NO_PROCESS = (
    "<?xml version='1.0'?>"
    "<bpmn:definitions xmlns:bpmn='http://www.omg.org/spec/BPMN/20100524/MODEL'/>"
)
_XML_INVALID = "<bpmn:definitions><unclosed>"


class TestSmqProcessVersion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")

        cls.employee = cls.env["res.users"].create(
            {
                "name": "Employé BPMN Test",
                "login": "smq_bpmn_employee_test",
                "email": "smq_bpmn_employee_test@example.com",
                "groups_id": [
                    (6, 0, [cls.env.ref("smq_quality.group_smq_employee").id])
                ],
            }
        )
        # LOT 11 : "email" est nécessaire ici — message_post() (chatter,
        # §14) refuse d'envoyer un message dont l'auteur n'a pas d'adresse
        # e-mail configurée, ce que les transitions du workflow déclenchent
        # désormais pour de vrai (découvert en exécutant les tests).
        cls.writer = cls.env["res.users"].create(
            {
                "name": "Rédacteur BPMN Test",
                "login": "smq_bpmn_writer_test",
                "email": "smq_bpmn_writer_test@example.com",
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
                "name": "Responsable Qualité BPMN Test",
                "login": "smq_bpmn_manager_test",
                "email": "smq_bpmn_manager_test@example.com",
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
            {"code": "PROC-BPMN-TEST", "name": "Processus test BPMN"}
        )

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.admin)

    def _new_version(self, process=None, version="V1", **vals):
        process = process or self.process
        values = {"process_id": process.id, "version": version}
        values.update(vals)
        return self.env["smq.process.version"].create(values)

    def _reject(self, version, reason="Motif de test"):
        action = version.action_reject()
        self.assertEqual(action["res_model"], "smq.process.version.reject.wizard")
        wizard = self.env["smq.process.version.reject.wizard"].create(
            {"version_id": version.id, "reason": reason}
        )
        wizard.action_confirm()

    def _to_effective(self, version):
        version.write({"bpmn_xml": _VALID_XML})
        version.action_submit_review()
        version.action_approve()
        version.action_make_effective()

    # ------------------------------------------------------------------
    # A. Extension du modèle smq.process
    # ------------------------------------------------------------------

    def test_a1_version_ids_relation(self):
        process = self.env["smq.process"].create({"code": "PROC-A1", "name": "A1"})
        v1 = self._new_version(process, "V1")
        v2 = self._new_version(process, "V2")
        self.assertEqual(set(process.version_ids.ids), {v1.id, v2.id})

    def test_a2_version_count_computed(self):
        process = self.env["smq.process"].create({"code": "PROC-A2", "name": "A2"})
        self.assertEqual(process.version_count, 0)
        self._new_version(process, "V1")
        self._new_version(process, "V2")
        process.invalidate_recordset()
        self.assertEqual(process.version_count, 2)

    def test_a3_current_version_id_empty_by_default(self):
        process = self.env["smq.process"].create({"code": "PROC-A3", "name": "A3"})
        self.assertFalse(process.current_version_id)

    def test_a4_process_existing_fields_untouched(self):
        process = self.env["smq.process"].create(
            {"code": "PROC-A4", "name": "A4", "status": "draft"}
        )
        self.assertEqual(process.status, "draft")
        self.assertTrue(process.active)

    # ------------------------------------------------------------------
    # B. Création et unicité des versions
    # ------------------------------------------------------------------

    def test_b1_create_version_defaults_draft(self):
        version = self._new_version(version="VB1")
        self.assertEqual(version.state, "draft")

    def test_b2_created_by_defaults_current_user(self):
        version = self._new_version(version="VB2")
        self.assertEqual(version.created_by, self.admin)

    def test_b3_created_date_auto_set(self):
        version = self._new_version(version="VB3")
        self.assertTrue(version.created_date)

    def test_b4_duplicate_version_same_process_rejected(self):
        self._new_version(version="VB4-DUP")
        with self.assertRaises(Exception):
            self._new_version(version="VB4-DUP")
            self.env.flush_all()

    def test_b5_same_version_label_allowed_on_different_process(self):
        other_process = self.env["smq.process"].create(
            {"code": "PROC-B5", "name": "B5"}
        )
        self._new_version(self.process, "VB5-SHARED")
        self._new_version(other_process, "VB5-SHARED")
        self.env.flush_all()

    def test_b6_create_with_non_draft_state_blocked(self):
        # §22 (analyse) : lacune fermée — create() ne peut pas démarrer
        # ailleurs qu'en draft.
        with self.assertRaises(ValidationError):
            self.env["smq.process.version"].create(
                {"process_id": self.process.id, "version": "VB6", "state": "effective"}
            )

    # ------------------------------------------------------------------
    # C. Transitions autorisées (machine à 6 états, §3/§24)
    # ------------------------------------------------------------------

    def test_c1_submit_review_draft_to_review(self):
        version = self._new_version(version="VC1")
        version.with_user(self.writer).action_submit_review()
        self.assertEqual(version.state, "review")

    def test_c2_approve_from_review(self):
        version = self._new_version(version="VC2", bpmn_xml=_VALID_XML)
        version.action_submit_review()
        version.action_approve()
        self.assertEqual(version.state, "approved")
        self.assertEqual(version.approved_by, self.admin)
        self.assertTrue(version.approved_date)

    def test_c3_make_effective_from_approved(self):
        version = self._new_version(version="VC3", bpmn_xml=_VALID_XML)
        version.action_submit_review()
        version.action_approve()
        version.action_make_effective()
        self.assertEqual(version.state, "effective")
        self.assertEqual(version.effective_by, self.admin)
        self.assertTrue(version.effective_date)

    def test_c4_obsolete_from_effective(self):
        version = self._new_version(version="VC4")
        self._to_effective(version)
        version.action_obsolete()
        self.assertEqual(version.state, "obsolete")
        self.assertTrue(version.obsolete_date)

    def test_c5_reject_from_review(self):
        version = self._new_version(version="VC5")
        version.action_submit_review()
        self._reject(version, "Incomplet")
        self.assertEqual(version.state, "rejected")
        self.assertEqual(version.rejection_reason, "Incomplet")
        self.assertEqual(version.rejected_by, self.admin)

    def test_c6_reset_to_draft_from_rejected(self):
        version = self._new_version(version="VC6")
        version.action_submit_review()
        self._reject(version)
        version.with_user(self.writer).action_reset_to_draft()
        self.assertEqual(version.state, "draft")

    # ------------------------------------------------------------------
    # D. Transitions interdites
    # ------------------------------------------------------------------

    def test_d1_submit_review_from_non_draft_raises(self):
        version = self._new_version(version="VD1")
        version.action_submit_review()
        with self.assertRaises(UserError):
            version.action_submit_review()

    def test_d2_approve_from_draft_raises(self):
        version = self._new_version(version="VD2")
        with self.assertRaises(UserError):
            version.action_approve()

    def test_d3_make_effective_from_draft_raises(self):
        version = self._new_version(version="VD3")
        with self.assertRaises(UserError):
            version.action_make_effective()

    def test_d4_make_effective_from_review_raises(self):
        version = self._new_version(version="VD4")
        version.action_submit_review()
        with self.assertRaises(UserError):
            version.action_make_effective()

    def test_d5_obsolete_from_approved_raises(self):
        version = self._new_version(version="VD5", bpmn_xml=_VALID_XML)
        version.action_submit_review()
        version.action_approve()
        with self.assertRaises(UserError):
            version.action_obsolete()

    def test_d6_reset_to_draft_from_review_raises(self):
        # LOT 11 : contrairement au LOT 8, "reset_to_draft" ne part plus de
        # "review" mais de "rejected" — un retour direct review->draft sans
        # passer par le rejet motivé n'est plus autorisé.
        version = self._new_version(version="VD6")
        version.action_submit_review()
        with self.assertRaises(UserError):
            version.action_reset_to_draft()

    def test_d7_direct_state_write_raises(self):
        version = self._new_version(version="VD7")
        with self.assertRaises(ValidationError):
            version.write({"state": "approved"})

    # ------------------------------------------------------------------
    # E. Version effective unique / process.current_version_id
    # ------------------------------------------------------------------

    def test_e1_first_effective_sets_current_version(self):
        process = self.env["smq.process"].create({"code": "PROC-E1", "name": "E1"})
        v1 = self._new_version(process, "V1")
        self._to_effective(v1)
        self.assertEqual(process.current_version_id, v1)

    def test_e2_second_effective_obsoletes_first_and_becomes_current(self):
        process = self.env["smq.process"].create({"code": "PROC-E2", "name": "E2"})
        v1 = self._new_version(process, "V1")
        self._to_effective(v1)

        v2 = self._new_version(process, "V2")
        self._to_effective(v2)

        self.assertEqual(v1.state, "obsolete")
        self.assertTrue(v1.obsolete_date)
        self.assertEqual(v2.state, "effective")
        self.assertEqual(process.current_version_id, v2)

    def test_e3_constraint_blocks_two_simultaneous_effective(self):
        process = self.env["smq.process"].create({"code": "PROC-E3", "name": "E3"})
        v1 = self._new_version(process, "V1")
        v2 = self._new_version(process, "V2")
        v1._write_state({"state": "effective"})
        with self.assertRaises(ValidationError):
            v2._write_state({"state": "effective"})
            self.env.flush_all()

    # ------------------------------------------------------------------
    # F. Verrouillage — Python, jamais seulement readonly dans les vues
    # ------------------------------------------------------------------

    def test_f1_bpmn_xml_editable_in_draft(self):
        version = self._new_version(version="VF1")
        version.write({"bpmn_xml": _VALID_XML})
        self.assertEqual(version.bpmn_xml, _VALID_XML)

    def test_f2_bpmn_xml_locked_in_review(self):
        version = self._new_version(version="VF2", bpmn_xml=_VALID_XML)
        version.action_submit_review()
        with self.assertRaises(ValidationError):
            version.write({"bpmn_xml": _VALID_XML_V2})

    def test_f3_bpmn_xml_locked_in_approved(self):
        version = self._new_version(version="VF3", bpmn_xml=_VALID_XML)
        version.action_submit_review()
        version.action_approve()
        with self.assertRaises(ValidationError):
            version.write({"bpmn_xml": _VALID_XML_V2})

    def test_f4_bpmn_xml_locked_in_effective(self):
        version = self._new_version(version="VF4")
        self._to_effective(version)
        with self.assertRaises(ValidationError):
            version.write({"bpmn_xml": _VALID_XML_V2})

    def test_f5_bpmn_xml_locked_in_obsolete(self):
        version = self._new_version(version="VF5")
        self._to_effective(version)
        version.action_obsolete()
        with self.assertRaises(ValidationError):
            version.write({"bpmn_xml": _VALID_XML_V2})

    def test_f6_bpmn_xml_locked_in_rejected(self):
        version = self._new_version(version="VF6", bpmn_xml=_VALID_XML)
        version.action_submit_review()
        self._reject(version)
        with self.assertRaises(ValidationError):
            version.write({"bpmn_xml": _VALID_XML_V2})

    def test_f7_notes_still_editable_when_effective(self):
        version = self._new_version(version="VF7")
        self._to_effective(version)
        version.write({"notes": "Commentaire ajouté après mise en vigueur"})
        self.assertEqual(version.notes, "Commentaire ajouté après mise en vigueur")

    # ------------------------------------------------------------------
    # G. BPMN XML et checksum
    # ------------------------------------------------------------------

    def test_g1_checksum_matches_sha256_of_xml(self):
        version = self._new_version(version="VG1", bpmn_xml=_VALID_XML)
        expected = hashlib.sha256(_VALID_XML.encode("utf-8")).hexdigest()
        self.assertEqual(version.bpmn_checksum, expected)

    def test_g2_checksum_false_when_xml_empty(self):
        version = self._new_version(version="VG2")
        self.assertFalse(version.bpmn_checksum)

    def test_g3_checksum_recomputed_on_xml_change(self):
        version = self._new_version(version="VG3", bpmn_xml=_VALID_XML)
        first = version.bpmn_checksum
        version.write({"bpmn_xml": _VALID_XML_V2})
        version.invalidate_recordset()
        second = version.bpmn_checksum
        self.assertNotEqual(first, second)
        self.assertEqual(
            second, hashlib.sha256(_VALID_XML_V2.encode("utf-8")).hexdigest()
        )

    def test_g4_checksum_field_not_manually_settable_via_views(self):
        field = self.env["smq.process.version"]._fields["bpmn_checksum"]
        self.assertTrue(field.compute)
        self.assertTrue(field.store)
        self.assertFalse(field.inverse)

    # ------------------------------------------------------------------
    # H. Sécurité Viewer / Editor / Manager
    # ------------------------------------------------------------------

    def test_h1_viewer_can_read_process_and_version(self):
        version = self._new_version(version="VH1")
        version.with_user(self.employee).read(["state"])
        self.process.with_user(self.employee).read(["code"])

    def test_h2_viewer_cannot_create_process(self):
        with self.assertRaises(Exception):
            self.env["smq.process"].with_user(self.employee).create(
                {"code": "PROC-H2", "name": "H2"}
            )

    def test_h3_viewer_cannot_create_version(self):
        with self.assertRaises(Exception):
            self.env["smq.process.version"].with_user(self.employee).create(
                {"process_id": self.process.id, "version": "VH3"}
            )

    def test_h4_editor_can_create_process(self):
        process = self.env["smq.process"].with_user(self.writer).create(
            {"code": "PROC-H4", "name": "H4"}
        )
        self.assertTrue(process)

    def test_h5_editor_can_create_version_and_submit_review(self):
        version = self.env["smq.process.version"].with_user(self.writer).create(
            {"process_id": self.process.id, "version": "VH5"}
        )
        version.with_user(self.writer).action_submit_review()
        self.assertEqual(version.state, "review")

    def test_h6_editor_cannot_approve(self):
        version = self._new_version(version="VH6", bpmn_xml=_VALID_XML)
        version.action_submit_review()
        with self.assertRaises(UserError):
            version.with_user(self.writer).action_approve()

    def test_h7_editor_cannot_make_effective_or_reject(self):
        version = self._new_version(version="VH7", bpmn_xml=_VALID_XML)
        version.action_submit_review()
        version.action_approve()
        with self.assertRaises(UserError):
            version.with_user(self.writer).action_make_effective()
        version2 = self._new_version(version="VH7-bis")
        version2.action_submit_review()
        with self.assertRaises(UserError):
            version2.with_user(self.writer).action_reject()

    def test_h8_manager_can_approve_make_effective_obsolete(self):
        version = self._new_version(version="VH8", bpmn_xml=_VALID_XML)
        version.with_user(self.writer).action_submit_review()
        version.with_user(self.manager).action_approve()
        self.assertEqual(version.state, "approved")
        version.with_user(self.manager).action_make_effective()
        self.assertEqual(version.state, "effective")
        version.with_user(self.manager).action_obsolete()
        self.assertEqual(version.state, "obsolete")

    # ------------------------------------------------------------------
    # I. Préconditions avant approbation (§11)
    # ------------------------------------------------------------------

    def test_i1_approve_without_xml_blocked(self):
        version = self._new_version(version="VI1")
        version.action_submit_review()
        with self.assertRaises(ValidationError):
            version.action_approve()

    def test_i2_approve_with_invalid_xml_blocked(self):
        version = self._new_version(version="VI2", bpmn_xml=_XML_INVALID)
        version.action_submit_review()
        with self.assertRaises(ValidationError):
            version.action_approve()

    def test_i3_approve_without_identifiable_process_blocked(self):
        version = self._new_version(version="VI3", bpmn_xml=_XML_NO_PROCESS)
        version.action_submit_review()
        with self.assertRaises(ValidationError):
            version.action_approve()

    def test_i4_approve_with_orphaned_mapping_blocked(self):
        version = self._new_version(version="VI4", bpmn_xml=_VALID_XML)
        self.env["smq.bpmn.task.mapping"].create(
            {"process_version_id": version.id, "bpmn_element_id": "Task_MISSING"}
        )
        version.action_submit_review()
        with self.assertRaises(ValidationError):
            version.action_approve()

    # ------------------------------------------------------------------
    # J. Rejet (§13)
    # ------------------------------------------------------------------

    def test_j1_reject_wizard_requires_reason(self):
        version = self._new_version(version="VJ1")
        version.action_submit_review()
        with self.assertRaises(Exception):
            self.env["smq.process.version.reject.wizard"].create({"version_id": version.id})
            self.env.flush_all()

    def test_j2_reject_records_traceability(self):
        version = self._new_version(version="VJ2")
        version.action_submit_review()
        self._reject(version, "Mapping de validation incomplet")
        self.assertEqual(version.rejection_reason, "Mapping de validation incomplet")
        self.assertTrue(version.rejected_date)
        self.assertEqual(version.rejected_by, self.admin)

    def test_j3_reject_from_non_review_raises(self):
        version = self._new_version(version="VJ3")
        with self.assertRaises(UserError):
            version.action_reject()

    def test_j4_reject_only_by_manager(self):
        version = self._new_version(version="VJ4")
        version.with_user(self.writer).action_submit_review()
        with self.assertRaises(UserError):
            version.with_user(self.writer).action_reject()

    # ------------------------------------------------------------------
    # K. Nouvelle version / clonage (§8-9)
    # ------------------------------------------------------------------

    def test_k1_create_new_version_is_independent_draft(self):
        process = self.env["smq.process"].create({"code": "PROC-K1", "name": "K1"})
        v1 = self._new_version(process, "1.0", bpmn_xml=_VALID_XML)
        self._to_effective(v1)
        action = v1.with_user(self.writer).action_create_new_version()
        v2 = self.env["smq.process.version"].browse(action["res_id"])
        self.assertEqual(v2.state, "draft")
        self.assertEqual(v2.bpmn_xml, _VALID_XML)
        self.assertNotEqual(v2.id, v1.id)

    def test_k2_version_numbering_increments_minor(self):
        process = self.env["smq.process"].create({"code": "PROC-K2", "name": "K2"})
        v1 = self._new_version(process, "1.0", bpmn_xml=_VALID_XML)
        v2_action = v1.action_create_new_version()
        v2 = self.env["smq.process.version"].browse(v2_action["res_id"])
        self.assertEqual(v2.version, "1.1")
        v3_action = v2.action_create_new_version()
        v3 = self.env["smq.process.version"].browse(v3_action["res_id"])
        self.assertEqual(v3.version, "1.2")

    def test_k3_cloned_mappings_are_new_independent_records(self):
        process = self.env["smq.process"].create({"code": "PROC-K3", "name": "K3"})
        v1 = self._new_version(process, "1.0", bpmn_xml=_VALID_XML)
        mapping_v1 = self.env["smq.bpmn.task.mapping"].create(
            {
                "process_version_id": v1.id,
                "bpmn_element_id": "Task_1",
                "task_type": "document",
            }
        )
        action = v1.action_create_new_version()
        v2 = self.env["smq.process.version"].browse(action["res_id"])
        self.assertEqual(len(v2.mapping_ids), 1)
        mapping_v2 = v2.mapping_ids
        self.assertNotEqual(mapping_v1.id, mapping_v2.id)
        self.assertEqual(mapping_v2.bpmn_element_id, "Task_1")
        self.assertEqual(mapping_v2.task_type, "document")

    def test_k4_modifying_clone_mapping_never_touches_original(self):
        process = self.env["smq.process"].create({"code": "PROC-K4", "name": "K4"})
        v1 = self._new_version(process, "1.0", bpmn_xml=_VALID_XML)
        self.env["smq.bpmn.task.mapping"].create(
            {"process_version_id": v1.id, "bpmn_element_id": "Task_1", "task_type": "document"}
        )
        self._to_effective(v1)
        action = v1.action_create_new_version()
        v2 = self.env["smq.process.version"].browse(action["res_id"])
        v2.mapping_ids.write({"task_type": "approval"})
        self.assertEqual(v1.mapping_ids.task_type, "document")
        self.assertEqual(v2.mapping_ids.task_type, "approval")

    def test_k5_new_version_created_from_any_source_state(self):
        process = self.env["smq.process"].create({"code": "PROC-K5", "name": "K5"})
        v1 = self._new_version(process, "1.0")
        action = v1.action_create_new_version()
        v2 = self.env["smq.process.version"].browse(action["res_id"])
        self.assertEqual(v2.state, "draft")

    def test_k6_non_numeric_source_version_falls_back_gracefully(self):
        process = self.env["smq.process"].create({"code": "PROC-K6", "name": "K6"})
        v1 = self._new_version(process, "V-legacy")
        action = v1.action_create_new_version()
        v2 = self.env["smq.process.version"].browse(action["res_id"])
        self.assertEqual(v2.version, "1.0")

    # ------------------------------------------------------------------
    # L. Sécurité — contournement ORM direct (§21)
    # ------------------------------------------------------------------

    def test_l1_writer_cannot_bypass_lock_via_direct_orm_write(self):
        version = self._new_version(version="VL1")
        self._to_effective(version)
        with self.assertRaises(ValidationError):
            version.with_user(self.writer).write({"bpmn_xml": _VALID_XML_V2, "name": "hack"})

    def test_l2_writer_cannot_bypass_lock_via_direct_state_write(self):
        version = self._new_version(version="VL2")
        with self.assertRaises(ValidationError):
            version.with_user(self.writer).write({"state": "effective"})

    # ------------------------------------------------------------------
    # M. Chatter / traçabilité (§14)
    # ------------------------------------------------------------------

    def test_m1_submit_review_posts_chatter_message(self):
        version = self._new_version(version="VM1")
        count_before = len(version.message_ids)
        version.action_submit_review()
        self.assertGreater(len(version.message_ids), count_before)

    def test_m2_make_effective_posts_chatter_message_on_old_and_new(self):
        process = self.env["smq.process"].create({"code": "PROC-M2", "name": "M2"})
        v1 = self._new_version(process, "V1")
        self._to_effective(v1)
        v2 = self._new_version(process, "V2")
        v2.write({"bpmn_xml": _VALID_XML})
        v2.action_submit_review()
        v2.action_approve()
        count_before = len(v1.message_ids)
        v2.action_make_effective()
        self.assertGreater(len(v1.message_ids), count_before)
