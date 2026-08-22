from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSmqReferential(TransactionCase):
    def test_requirement_complete_name_includes_parent(self):
        referential = self.env["smq.referential"].create({"name": "Référentiel test"})
        parent = self.env["smq.referential.requirement"].create(
            {"referential_id": referential.id, "code": "7", "name": "Support"}
        )
        child = self.env["smq.referential.requirement"].create(
            {
                "referential_id": referential.id,
                "parent_id": parent.id,
                "code": "7.5",
                "name": "Informations documentées",
            }
        )
        self.assertIn(parent.complete_name, child.complete_name)

    def test_generate_compliance_lines_creates_one_per_leaf_requirement(self):
        referential = self.env["smq.referential"].create({"name": "Référentiel test"})
        parent = self.env["smq.referential.requirement"].create(
            {"referential_id": referential.id, "code": "7", "name": "Support"}
        )
        leaf = self.env["smq.referential.requirement"].create(
            {
                "referential_id": referential.id,
                "parent_id": parent.id,
                "code": "7.5",
                "name": "Informations documentées",
            }
        )
        referential.action_generate_compliance_lines()
        lines = self.env["smq.compliance.line"].search([("requirement_id", "=", leaf.id)])
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.state, "not_evaluated")
        # Le parent n'est pas terminal (a un enfant) : aucune ligne créée pour lui.
        parent_lines = self.env["smq.compliance.line"].search([("requirement_id", "=", parent.id)])
        self.assertFalse(parent_lines)
        # Ré-exécuter le bouton ne doit pas dupliquer la ligne déjà créée.
        referential.action_generate_compliance_lines()
        lines_after = self.env["smq.compliance.line"].search([("requirement_id", "=", leaf.id)])
        self.assertEqual(len(lines_after), 1)

    def test_compliance_line_unique_per_requirement_and_process(self):
        referential = self.env["smq.referential"].create({"name": "Référentiel test"})
        requirement = self.env["smq.referential.requirement"].create(
            {"referential_id": referential.id, "code": "7.5", "name": "Informations documentées"}
        )
        # Sans processus (évaluation globale) : la contrainte SQL ne détecte
        # pas les NULL, c'est le contrôle Python qui doit lever l'erreur.
        self.env["smq.compliance.line"].create({"requirement_id": requirement.id})
        with self.assertRaises(ValidationError):
            self.env["smq.compliance.line"].create({"requirement_id": requirement.id})

        # Avec un processus renseigné : la contrainte SQL détecte le doublon.
        process = self.env["smq.process"].create({"code": "PR-REF-TEST-UNIQ", "name": "Test"})
        self.env["smq.compliance.line"].create(
            {"requirement_id": requirement.id, "process_id": process.id}
        )
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["smq.compliance.line"].create(
                {"requirement_id": requirement.id, "process_id": process.id}
            )

    def test_compliance_line_can_reference_process_and_document_evidence(self):
        process = self.env["smq.process"].create({"code": "PR-REF-TEST", "name": "Test"})
        document_type = self.env["smq.document.type"].create(
            {"name": "Type test", "code_prefix": "REFTST"}
        )
        document = self.env["smq.document"].create({"name": "Doc test", "document_type_id": document_type.id})
        referential = self.env["smq.referential"].create({"name": "Référentiel test"})
        requirement = self.env["smq.referential.requirement"].create(
            {"referential_id": referential.id, "code": "7.5", "name": "Informations documentées"}
        )
        line = self.env["smq.compliance.line"].create(
            {
                "requirement_id": requirement.id,
                "process_id": process.id,
                "state": "compliant",
                "evidence_document_ids": [(4, document.id)],
            }
        )
        self.assertEqual(line.process_id, process)
        self.assertIn(document, line.evidence_document_ids)
        self.assertEqual(line.referential_id, referential)
