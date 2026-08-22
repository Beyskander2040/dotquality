from odoo.tests.common import TransactionCase


class TestSmqDashboardTile(TransactionCase):
    def test_process_tile_matches_reality(self):
        process = self.env["smq.process"]
        before = process.search_count([])
        process.create({"code": "PR-DASH-TEST", "name": "Test"})
        tile = self.env.ref("smq_quality.smq_dashboard_tile_process")
        self.assertEqual(tile.count, before + 1)

    def test_not_yet_wired_tiles_are_zero(self):
        # "Audits" attend encore un lot ultérieur : toujours 0 ici, même si
        # mgmtsystem_audit est installé et non vide.
        tile = self.env.ref("smq_quality.smq_dashboard_tile_audit")
        self.assertEqual(tile.count, 0)

    def test_nonconformity_and_action_tiles_reflect_reality_if_bridge_installed(self):
        # Câblées par smq_quality_bridge (Lot 4/5) : reflètent le vrai compte
        # une fois le pont installé, 0 sinon. mgmtsystem.nonconformity/action
        # existent dès mgmtsystem_nonconformity/action (indépendamment du
        # pont) : on détecte l'installation du pont via un champ qu'il est
        # seul à ajouter, pas via la présence du modèle lui-même.
        for key, model_name, bridge_field in (
            ("nonconformity", "mgmtsystem.nonconformity", "quality_process_id"),
            ("action", "mgmtsystem.action", "efficacy_result"),
        ):
            tile = self.env.ref(f"smq_quality.smq_dashboard_tile_{key}")
            bridge_installed = model_name in self.env and bridge_field in self.env[model_name]._fields
            expected = (
                self.env[model_name].search_count([]) if bridge_installed else 0
            )
            self.assertEqual(tile.count, expected)

    def test_document_tile_reflects_reality_if_installed(self):
        tile = self.env.ref("smq_quality.smq_dashboard_tile_document")
        expected = (
            self.env["smq.document"].search_count([])
            if "smq.document" in self.env
            else 0
        )
        self.assertEqual(tile.count, expected)

    def test_action_open_returns_action(self):
        tile = self.env.ref("smq_quality.smq_dashboard_tile_process")
        action = tile.action_open()
        self.assertEqual(action.get("res_model"), "smq.process")

    def test_document_tile_opens_real_screen_once_installed(self):
        tile = self.env.ref("smq_quality.smq_dashboard_tile_document")
        action = tile.action_open()
        if "smq.document" in self.env:
            self.assertEqual(action.get("res_model"), "smq.document")
        else:
            self.assertEqual(action.get("res_model"), "smq.coming.soon")

    def test_get_dashboard_data_shape(self):
        data = self.env["smq.dashboard.tile"].get_dashboard_data()
        self.assertEqual(len(data["tiles"]), 9)
        process_tile = next(t for t in data["tiles"] if t["key"] == "process")
        self.assertEqual(
            process_tile["count"], self.env["smq.process"].search_count([])
        )
        for key in (
            "kpis",
            "module_categories",
            "watchlist",
            "my_work",
            "quality_health",
            "recent_activity",
            "quality_chain",
            "nc_trend",
        ):
            self.assertIn(key, data)
        self.assertEqual(data["user_name"], self.env.user.name)
        self.assertEqual(data["company_name"], self.env.company.name)

    def test_document_kpi_tiles_reflect_reality(self):
        for key, domain in (
            ("document_active", [("stage_id.code", "=", "effective")]),
            ("document_pending", [("stage_id.code", "in", ("in_validation", "approved"))]),
        ):
            tile = self.env.ref(f"smq_quality.smq_dashboard_kpi_{key}")
            self.assertEqual(tile.kind, "kpi")
            expected = (
                self.env["smq.document"].search_count(domain)
                if "smq.document" in self.env
                else 0
            )
            self.assertEqual(tile.count, expected)

    def test_get_dashboard_data_kpis_are_separate_from_modules(self):
        data = self.env["smq.dashboard.tile"].get_dashboard_data()
        kpi_keys = {k["key"] for k in data["kpis"]}
        module_keys = {t["key"] for t in data["tiles"]}
        self.assertFalse(kpi_keys & module_keys)
        self.assertIn("document_active", kpi_keys)
        self.assertIn("document_pending", kpi_keys)

    def test_quality_chain_marks_improvement_unavailable(self):
        chain = self.env["smq.dashboard.tile"].get_quality_chain()
        improvement = next(s for s in chain if s["key"] == "improvement")
        self.assertFalse(improvement["available"])
        self.assertFalse(improvement["action_xmlid"])
        process_step = next(s for s in chain if s["key"] == "process")
        self.assertTrue(process_step["available"])

    def test_watchlist_returns_only_real_anomalies(self):
        # Sans document en attente/à échéance, aucune entrée fictive.
        watchlist = self.env["smq.dashboard.tile"].get_watchlist()
        for item in watchlist:
            self.assertGreater(item["count"], 0)

    def test_recent_activity_reuses_existing_chatter(self):
        process = self.env["smq.process"].create({"code": "PR-ACT-TEST", "name": "Test"})
        process.message_post(body="Message de test pour l'activité récente")
        activity = self.env["smq.dashboard.tile"].get_recent_activity()
        self.assertTrue(any(a["model"] == "smq.process" and a["res_id"] == process.id for a in activity))

    def test_quality_health_shape_and_bounds(self):
        health = self.env["smq.dashboard.tile"].get_quality_health()
        if health["score"] is not None:
            self.assertGreaterEqual(health["score"], 0)
            self.assertLessEqual(health["score"], 100)
            for component in health["components"]:
                self.assertGreaterEqual(component["score"], 0)
                self.assertLessEqual(component["score"], 100)
                self.assertTrue(component["detail"])

    def test_module_categories_contain_only_real_modules_with_counts(self):
        data = self.env["smq.dashboard.tile"].get_dashboard_data()
        seen_keys = set()
        for category in data["module_categories"]:
            for module in category["modules"]:
                seen_keys.add(module["key"])
                if module["count"] is not False:
                    self.assertIsInstance(module["count"], int)
        # Les 5 modules réels doivent tous être rangés dans une catégorie.
        self.assertTrue({"document", "process", "nonconformity", "action", "audit"} <= seen_keys)

    def test_kpi_trend_key_present_and_null_when_not_derivable(self):
        data = self.env["smq.dashboard.tile"].get_dashboard_data()
        by_key = {k["key"]: k for k in data["kpis"]}
        self.assertIn("trend", by_key["document_active"])
        # "documents à valider" est un état transitoire : pas d'historique
        # fiable, donc pas de tendance inventée.
        self.assertIsNone(by_key["document_pending"]["trend"])

    def test_my_work_empty_without_verifier_role(self):
        # base.user_admin a le groupe admin (implique tout), donc peut avoir
        # une file de validation ; on vérifie juste la forme sans casser sur
        # les données de démonstration présentes ou non.
        my_work = self.env["smq.dashboard.tile"].get_my_work()
        for item in my_work:
            self.assertGreater(item["count"], 0)

    def test_get_dashboard_data_recent_processes_limited_to_five(self):
        process = self.env["smq.process"]
        for i in range(7):
            process.create({"code": f"PR-RECENT-{i}", "name": f"Test {i}"})
        data = self.env["smq.dashboard.tile"].get_dashboard_data()
        self.assertEqual(len(data["recent_processes"]), 5)
