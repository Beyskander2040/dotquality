import base64

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestSmqDocumentVersion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.quality_manager = cls.env.ref("base.user_admin")
        cls.doc_type = cls.env["smq.document.type"].create(
            {"name": "Formulaire Test", "code_prefix": "FVTEST"}
        )

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.quality_manager)

    def _new_document(self):
        return self.env["smq.document"].create(
            {"name": "Doc", "document_type_id": self.doc_type.id}
        )

    def _attach_file(self, version):
        version.attachment_ids = [
            (
                0,
                0,
                {
                    "name": "fichier.txt",
                    "datas": base64.b64encode(b"contenu"),
                    "res_model": "smq.document.version",
                },
            )
        ]

    def test_first_version_number_is_one(self):
        doc = self._new_document()
        self.assertEqual(doc.version_ids.version_number, 1)

    def test_cannot_submit_without_attachment(self):
        doc = self._new_document()
        with self.assertRaises(UserError):
            doc.version_ids.action_submit_validation()

    def test_full_workflow_draft_to_effective(self):
        doc = self._new_document()
        version = doc.version_ids
        self._attach_file(version)

        version.action_submit_validation()
        self.assertEqual(version.state, "in_validation")
        self.assertTrue(version.submitted_by)
        self.assertTrue(version.submission_date)

        version.action_validate()
        self.assertEqual(version.state, "approved")
        self.assertTrue(version.validated_by)
        self.assertTrue(version.approval_date)

        version.action_publish()
        self.assertEqual(version.state, "published")
        self.assertTrue(version.published_by)
        self.assertTrue(version.publication_date)

        version.action_set_effective_confirm(fields.Datetime.now())
        self.assertEqual(version.state, "effective")
        self.assertTrue(version.set_effective_by)
        self.assertTrue(version.effective_date)
        self.assertEqual(doc.current_version_id, version)

    def test_reject_returns_to_draft_same_version_number(self):
        doc = self._new_document()
        version = doc.version_ids
        self._attach_file(version)
        version.action_submit_validation()

        version.action_reject_confirm("Motif de test")
        self.assertEqual(version.state, "draft")
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.rejection_reason, "Motif de test")
        self.assertTrue(version.rejected_by)

    def test_rejected_version_can_be_resubmitted_and_approved(self):
        doc = self._new_document()
        version = doc.version_ids
        self._attach_file(version)
        version.action_submit_validation()
        version.action_reject_confirm("Corriger le contenu")

        version.action_submit_validation()
        version.action_validate()
        self.assertEqual(version.state, "approved")
        self.assertEqual(version.version_number, 1)

    def test_cannot_write_state_directly(self):
        doc = self._new_document()
        version = doc.version_ids
        with self.assertRaises(ValidationError):
            version.write({"state": "effective"})

    def test_cannot_edit_locked_fields_after_leaving_draft(self):
        doc = self._new_document()
        version = doc.version_ids
        self._attach_file(version)
        version.action_submit_validation()
        with self.assertRaises(ValidationError):
            version.write({"change_description": "Modifié après coup"})

    def test_new_version_requires_effective_document(self):
        doc = self._new_document()
        with self.assertRaises(UserError):
            doc.action_create_new_version()

    def test_new_version_supersedes_previous_effective(self):
        doc = self._new_document()
        v1 = doc.version_ids
        self._attach_file(v1)
        v1.action_submit_validation()
        v1.action_validate()
        v1.action_publish()
        v1.action_set_effective_confirm(fields.Datetime.now())

        action = doc.action_create_new_version()
        v2 = self.env["smq.document.version"].create(
            {
                "document_id": doc.id,
                "previous_version_id": action["context"]["default_previous_version_id"],
                "change_reason": "process_improvement",
            }
        )
        self.assertEqual(v2.version_number, 2)
        self.assertEqual(v2.previous_version_id, v1)

        self._attach_file(v2)
        v2.action_submit_validation()
        v2.action_validate()
        v2.action_publish()
        v2.action_set_effective_confirm(fields.Datetime.now())

        self.assertEqual(v2.state, "effective")
        self.assertEqual(v1.state, "obsolete")
        self.assertTrue(v1.obsolete_date)
        self.assertEqual(doc.current_version_id, v2)

    def test_change_reason_required_from_v2(self):
        doc = self._new_document()
        v1 = doc.version_ids
        self._attach_file(v1)
        v1.action_submit_validation()
        v1.action_validate()
        v1.action_publish()
        v1.action_set_effective_confirm(fields.Datetime.now())

        with self.assertRaises(ValidationError):
            self.env["smq.document.version"].create(
                {"document_id": doc.id, "previous_version_id": v1.id}
            )

    def test_verifier_without_group_cannot_validate(self):
        doc = self._new_document()
        version = doc.version_ids
        self._attach_file(version)
        version.action_submit_validation()
        employee_only = self.env["res.users"].create(
            {
                "name": "Employé Test",
                "login": "employe.test@example.com",
                "groups_id": [(6, 0, [self.env.ref("smq_quality.group_smq_employee").id])],
            }
        )
        with self.assertRaises(UserError):
            version.with_user(employee_only).action_validate()
