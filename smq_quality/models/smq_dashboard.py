from datetime import timedelta

from odoo import _, api, fields, models

# Modules encore hors périmètre : aucun modèle, donc aucune donnée — cette
# liste n'alimente que l'affichage "À venir" (icône + libellé), jamais un
# compteur ni une donnée métier. "category" les range dans les mêmes
# groupes que les modules réels pour la section "Modules SMQ".
_FUTURE_MODULES = [
    {"key": "revision", "name": "Révisions", "icon": "fa-refresh", "category": "documentation"},
    {"key": "objectives", "name": "Objectifs qualité", "icon": "fa-bullseye", "category": "performance"},
    {"key": "kpi", "name": "Indicateurs / KPI", "icon": "fa-line-chart", "category": "performance"},
    {"key": "risk", "name": "Risques & opportunités", "icon": "fa-exclamation-circle", "category": "risk_compliance"},
    {"key": "improvement", "name": "Amélioration continue", "icon": "fa-arrow-up", "category": "audit_improvement"},
]

# Regroupement de la section "Modules SMQ" : chaque module réel (clé de
# _COUNTERS) est rangé dans une des mêmes 5 catégories que les modules à
# venir, plutôt que d'afficher 12 cartes de poids visuel identique.
_MODULE_CATEGORIES = [
    ("documentation", "Documentation"),
    ("performance", "Performance & Processus"),
    ("risk_compliance", "Risques & Conformité"),
    ("audit_improvement", "Audit & Amélioration"),
    ("stakeholders", "Parties intéressées"),
]
_MODULE_CATEGORY_BY_KEY = {
    "document": "documentation",
    "process": "performance",
    "nonconformity": "risk_compliance",
    "action": "risk_compliance",
    "audit": "audit_improvement",
    "management_review": "audit_improvement",
    "complaint": "stakeholders",
    "training": "stakeholders",
    "supplier": "stakeholders",
}

# Chaîne qualité affichée sur le dashboard : chaque étape n'est cliquable
# que si le modèle qu'elle représente est réellement installé (vérifié à
# l'exécution, jamais supposé). "Constats" n'a pas de modèle dédié (c'est
# une checklist intégrée à l'audit) et n'apparaît donc pas comme étape
# séparée ; "Amélioration" reste affichée grisée, sans modèle.
_QUALITY_CHAIN = [
    ("process", "Processus", "smq.process", "smq_quality.action_smq_process"),
    ("document", "Documents", "smq.document", "smq_document.action_smq_document"),
    ("audit", "Audits", "mgmtsystem.audit", "smq_quality_bridge.action_smq_audit"),
    ("nonconformity", "Non-conformités", "mgmtsystem.nonconformity", "smq_quality_bridge.action_smq_nonconformity"),
    ("action", "Actions correctives", "mgmtsystem.action", "smq_quality_bridge.action_smq_corrective_action"),
    ("improvement", "Amélioration", False, False),
]


