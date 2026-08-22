from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, fields, models

# Câblage prévu depuis smq_quality (cf. commentaire sur _COUNTERS/_UPGRADED_ACTIONS
# dans smq_quality/models/smq_dashboard.py) : NC, Actions et Audits pointent
# maintenant vers de vrais écrans avec de vrais compteurs.
_MODEL_BY_KEY = {
    "nonconformity": "mgmtsystem.nonconformity",
    "action": "mgmtsystem.action",
    "audit": "mgmtsystem.audit",
    "management_review": "mgmtsystem.review",
    # Indicateurs de la ligne d'en-tête (kind='kpi') — même modèle que les
    # tuiles "module" ci-dessus, mais avec un domaine réel plutôt que [].
    "nc_open": "mgmtsystem.nonconformity",
    "action_late": "mgmtsystem.action",
    "audit_upcoming": "mgmtsystem.audit",
}
_ACTION_XMLID_BY_KEY = {
    "nonconformity": "smq_quality_bridge.action_smq_nonconformity",
    "action": "smq_quality_bridge.action_smq_corrective_action",
    "audit": "smq_quality_bridge.action_smq_audit",
    "management_review": "smq_quality_bridge.action_smq_management_review",
    "nc_open": "smq_quality_bridge.action_smq_nonconformity",
    "action_late": "smq_quality_bridge.action_smq_corrective_action",
    "audit_upcoming": "smq_quality_bridge.action_smq_audit",
}


