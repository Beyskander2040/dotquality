from odoo import _, api, fields, models


class SmqSupplierEvaluation(models.Model):
    _name = "smq.supplier.evaluation"
    _description = "SMQ Supplier Evaluation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "evaluation_date desc, id desc"

    # ------------------------------------------------------------------
    # Identification — le fournisseur reste res.partner, jamais recopié.
    # ------------------------------------------------------------------
    reference = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("Nouveau"),
    )
    # Pas de domaine sur "supplier_rank" : ce champ est fourni par le
    # module "account" (Comptabilité), non installé dans ce SMQ autonome
    # (vérifié : account/purchase/sale sont désinstallés dans cet
    # environnement) — l'ajouter comme dépendance uniquement pour un filtre
    # serait disproportionné. Si "account" est installé un jour, le champ
    # redeviendra filtrable sans changement de code ici.
    partner_id = fields.Many2one(
        "res.partner",
        string="Fournisseur",
        required=True,
        tracking=True,
    )
    stakeholder_id = fields.Many2one(
        "smq.stakeholder",
        string="Partie intéressée",
        domain="[('category', '=', 'supplier')]",
    )
    evaluation_date = fields.Date(
        string="Date d'évaluation", default=fields.Date.context_today, required=True
    )

    # ------------------------------------------------------------------
    # Évaluation — critères pondérés, score global et niveau de
    # qualification calculés, même patron que smq.risk (probabilité ×
    # impact → score → criticité).
    # ------------------------------------------------------------------
    criteria_line_ids = fields.One2many(
        "smq.supplier.evaluation.line", "evaluation_id", string="Critères"
    )
    global_score = fields.Integer(
        string="Score global", compute="_compute_global_score", store=True
    )
    qualification_level_id = fields.Many2one(
        "smq.supplier.qualification.level",
        string="Niveau de qualification",
        compute="_compute_qualification_level_id",
        store=True,
    )

    # ------------------------------------------------------------------
    # Actions (réutilisation pure de mgmtsystem.action)
    # ------------------------------------------------------------------
    action_ids = fields.Many2many(
        "mgmtsystem.action",
        "smq_supplier_evaluation_action_rel",
        "evaluation_id",
        "action_id",
        string="Actions",
    )
    action_count = fields.Integer(compute="_compute_action_count")

    # ------------------------------------------------------------------
    # Statut / responsable / société
    # ------------------------------------------------------------------
    state = fields.Selection(
        [("draft", "Brouillon"), ("done", "Validée")],
        default="draft",
        required=True,
        tracking=True,
    )
    responsible_user_id = fields.Many2one(
        "res.users", string="Responsable", default=lambda self: self.env.user
    )
    company_id = fields.Many2one(
        "res.company", string="Société", default=lambda self: self.env.company
    )

    _sql_constraints = [
        ("reference_uniq", "unique(reference)", "La référence doit être unique."),
    ]

    @api.depends("criteria_line_ids.score", "criteria_line_ids.criterion_id.weight")
    def _compute_global_score(self):
        for evaluation in self:
            lines = evaluation.criteria_line_ids
            total_weight = sum(lines.mapped("criterion_id.weight"))
            if total_weight:
                weighted_sum = sum(
                    line.score * line.criterion_id.weight for line in lines
                )
                evaluation.global_score = round(weighted_sum / total_weight)
            else:
                evaluation.global_score = 0

    @api.depends("global_score")
    def _compute_qualification_level_id(self):
        Level = self.env["smq.supplier.qualification.level"]
        for evaluation in self:
            evaluation.qualification_level_id = (
                Level.search(
                    [
                        ("min_score", "<=", evaluation.global_score),
                        ("max_score", ">=", evaluation.global_score),
                    ],
                    limit=1,
                )
                if evaluation.criteria_line_ids
                else False
            )

    @api.depends("action_ids")
    def _compute_action_count(self):
        for evaluation in self:
            evaluation.action_count = len(evaluation.action_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", _("Nouveau")) == _("Nouveau"):
                vals["reference"] = self.env["ir.sequence"].next_by_code(
                    "smq.supplier.evaluation"
                ) or _("Nouveau")
        return super().create(vals_list)

    def action_validate(self):
        for evaluation in self:
            evaluation.state = "done"

    def action_create_treatment_action(self):
        self.ensure_one()
        action = self.env["mgmtsystem.action"].create(
            {
                "name": self.partner_id.name,
                "type_action": "correction",
                "user_id": self.responsible_user_id.id or self.env.user.id,
            }
        )
        self.action_ids = [(4, action.id)]
        return {
            "type": "ir.actions.act_window",
            "res_model": "mgmtsystem.action",
            "res_id": action.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_actions(self):
        self.ensure_one()
        return {
            "name": _("Actions"),
            "type": "ir.actions.act_window",
            "res_model": "mgmtsystem.action",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.action_ids.ids)],
        }
