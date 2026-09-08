import base64

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestSmqDocumentPeriodicReview(TransactionCase):
    """LOT 3 : Révisions = suivi des échéances de révision périodique
    documentaire (distinct de la Revue de direction) — extension de
    smq.document + wizard, aucun nouveau modèle métier persistant."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.quality_manager = cls.env.ref("base.user_admin")
        cls.doc_type = cls.env["smq.document.type"].create(
            {"name": "Procédure Test", "code_prefix": "PREV", "review_period": 12}
        )
        cls.writer = cls.env["res.users"].create(
            {
                "name": "Rédacteur SMQ Test",
                "login": "smq_periodic_review_writer_test",
                "groups_id": [
                    (6, 0, [
                        cls.env.ref("base.group_user").id,
                        cls.env.ref("smq_quality.group_smq_writer").id,
                    ])
                ],
            }
        )

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.quality_manager)

    def _make_effective_document(self, effective_date="2026-01-01 09:00:00", **extra):
        doc = self.env["smq.document"].create(
            {"name": "Doc test", "document_type_id": self.doc_type.id, **extra}
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
        version.action_set_effective_confirm(fields.Datetime.from_string(effective_date))
        return doc

    def test_01_next_review_date_from_effective_date(self):
        doc = self._make_effective_document()
        self.assertEqual(doc.next_review_date, fields.Date.from_string("2027-01-01"))

    def test_02_periodic_review_confirm_updates_fields(self):
        doc = self._make_effective_document()
        doc.action_periodic_review_confirm(
            fields.Datetime.from_string("2026-06-15 10:00:00"), "Rien à signaler."
        )
        self.assertEqual(
            doc.last_periodic_review_date, fields.Datetime.from_string("2026-06-15 10:00:00")
        )
        self.assertEqual(doc.last_periodic_reviewer_id, self.quality_manager)

    def test_03_next_review_date_uses_latest_periodic_review(self):
        doc = self._make_effective_document()
        doc.action_periodic_review_confirm(fields.Datetime.from_string("2026-06-15 10:00:00"))
        # 2026-06-15 est plus récent que l'entrée en vigueur (2026-01-01) :
        # la prochaine échéance repart de la revue périodique, pas de la
        # version.
        self.assertEqual(doc.next_review_date, fields.Date.from_string("2027-06-15"))

    def test_04_new_version_supersedes_stale_periodic_review(self):
        doc = self._make_effective_document()
        doc.action_periodic_review_confirm(fields.Datetime.from_string("2026-02-01 10:00:00"))
        new_version = self.env["smq.document.version"].create(
            {"document_id": doc.id, "previous_version_id": doc.current_version_id.id, "change_reason": "other"}
        )
        new_version.attachment_ids = [
            (
                0,
                0,
                {
                    "name": "fichier2.txt",
                    "datas": base64.b64encode(b"contenu 2"),
                    "res_model": "smq.document.version",
                },
            )
        ]
        new_version.action_submit_validation()
        new_version.action_validate()
        new_version.action_publish()
        new_version.action_set_effective_confirm(fields.Datetime.from_string("2026-09-01 09:00:00"))
        # La nouvelle version (2026-09-01) est plus récente que l'ancienne
        # revue périodique (2026-02-01) : c'est elle qui sert de base.
        self.assertEqual(doc.next_review_date, fields.Date.from_string("2027-09-01"))

    def test_05_periodic_review_requires_effective_document(self):
        doc = self.env["smq.document"].create(
            {"name": "Doc brouillon", "document_type_id": self.doc_type.id}
        )
        with self.assertRaises(UserError):
            doc.action_periodic_review()

    def test_06_search_filter_to_review_unaffected(self):
        # Échéance (2024-01-01 + 12 mois = 2025-01-01) largement dépassée par
        # rapport à "aujourd'hui" dans l'environnement de test.
        overdue = self._make_effective_document(effective_date="2024-01-01 09:00:00")
        found = self.env["smq.document"].search(
            [("next_review_date", "<=", fields.Date.context_today(self.env["smq.document"]))]
        )
        self.assertIn(overdue, found)

    def test_07_action_to_review_points_to_smq_document(self):
        action = self.env.ref("smq_document.action_smq_document_to_review")
        self.assertEqual(action.res_model, "smq.document")

    def test_08_writer_cannot_confirm_periodic_review_wizard(self):
        doc = self._make_effective_document()
        with self.assertRaises(AccessError):
            self.env["smq.document.periodic.review.wizard"].with_user(self.writer).create(
                {"document_id": doc.id, "review_date": "2026-06-15"}
            )
