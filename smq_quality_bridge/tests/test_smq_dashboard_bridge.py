from odoo.tests.common import TransactionCase


class TestSmqDashboardBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.quality_manager = cls.env.ref("base.user_admin")
        cls.process = cls.env["smq.process"].create({"code": "PR-DASH-BRIDGE", "name": "Test"})

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.quality_manager)

    def test_kpi_tiles_reflect_reality(self):
        NC = self.env["mgmtsystem.nonconformity"]
        before = NC.search_count([("state", "not in", ("done", "cancel"))])
        NC.create(
            {
                "name": "NC dashboard test",
                "description": "Test",
                "quality_process_id": self.process.id,
                "origin_ids": [(4, self.env.ref("mgmtsystem_nonconformity.nc_origin_process").id)],
            }
        )
        tile = self.env.ref("smq_quality_bridge.smq_dashboard_kpi_nc_open")
        self.assertEqual(tile.kind, "kpi")
        self.assertEqual(tile.count, before + 1)

    def test_quality_chain_nc_action_audit_available(self):
        chain = self.env["smq.dashboard.tile"].get_quality_chain()
        by_key = {s["key"]: s for s in chain}
        for key in ("audit", "nonconformity", "action"):
            self.assertTrue(by_key[key]["available"])
            self.assertTrue(by_key[key]["action_xmlid"])

    def test_watchlist_includes_critical_nc_with_named_records(self):
        nc = self.env["mgmtsystem.nonconformity"].create(
            {
                "name": "NC critique test",
                "description": "Test",
                "quality_process_id": self.process.id,
                "origin_ids": [(4, self.env.ref("mgmtsystem_nonconformity.nc_origin_process").id)],
                "priority": "3",
            }
        )
        watchlist = self.env["smq.dashboard.tile"].get_watchlist()
        critical_item = next(
            item for item in watchlist if item["label"] == "non-conformités critiques ouvertes"
        )
        self.assertGreater(critical_item["count"], 0)
        self.assertTrue(critical_item["records"])
        self.assertTrue(
            any(r["res_id"] == nc.id and r["model"] == "mgmtsystem.nonconformity" for r in critical_item["records"])
        )
        for item in watchlist:
            self.assertGreater(item["count"], 0)

    def test_quality_health_includes_nc_action_audit_components(self):
        health = self.env["smq.dashboard.tile"].get_quality_health()
        keys = {c["key"] for c in health["components"]}
        self.assertTrue({"nonconformity", "action", "audit"} <= keys)
        self.assertIsNotNone(health["score"])

    def test_get_my_work_counts_only_own_records(self):
        other_user = self.env["res.users"].create(
            {
                "name": "Autre utilisateur",
                "login": "autre.dashboard@example.com",
                "groups_id": [(6, 0, [self.env.ref("smq_quality.group_smq_admin").id])],
            }
        )
        self.env["mgmtsystem.nonconformity"].create(
            {
                "name": "NC autre utilisateur",
                "description": "Test",
                "quality_process_id": self.process.id,
                "origin_ids": [(4, self.env.ref("mgmtsystem_nonconformity.nc_origin_process").id)],
                "responsible_user_id": other_user.id,
                "manager_user_id": other_user.id,
            }
        )
        my_work_other = self.env["smq.dashboard.tile"].with_user(other_user).get_my_work()
        nc_item = next((i for i in my_work_other if i["key"] == "nc_mine"), None)
        self.assertIsNotNone(nc_item)
        self.assertGreaterEqual(nc_item["count"], 1)

    def test_nc_trend_shape(self):
        buckets = self.env["smq.dashboard.tile"].get_nc_trend(months=3)
        self.assertEqual(len(buckets), 3)
        for bucket in buckets:
            self.assertIn("opened", bucket)
            self.assertIn("closed", bucket)
            self.assertGreaterEqual(bucket["opened"], 0)

    def test_recent_activity_includes_bridge_models(self):
        NC = self.env["mgmtsystem.nonconformity"].create(
            {
                "name": "NC activity test",
                "description": "Test",
                "quality_process_id": self.process.id,
                "origin_ids": [(4, self.env.ref("mgmtsystem_nonconformity.nc_origin_process").id)],
            }
        )
        NC.message_post(body="Message de test")
        activity = self.env["smq.dashboard.tile"].get_recent_activity()
        self.assertTrue(
            any(a["model"] == "mgmtsystem.nonconformity" and a["res_id"] == NC.id for a in activity)
        )
