from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLot7ViewPinning(TransactionCase):
    """LOT 7 : action_smq_nonconformity et action_smq_audit ne pinnaient pas
    explicitement leurs vues kanban/tree/form (contrairement à
    action_smq_management_review, corrigée au LOT 2) — le webclient
    résolvait donc silencieusement vers les vues OCA natives au lieu des
    vues SMQ. Ces tests vérifient la configuration réelle des actions
    (le champ relationnel view_ids, pas un appel direct à une méthode
    métier), pour reproduire fidèlement ce que fait le webclient."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.action_nc = cls.env.ref("smq_quality_bridge.action_smq_nonconformity")
        cls.action_audit = cls.env.ref("smq_quality_bridge.action_smq_audit")

    def test_01_nonconformity_action_has_explicit_view_per_mode(self):
        views_by_mode = {v.view_mode: v.view_id for v in self.action_nc.view_ids}
        self.assertEqual(
            views_by_mode.get("kanban"),
            self.env.ref("smq_quality_bridge.view_smq_nonconformity_kanban"),
        )
        self.assertEqual(
            views_by_mode.get("tree"),
            self.env.ref("smq_quality_bridge.view_smq_nonconformity_tree"),
        )
        self.assertEqual(
            views_by_mode.get("form"),
            self.env.ref("smq_quality_bridge.view_smq_nonconformity_form"),
        )

    def test_02_audit_action_has_explicit_view_per_mode(self):
        views_by_mode = {v.view_mode: v.view_id for v in self.action_audit.view_ids}
        self.assertEqual(
            views_by_mode.get("tree"),
            self.env.ref("smq_quality_bridge.view_smq_audit_tree"),
        )
        self.assertEqual(
            views_by_mode.get("form"),
            self.env.ref("smq_quality_bridge.view_smq_audit_form"),
        )
        self.assertEqual(
            views_by_mode.get("calendar"),
            self.env.ref("mgmtsystem_audit.view_audit_calendar"),
        )

    def test_03_nonconformity_get_views_resolves_smq_views(self):
        # Reproduit exactement l'appel du webclient (liste (view_id, view_type)
        # portée par l'action) plutôt que d'appeler get_view() sans contexte.
        result = self.env["mgmtsystem.nonconformity"].get_views(self.action_nc.views)
        for view_type, xmlid in (
            ("kanban", "smq_quality_bridge.view_smq_nonconformity_kanban"),
            ("tree", "smq_quality_bridge.view_smq_nonconformity_tree"),
            ("form", "smq_quality_bridge.view_smq_nonconformity_form"),
        ):
            self.assertEqual(
                result["views"][view_type]["id"], self.env.ref(xmlid).id
            )

    def test_04_audit_get_views_resolves_smq_views(self):
        result = self.env["mgmtsystem.audit"].get_views(self.action_audit.views)
        for view_type, xmlid in (
            ("tree", "smq_quality_bridge.view_smq_audit_tree"),
            ("form", "smq_quality_bridge.view_smq_audit_form"),
            ("calendar", "mgmtsystem_audit.view_audit_calendar"),
        ):
            self.assertEqual(
                result["views"][view_type]["id"], self.env.ref(xmlid).id
            )

    def test_05_nonconformity_form_exposes_smq_button_box(self):
        result = self.env["mgmtsystem.nonconformity"].get_views(self.action_nc.views)
        arch = result["views"]["form"]["arch"]
        self.assertIn("quality_process_id", arch)
        self.assertIn("action_view_actions", arch)
        self.assertIn("action_view_smq_documents", arch)

    def test_06_audit_form_exposes_smq_button_box(self):
        result = self.env["mgmtsystem.audit"].get_views(self.action_audit.views)
        arch = result["views"]["form"]["arch"]
        self.assertIn("quality_process_id", arch)
        self.assertIn("action_view_nonconformities", arch)
        self.assertIn("action_view_imp_opp", arch)
        self.assertIn("action_view_smq_documents", arch)

    def test_07_audit_calendar_unchanged_no_new_smq_view_created(self):
        # Contrainte explicite du LOT 7 : ne pas créer de vue calendar SMQ
        # inexistante — réutiliser le calendrier OCA natif tel quel.
        views_by_mode = {v.view_mode: v.view_id for v in self.action_audit.view_ids}
        self.assertEqual(views_by_mode["calendar"].model, "mgmtsystem.audit")
        self.assertFalse(
            self.env["ir.ui.view"].search(
                [("model", "=", "mgmtsystem.audit"), ("type", "=", "calendar")]
            )
            - self.env.ref("mgmtsystem_audit.view_audit_calendar")
        )