class SmqDashboardTile(models.Model):
    _name = "smq.dashboard.tile"
    _description = "SMQ Dashboard Tile"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    key = fields.Char(required=True)
    name = fields.Char(required=True)
    icon = fields.Char(default="fa-square-o")
    action_xmlid = fields.Char()
    kind = fields.Selection(
        [("module", "Module"), ("kpi", "Indicateur")],
        default="module",
        required=True,
        help="Module : carte de la section 'Modules SMQ'. Indicateur : KPI de la ligne d'en-tête du dashboard.",
    )
    count = fields.Integer(compute="_compute_count")

    # NC/Actions/Audits restent à 0 tant que smq_quality_bridge (Lot 4/5) n'existe
    # pas : ces modules OCA sont déjà installés et peuvent contenir des données
    # réelles mais sans lien avec un processus SMQ, ce serait trompeur de les
    # afficher ici avant que le pont existe.
    # "document" utilise le même mécanisme défensif (model_name not in self.env) :
    # smq_quality ne dépend pas de smq_document, mais affiche son vrai chiffre
    # dès qu'il est installé, sans avoir à modifier ce fichier plus tard.
    _COUNTERS = {
        "process": ("smq.process", []),
        "document": ("smq.document", []),
        "nonconformity": (None, []),
        "action": (None, []),
        "audit": (None, []),
    }

    # Indicateurs de la ligne d'en-tête (kind='kpi') : modèle propriétaire de
    # chaque clé. Le domaine réel est construit par _get_domain() car certains
    # ont besoin de la date du jour (non exprimable dans un tuple statique).
    _KPI_MODEL_BY_KEY = {
        "document_active": "smq.document",
        "document_pending": "smq.document",
    }

    @api.depends("key", "kind")
    def _compute_count(self):
        for rec in self:
            rec.count = rec._get_count()

    def _get_domain(self):
        """Domaine de comptage pour les clés possédées par ce module.
        Toujours rappeler super() en cascade pour les clés non reconnues
        (mêmes principe que _get_count/_get_action_xmlid ci-dessous)."""
        self.ensure_one()
        if self.key == "document_active":
            return [("stage_id.code", "=", "effective")]
        if self.key == "document_pending":
            return [("stage_id.code", "in", ("in_validation", "approved"))]
        return []

    def _get_count(self):
        self.ensure_one()
        if self.kind == "kpi":
            model_name = self._KPI_MODEL_BY_KEY.get(self.key)
            if not model_name or model_name not in self.env:
                return 0
            return self.env[model_name].search_count(self._get_domain())
        model_name, domain = self._COUNTERS.get(self.key, (None, []))
        if not model_name or model_name not in self.env:
            return 0
        return self.env[model_name].search_count(domain)

    # ------------------------------------------------------------------
    # Tendance à 30 jours — uniquement pour les clés où l'historique est
    # honnêtement reconstituable à partir de champs déjà stockés (dates
    # d'effet/clôture). Retourne None (pas de tendance affichée) plutôt que
    # d'inventer un chiffre quand ce n'est pas fiable (ex. "documents en
    # attente" ou "audits à venir" sont des états transitoires sans trace
    # historique exploitable).
    # ------------------------------------------------------------------
    def _get_previous_count(self):
        self.ensure_one()
        if self.key == "document_active" and "smq.document.version" in self.env:
            cutoff = fields.Date.context_today(self) - timedelta(days=30)
            return self.env["smq.document.version"].search_count(
                [
                    ("effective_date", "!=", False),
                    ("effective_date", "<=", cutoff),
                    "|",
                    ("obsolete_date", "=", False),
                    ("obsolete_date", ">", cutoff),
                ]
            )
        return None

    # Une fois le modèle réel installé, la tuile doit pointer sur son vrai
    # écran plutôt que sur l'action "à venir" figée dans les données de démo.
    # NC/Actions/Audits rejoindront cette table au Lot 4/5 — un seul endroit
    # à modifier, ni le champ action_xmlid ni les données ne bougent.
    _UPGRADED_ACTIONS = {
        "document": ("smq.document", "smq_document.action_smq_document"),
    }
    # Idem pour les KPI dont l'action réelle appartient à un module optionnel
    # (smq_quality ne dépend pas de smq_document) : on ne stocke jamais un
    # xmlid d'un autre module directement en donnée, on le résout ici, de
    # façon défensive, comme pour _UPGRADED_ACTIONS ci-dessus.
    _KPI_ACTION_XMLIDS = {
        "document_active": ("smq.document", "smq_document.action_smq_document_effective"),
        "document_pending": ("smq.document", "smq_document.action_smq_document_in_validation"),
    }

    def _get_action_xmlid(self):
        self.ensure_one()
        if self.kind == "kpi":
            model_name, xmlid = self._KPI_ACTION_XMLIDS.get(self.key, (None, None))
            if model_name and model_name in self.env:
                return xmlid
            return self.action_xmlid
        model_name, xmlid = self._UPGRADED_ACTIONS.get(self.key, (None, None))
        if model_name and model_name in self.env:
            return xmlid
        return self.action_xmlid

    def action_open(self):
        self.ensure_one()
        xmlid = self._get_action_xmlid()
        if not xmlid:
            return False
        return self.env["ir.actions.act_window"]._for_xml_id(xmlid)

    # ------------------------------------------------------------------
    # Priorités (ex "À surveiller") — un item par anomalie réelle détectée,
    # jamais de valeur statique, avec le détail des enregistrements
    # concernés (nom, responsable, échéance) pour rester actionnable et pas
    # seulement informatif. Chaque module ajoute les siens via super().
    # ------------------------------------------------------------------
    def _document_brief(self, doc, deadline_field=None):
        return {
            "name": f"{doc.code} — {doc.name}" if doc.code else doc.name,
            "model": "smq.document",
            "res_id": doc.id,
            "responsible": doc.responsible_id.name or "",
            "deadline": doc[deadline_field] if deadline_field else False,
        }

    @api.model
    def get_watchlist(self):
        items = []
        if "smq.document" in self.env:
            Document = self.env["smq.document"]
            pending_docs = Document.search(
                [("stage_id.code", "in", ("in_validation", "approved"))],
                order="write_date desc",
                limit=3,
            )
            if pending_docs:
                items.append(
                    {
                        "level": "warning",
                        "label": _("documents en attente de validation"),
                        "count": Document.search_count(
                            [("stage_id.code", "in", ("in_validation", "approved"))]
                        ),
                        "action_xmlid": "smq_document.action_smq_document_in_validation",
                        "records": [self._document_brief(d) for d in pending_docs],
                    }
                )
            today = fields.Date.context_today(self)
            soon_domain = [
                ("next_review_date", "!=", False),
                ("next_review_date", "<=", today + timedelta(days=30)),
            ]
            soon_docs = Document.search(soon_domain, order="next_review_date", limit=3)
            if soon_docs:
                items.append(
                    {
                        "level": "info",
                        "label": _("documents arrivant à échéance de révision (30 j)"),
                        "count": Document.search_count(soon_domain),
                        "action_xmlid": "smq_document.action_smq_document_all",
                        "records": [
                            self._document_brief(d, "next_review_date") for d in soon_docs
                        ],
                    }
                )
        return items

    # ------------------------------------------------------------------
    # Mes tâches — compteurs personnels réels (filtrés sur l'utilisateur
    # courant), pas une simple répétition des KPI globaux. smq_quality ne
    # connaissant aucun champ d'assignation individuelle sur smq.document
    # (aucun validateur nommé n'existe sur le modèle), on ne peut
    # honnêtement personnaliser que par rôle : la file de validation
    # partagée n'est montrée qu'aux utilisateurs pouvant réellement agir.
    # ------------------------------------------------------------------
    @api.model
    def get_my_work(self):
        items = []
        if "smq.document" in self.env and self.env.user.has_group(
            "smq_quality.group_smq_verifier"
        ):
            count = self.env["smq.document"].search_count(
                [("stage_id.code", "in", ("in_validation", "approved"))]
            )
            if count:
                items.append(
                    {
                        "key": "doc_pending",
                        "label": _("Documents à valider"),
                        "count": count,
                        "action_xmlid": "smq_document.action_smq_document_in_validation",
                    }
                )
        return items

    # ------------------------------------------------------------------
    # Score de santé qualité — moyenne de composantes réelles et explicites
    # (jamais un chiffre décoratif) : chaque composante est un pourcentage
    # de maîtrise (1 - anomalies / total pertinent), avec son détail.
    # ------------------------------------------------------------------
    def _get_health_components(self):
        components = []
        if "smq.document" in self.env:
            Document = self.env["smq.document"]
            active = Document.search_count([("stage_id.code", "=", "effective")])
            today = fields.Date.context_today(self)
            overdue = Document.search_count(
                [
                    ("stage_id.code", "=", "effective"),
                    ("next_review_date", "!=", False),
                    ("next_review_date", "<", today),
                ]
            )
            score = 100 if not active else round(100 * (1 - overdue / active))
            components.append(
                {
                    "key": "document",
                    "label": _("Documents maîtrisés"),
                    "score": score,
                    "detail": _(
                        "%(overdue)s document(s) en retard de révision sur %(active)s actifs"
                    )
                    % {"overdue": overdue, "active": active},
                }
            )
        return components

    @api.model
    def get_quality_health(self):
        components = self._get_health_components()
        if not components:
            return {"score": None, "label": "", "components": []}
        score = round(sum(c["score"] for c in components) / len(components))
        if score >= 85:
            label = _("Système globalement maîtrisé")
        elif score >= 60:
            label = _("Vigilance requise")
        else:
            label = _("Action requise")
        return {"score": score, "label": label, "components": components}

    # ------------------------------------------------------------------
    # Activité récente — réutilise le chatter (mail.message) déjà posté par
    # les modèles existants (mail.thread) : aucun nouveau système d'activité.
    # ------------------------------------------------------------------
    def _get_activity_models(self):
        return [m for m in ("smq.process",) if m in self.env]

    @api.model
    def get_recent_activity(self, limit=8):
        models_list = self._get_activity_models()
        if not models_list:
            return []
        messages = self.env["mail.message"].search(
            [
                ("model", "in", models_list),
                ("res_id", "!=", False),
                ("message_type", "!=", "user_notification"),
            ],
            order="date desc",
            limit=limit,
        )
        return [
            {
                "id": message.id,
                "record_name": message.record_name or message.model,
                "model": message.model,
                "res_id": message.res_id,
                "date": message.date,
                "author": message.author_id.name or "",
            }
            for message in messages
        ]

    # ------------------------------------------------------------------
    # Chaîne qualité — étapes statiques, cliquabilité vérifiée à l'exécution,
    # complétées d'une courte statistique réelle par étape.
    # ------------------------------------------------------------------
    def _get_chain_stats(self, key):
        if key == "process" and "smq.process" in self.env:
            total = self.env["smq.process"].search_count([])
            return _("%s processus") % total
        if key == "document" and "smq.document" in self.env:
            Document = self.env["smq.document"]
            active = Document.search_count([("stage_id.code", "=", "effective")])
            pending = Document.search_count(
                [("stage_id.code", "in", ("in_validation", "approved"))]
            )
            return _("%(active)s actifs · %(pending)s à valider") % {
                "active": active,
                "pending": pending,
            }
        return ""

    @api.model
    def get_quality_chain(self):
        chain = []
        for key, label, model_name, action_xmlid in _QUALITY_CHAIN:
            available = bool(model_name) and model_name in self.env
            chain.append(
                {
                    "key": key,
                    "label": label,
                    "available": available,
                    "action_xmlid": action_xmlid if available else False,
                    "stats": self._get_chain_stats(key) if available else "",
                }
            )
        return chain

    # ------------------------------------------------------------------
    # Graphique NC ouvertes/clôturées par mois — surchargé par le pont
    # (seul à connaître mgmtsystem.nonconformity) ; vide par défaut.
    # ------------------------------------------------------------------
    @api.model
    def get_nc_trend(self, months=6):
        return []

    @api.model
    def get_dashboard_data(self):
        """Payload consommé par le composant OWL du tableau de bord SMQ."""
        tiles = self.search([], order="sequence, id")

        def _tile_payload(tile):
            payload = {
                "key": tile.key,
                "name": tile.name,
                "icon": tile.icon,
                "count": tile.count,
                "action_xmlid": tile._get_action_xmlid(),
            }
            if tile.kind == "kpi":
                previous = tile._get_previous_count()
                payload["trend"] = (tile.count - previous) if previous is not None else None
            return payload

        modules = [_tile_payload(t) for t in tiles if t.kind == "module"]
        kpis = [_tile_payload(t) for t in tiles if t.kind == "kpi"]

        module_categories = []
        for cat_key, cat_label in _MODULE_CATEGORIES:
            cards = [m for m in modules if _MODULE_CATEGORY_BY_KEY.get(m["key"]) == cat_key]
            cards += [
                {
                    "key": f["key"],
                    "name": f["name"],
                    "icon": f["icon"],
                    "count": False,
                    "action_xmlid": False,
                }
                for f in _FUTURE_MODULES
                if f["category"] == cat_key
            ]
            if cards:
                module_categories.append({"key": cat_key, "label": cat_label, "modules": cards})

        process = self.env["smq.process"]
        recent_processes = process.search([], order="create_date desc", limit=5)
        status_selection = dict(process.fields_get(["status"])["status"]["selection"])
        processes_data = [
            {
                "code": proc.code,
                "name": proc.name,
                "category": proc.category_id.name or "",
                "responsible": proc.responsible_id.name or "",
                "status": proc.status,
                "status_label": status_selection.get(proc.status, proc.status),
            }
            for proc in recent_processes
        ]

        return {
            "tiles": modules,
            "kpis": kpis,
            "recent_processes": processes_data,
            "module_categories": module_categories,
            "watchlist": self.get_watchlist(),
            "my_work": self.get_my_work(),
            "quality_health": self.get_quality_health(),
            "recent_activity": self.get_recent_activity(),
            "quality_chain": self.get_quality_chain(),
            "nc_trend": self.get_nc_trend(),
            "user_name": self.env.user.name,
            "company_name": self.env.company.name,
        }


class SmqComingSoon(models.Model):
    _name = "smq.coming.soon"
    _description = "SMQ - Section en construction"
