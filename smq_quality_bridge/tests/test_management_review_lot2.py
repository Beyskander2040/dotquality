from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestManagementReviewLot2(TransactionCase):
    """LOT 2 : corrections ciblées sur l'intégration existante de
    mgmtsystem.review — aucun nouveau modèle, uniquement résolution de
    vue, sondage, dashboard, rapport PDF et masquage du menu OCA."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.action = cls.env.ref("smq_quality_bridge.action_smq_management_review")

    def test_01_action_has_explicit_view_per_mode(self):
        views_by_mode = {v.view_mode: v.view_id for v in self.action.view_ids}
        self.assertEqual(
            views_by_mode.get("tree"),
            self.env.ref("smq_quality_bridge.view_smq_management_review_tree"),
        )
        self.assertEqual(
            views_by_mode.get("form"),
            self.env.ref("smq_quality_bridge.view_smq_management_review_form"),
        )
        self.assertEqual(
            views_by_mode.get("calendar"),
            self.env.ref("mgmtsystem_review.view_review_calendar"),
        )

    def test_02_survey_responses_visible_on_french_form(self):
        view = self.env["mgmtsystem.review"].get_view(
            view_id=self.env.ref("smq_quality_bridge.view_smq_management_review_form").id,
            view_type="form",
        )
        self.assertIn("response_ids", view["arch"])

    def test_03_dashboard_tile_reflects_review_count(self):
        tile = self.env.ref("smq_quality_bridge.smq_dashboard_tile_management_review")
        before = self.env["mgmtsystem.review"].search_count([])
        self.env["mgmtsystem.review"].create(
            {"name": "Revue test dashboard", "date": "2026-06-01 09:00:00"}
        )
        self.assertEqual(tile.count, before + 1)
        self.assertEqual(
            tile._get_action_xmlid(),
            "smq_quality_bridge.action_smq_management_review",
        )

    def test_04_management_review_no_longer_future(self):
        modules = self.env["smq.dashboard.tile"].get_dashboard_data()["module_categories"]
        future_keys = {
            f["key"]
            for category in modules
            for f in category["modules"]
            if f["count"] is False
        }
        self.assertNotIn("management_review", future_keys)

    def test_05_admin_not_in_oca_manager_group(self):
        group = self.env.ref("mgmtsystem.group_mgmtsystem_manager")
        self.assertNotIn(self.env.ref("base.user_admin"), group.users)

    def test_06_pdf_report_renders_in_french(self):
        review = self.env["mgmtsystem.review"].create(
            {"name": "Revue test PDF", "date": "2026-06-01 09:00:00"}
        )
        report = self.env.ref("mgmtsystem_review.review_report_mgmtsystem_review")
        html, _report_type = self.env["ir.actions.report"]._render_qweb_html(
            report.id, review.ids
        )
        html_text = html.decode() if isinstance(html, bytes) else html
        self.assertIn("Rapport de revue de direction", html_text)
        self.assertNotIn("Review Report", html_text)