class SmqDashboardTile(models.Model):
    _inherit = "smq.dashboard.tile"

    def _get_domain(self):
        self.ensure_one()
        if self.key == "nc_open":
            return [("state", "not in", ("done", "cancel"))]
        if self.key == "action_late":
            today = fields.Date.context_today(self)
            return [("date_deadline", "<", today), ("stage_id.is_ending", "=", False)]
        if self.key == "audit_upcoming":
            return [("state", "=", "open")]
        return super()._get_domain()

    def _get_count(self):
        self.ensure_one()
        model_name = _MODEL_BY_KEY.get(self.key)
        if model_name:
            return self.env[model_name].search_count(self._get_domain())
        return super()._get_count()

    def _get_previous_count(self):
        self.ensure_one()
        cutoff = fields.Date.context_today(self) - timedelta(days=30)
        if self.key == "nc_open":
            return self.env["mgmtsystem.nonconformity"].search_count(
                [
                    ("create_date", "<=", cutoff),
                    "|",
                    ("closing_date", "=", False),
                    ("closing_date", ">", cutoff),
                ]
            )
        if self.key == "action_late":
            return self.env["mgmtsystem.action"].search_count(
                [
                    ("date_deadline", "<", cutoff),
                    "|",
                    ("date_closed", "=", False),
                    ("date_closed", ">", cutoff),
                ]
            )
        # "audits à venir" est une notion tournée vers l'avenir : comparer à
        # il y a 30 jours n'a pas de sens, on n'affiche donc pas de tendance.
        return super()._get_previous_count()

    def _get_action_xmlid(self):
        self.ensure_one()
        xmlid = _ACTION_XMLID_BY_KEY.get(self.key)
        if xmlid:
            return xmlid
        return super()._get_action_xmlid()

    def _nc_brief(self, nc):
        return {
            "name": f"{nc.ref} — {nc.name}" if nc.ref else nc.name,
            "model": "mgmtsystem.nonconformity",
            "res_id": nc.id,
            "responsible": nc.responsible_user_id.name or "",
            "deadline": False,
        }

    def _action_brief(self, action):
        return {
            "name": f"{action.reference} — {action.name}" if action.reference else action.name,
            "model": "mgmtsystem.action",
            "res_id": action.id,
            "responsible": action.user_id.name or "",
            "deadline": action.date_deadline,
        }

    def _audit_brief(self, audit):
        return {
            "name": f"{audit.reference} — {audit.name}" if audit.reference else audit.name,
            "model": "mgmtsystem.audit",
            "res_id": audit.id,
            "responsible": audit.user_id.name or "",
            "deadline": fields.Date.to_date(audit.date) if audit.date else False,
        }

    def get_watchlist(self):
        items = super().get_watchlist()
        today = fields.Date.context_today(self)

        NC = self.env["mgmtsystem.nonconformity"]
        critical_domain = [("state", "not in", ("done", "cancel")), ("priority", "=", "3")]
        critical_records = NC.search(critical_domain, order="write_date desc", limit=3)
        if critical_records:
            items.append(
                {
                    "level": "critical",
                    "label": _("non-conformités critiques ouvertes"),
                    "count": NC.search_count(critical_domain),
                    "action_xmlid": "smq_quality_bridge.action_smq_nonconformity",
                    "records": [self._nc_brief(nc) for nc in critical_records],
                }
            )

        Action = self.env["mgmtsystem.action"]
        late_domain = [("date_deadline", "<", today), ("stage_id.is_ending", "=", False)]
        late_records = Action.search(late_domain, order="date_deadline", limit=3)
        if late_records:
            items.append(
                {
                    "level": "critical",
                    "label": _("actions correctives en retard"),
                    "count": Action.search_count(late_domain),
                    "action_xmlid": "smq_quality_bridge.action_smq_corrective_action",
                    "records": [self._action_brief(a) for a in late_records],
                }
            )

        Audit = self.env["mgmtsystem.audit"]
        week_end = today + timedelta(days=7)
        upcoming_domain = [
            ("state", "=", "open"),
            ("date", "!=", False),
            ("date", ">=", today),
            ("date", "<", week_end + timedelta(days=1)),
        ]
        upcoming_records = Audit.search(upcoming_domain, order="date", limit=3)
        if upcoming_records:
            items.append(
                {
                    "level": "warning",
                    "label": _("audit prévu dans les 7 prochains jours"),
                    "count": Audit.search_count(upcoming_domain),
                    "action_xmlid": "smq_quality_bridge.action_smq_audit",
                    "records": [self._audit_brief(a) for a in upcoming_records],
                }
            )
        return items

    def get_my_work(self):
        items = super().get_my_work()
        uid = self.env.uid
        today = fields.Date.context_today(self)

        NC = self.env["mgmtsystem.nonconformity"]
        nc_mine = NC.search_count(
            [
                ("state", "not in", ("done", "cancel")),
                "|",
                ("responsible_user_id", "=", uid),
                ("manager_user_id", "=", uid),
            ]
        )
        if nc_mine:
            items.append(
                {
                    "key": "nc_mine",
                    "label": _("Non-conformités à traiter"),
                    "count": nc_mine,
                    "action_xmlid": "smq_quality_bridge.action_smq_nonconformity",
                }
            )

        Action = self.env["mgmtsystem.action"]
        action_mine = Action.search_count(
            [("user_id", "=", uid), ("stage_id.is_ending", "=", False)]
        )
        if action_mine:
            action_late_mine = Action.search_count(
                [
                    ("user_id", "=", uid),
                    ("stage_id.is_ending", "=", False),
                    ("date_deadline", "<", today),
                ]
            )
            items.append(
                {
                    "key": "action_mine",
                    "label": _("Mes actions en cours"),
                    "count": action_mine,
                    "action_xmlid": "smq_quality_bridge.action_smq_corrective_action",
                    "sub_label": (
                        _("dont %s en retard") % action_late_mine if action_late_mine else ""
                    ),
                }
            )

        Audit = self.env["mgmtsystem.audit"]
        audit_mine = Audit.search_count(
            ["&", ("state", "=", "open"), "|", ("user_id", "=", uid), ("auditor_user_ids", "in", uid)]
        )
        if audit_mine:
            items.append(
                {
                    "key": "audit_mine",
                    "label": _("Mes audits ouverts"),
                    "count": audit_mine,
                    "action_xmlid": "smq_quality_bridge.action_smq_audit",
                }
            )
        return items

    def _get_health_components(self):
        components = super()._get_health_components()
        today = fields.Date.context_today(self)

        NC = self.env["mgmtsystem.nonconformity"]
        open_nc = NC.search_count([("state", "not in", ("done", "cancel"))])
        critical_nc = NC.search_count(
            [("state", "not in", ("done", "cancel")), ("priority", "=", "3")]
        )
        nc_score = 100 if not open_nc else round(100 * (1 - critical_nc / open_nc))
        components.append(
            {
                "key": "nonconformity",
                "label": _("Non-conformités maîtrisées"),
                "score": nc_score,
                "detail": _("%(critical)s critique(s) sur %(open)s ouverte(s)")
                % {"critical": critical_nc, "open": open_nc},
            }
        )

        Action = self.env["mgmtsystem.action"]
        open_action = Action.search_count([("stage_id.is_ending", "=", False)])
        late_action = Action.search_count(
            [("stage_id.is_ending", "=", False), ("date_deadline", "<", today)]
        )
        action_score = 100 if not open_action else round(100 * (1 - late_action / open_action))
        components.append(
            {
                "key": "action",
                "label": _("Actions dans les délais"),
                "score": action_score,
                "detail": _("%(late)s en retard sur %(open)s en cours")
                % {"late": late_action, "open": open_action},
            }
        )

        Audit = self.env["mgmtsystem.audit"]
        open_audit = Audit.search_count([("state", "=", "open")])
        overdue_audit = Audit.search_count(
            [("state", "=", "open"), ("date", "!=", False), ("date", "<", today)]
        )
        audit_score = 100 if not open_audit else round(100 * (1 - overdue_audit / open_audit))
        components.append(
            {
                "key": "audit",
                "label": _("Audits à jour"),
                "score": audit_score,
                "detail": _("%(overdue)s en retard sur %(open)s ouvert(s)")
                % {"overdue": overdue_audit, "open": open_audit},
            }
        )
        return components

    def _get_activity_models(self):
        return super()._get_activity_models() + [
            m
            for m in (
                "smq.document.version",
                "mgmtsystem.nonconformity",
                "mgmtsystem.action",
                "mgmtsystem.audit",
            )
            if m in self.env
        ]

    def _get_chain_stats(self, key):
        NC = self.env["mgmtsystem.nonconformity"]
        Action = self.env["mgmtsystem.action"]
        Audit = self.env["mgmtsystem.audit"]
        if key == "nonconformity":
            open_nc = NC.search_count([("state", "not in", ("done", "cancel"))])
            critical_nc = NC.search_count(
                [("state", "not in", ("done", "cancel")), ("priority", "=", "3")]
            )
            return _("%(open)s ouvertes · %(critical)s critiques") % {
                "open": open_nc,
                "critical": critical_nc,
            }
        if key == "action":
            today = fields.Date.context_today(self)
            open_action = Action.search_count([("stage_id.is_ending", "=", False)])
            late_action = Action.search_count(
                [("stage_id.is_ending", "=", False), ("date_deadline", "<", today)]
            )
            return _("%(open)s ouvertes · %(late)s en retard") % {
                "open": open_action,
                "late": late_action,
            }
        if key == "audit":
            done = Audit.search_count([("state", "=", "done")])
            open_audit = Audit.search_count([("state", "=", "open")])
            return _("%(done)s réalisés · %(open)s ouverts") % {"done": done, "open": open_audit}
        return super()._get_chain_stats(key)

    def get_nc_trend(self, months=6):
        NC = self.env["mgmtsystem.nonconformity"]
        today = fields.Date.context_today(self)
        buckets = []
        for i in range(months - 1, -1, -1):
            month_start = today.replace(day=1) - relativedelta(months=i)
            month_end = month_start + relativedelta(months=1)
            opened = NC.search_count(
                [("create_date", ">=", month_start), ("create_date", "<", month_end)]
            )
            closed = NC.search_count(
                [
                    ("closing_date", "!=", False),
                    ("closing_date", ">=", month_start),
                    ("closing_date", "<", month_end),
                ]
            )
            buckets.append(
                {"label": month_start.strftime("%b"), "opened": opened, "closed": closed}
            )
        return buckets
