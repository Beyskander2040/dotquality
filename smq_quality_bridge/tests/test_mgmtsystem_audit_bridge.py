from odoo.tests.common import TransactionCase


class TestMgmtsystemAuditBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.process = cls.env["smq.process"].create({"code": "PR-AUDIT-TEST", "name": "Test"})
        cls.doc_type = cls.env["smq.document.type"].create(
            {"name": "Formulaire Audit Test", "code_prefix": "FAUDIT"}
        )
        cls.document = cls.env["smq.document"].create(
            {"name": "Doc Audit Test", "document_type_id": cls.doc_type.id}
        )
        cls.nc = cls.env["mgmtsystem.nonconformity"].create(
            {
                "name": "NC test audit",
                "description": "Description de test",
                "quality_process_id": cls.process.id,
                "origin_ids": [(4, cls.env.ref("mgmtsystem_nonconformity.nc_origin_process").id)],
            }
        )

    def _new_audit(self, **extra):
        vals = {
            "name": "Audit test",
            "quality_process_id": self.process.id,
            "smq_document_ids": [(4, self.document.id)],
            "nonconformity_ids": [(4, self.nc.id)],
        }
        vals.update(extra)
        return self.env["mgmtsystem.audit"].create(vals)

    def test_linked_to_process_and_document(self):
        audit = self._new_audit()
        self.assertEqual(audit.quality_process_id, self.process)
        self.assertIn(audit, self.document.audit_ids)
        self.assertEqual(self.process.audit_count, 1)
        self.assertEqual(self.document.audit_count, 1)

    def test_nonconformity_count(self):
        audit = self._new_audit()
        self.assertEqual(audit.nonconformity_count, 1)

    def test_action_view_smq_documents_domain(self):
        audit = self._new_audit()
        action = audit.action_view_smq_documents()
        self.assertEqual(action["domain"], [("id", "in", [self.document.id])])

    def test_action_view_nonconformities_domain(self):
        audit = self._new_audit()
        action = audit.action_view_nonconformities()
        self.assertEqual(action["domain"], [("id", "in", [self.nc.id])])

    def test_process_action_view_audits_domain(self):
        audit = self._new_audit()
        action = self.process.action_view_audits()
        self.assertEqual(action["domain"], [("quality_process_id", "=", self.process.id)])
        self.assertIn(audit.id, self.env["mgmtsystem.audit"].search(action["domain"]).ids)
