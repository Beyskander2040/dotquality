import base64

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestSmqDocument(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.quality_manager = cls.env.ref("base.user_admin")
        cls.type_proc = cls.env["smq.document.type"].create(
            {"name": "Procédure Test", "code_prefix": "PTEST", "requires_process": True}
        )
        cls.type_form = cls.env["smq.document.type"].create(
            {"name": "Formulaire Test", "code_prefix": "FTEST"}
        )
        cls.process = cls.env["smq.process"].create({"code": "PR-TEST", "name": "Test"})

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.quality_manager)

    def test_code_generation(self):
        doc1 = self.env["smq.document"].create(
            {
                "name": "Doc 1",
                "document_type_id": self.type_proc.id,
                "process_id": self.process.id,
            }
        )
        doc2 = self.env["smq.document"].create(
            {
                "name": "Doc 2",
                "document_type_id": self.type_proc.id,
                "process_id": self.process.id,
            }
        )
        self.assertEqual(doc1.code, "PTEST-001")
        self.assertEqual(doc2.code, "PTEST-002")

    def test_first_version_created_automatically(self):
        doc = self.env["smq.document"].create(
            {"name": "Doc", "document_type_id": self.type_form.id}
        )
        self.assertEqual(len(doc.version_ids), 1)
        self.assertEqual(doc.version_ids.version_number, 1)
        self.assertEqual(doc.version_ids.state, "draft")
        self.assertEqual(doc.stage_id.code, "draft")

    def test_process_required_for_type_that_requires_it(self):
        with self.assertRaises(ValidationError):
            self.env["smq.document"].create(
                {"name": "Sans processus", "document_type_id": self.type_proc.id}
            )

    def test_process_not_required_when_type_does_not_require_it(self):
        doc = self.env["smq.document"].create(
            {"name": "Sans processus", "document_type_id": self.type_form.id}
        )
        self.assertTrue(doc.id)

    def test_current_version_id_reflects_effective_version_only(self):
        doc = self.env["smq.document"].create(
            {"name": "Doc", "document_type_id": self.type_form.id}
        )
        version = doc.version_ids
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
        version.action_submit_validation()
        version.action_validate()
        version.action_publish()
        # Publiée mais pas encore effective : ne doit pas être "courante".
        self.assertFalse(doc.current_version_id)

        version.action_set_effective_confirm(fields.Datetime.now())
        self.assertEqual(doc.current_version_id, version)
        self.assertEqual(doc.stage_id.code, "effective")

    def test_cannot_create_new_version_without_effective_version(self):
        doc = self.env["smq.document"].create(
            {"name": "Doc", "document_type_id": self.type_form.id}
        )
        with self.assertRaises(UserError):
            doc.action_create_new_version()

    def test_parent_document_links_child_reverse_side(self):
        procedure = self.env["smq.document"].create(
            {
                "name": "Procédure de traitement des NC",
                "document_type_id": self.type_proc.id,
                "process_id": self.process.id,
            }
        )
        form = self.env["smq.document"].create(
            {
                "name": "Fiche de déclaration de NC",
                "document_type_id": self.type_form.id,
                "parent_document_id": procedure.id,
            }
        )
        self.assertEqual(form.parent_document_id, procedure)
        self.assertIn(form, procedure.child_document_ids)
        self.assertEqual(procedure.child_document_count, 1)

    def test_document_cannot_be_its_own_parent(self):
        doc = self.env["smq.document"].create(
            {"name": "Doc", "document_type_id": self.type_form.id}
        )
        with self.assertRaises(ValidationError):
            doc.write({"parent_document_id": doc.id})

    def test_complete_name_shows_parent_chevron_child(self):
        procedure = self.env["smq.document"].create(
            {"name": "Procédure de traitement des NC", "document_type_id": self.type_proc.id, "process_id": self.process.id}
        )
        form = self.env["smq.document"].create(
            {
                "name": "Fiche de déclaration de NC",
                "document_type_id": self.type_form.id,
                "parent_document_id": procedure.id,
            }
        )
        self.assertEqual(procedure.complete_name, "Procédure de traitement des NC")
        self.assertEqual(
            form.complete_name, "Procédure de traitement des NC › Fiche de déclaration de NC"
        )

    def test_child_inherits_parent_process_when_unset(self):
        procedure = self.env["smq.document"].create(
            {"name": "Procédure", "document_type_id": self.type_proc.id, "process_id": self.process.id}
        )
        form = self.env["smq.document"].create(
            {"name": "Formulaire", "document_type_id": self.type_form.id, "parent_document_id": procedure.id}
        )
        self.assertEqual(form.process_id, self.process)

    def test_child_process_not_overridden_when_explicit(self):
        other_process = self.env["smq.process"].create({"code": "PR-OTHER", "name": "Autre"})
        procedure = self.env["smq.document"].create(
            {"name": "Procédure", "document_type_id": self.type_proc.id, "process_id": self.process.id}
        )
        form = self.env["smq.document"].create(
            {
                "name": "Formulaire",
                "document_type_id": self.type_form.id,
                "parent_document_id": procedure.id,
                "process_id": other_process.id,
            }
        )
        self.assertEqual(form.process_id, other_process)

    def test_write_parent_document_id_inherits_process_when_unset(self):
        procedure = self.env["smq.document"].create(
            {"name": "Procédure", "document_type_id": self.type_proc.id, "process_id": self.process.id}
        )
        form = self.env["smq.document"].create({"name": "Formulaire", "document_type_id": self.type_form.id})
        form.write({"parent_document_id": procedure.id})
        self.assertEqual(form.process_id, self.process)

    def test_hierarchy_cycle_across_two_documents_is_rejected(self):
        doc_a = self.env["smq.document"].create(
            {"name": "Doc A", "document_type_id": self.type_form.id}
        )
        doc_b = self.env["smq.document"].create(
            {
                "name": "Doc B",
                "document_type_id": self.type_form.id,
                "parent_document_id": doc_a.id,
            }
        )
        with self.assertRaises(ValidationError):
            doc_a.write({"parent_document_id": doc_b.id})
