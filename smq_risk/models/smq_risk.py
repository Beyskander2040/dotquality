from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SmqRisk(models.Model):
    _name = "smq.risk"
    _description = "SMQ Risk / Opportunity"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "risk_score desc, id desc"

    # ------------------------------------------------------------------
    # 1. Identification
    # ------------------------------------------------------------------
    reference = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("Nouveau"),
    )
    name = fields.Char(required=True, tracking=True)
    description = fields.Text()
    nature = fields.Selection(
        [("risk", "Risque"), ("opportunity", "Opportunité")],
        required=True,
        default="risk",
        tracking=True,
    )

    # ------------------------------------------------------------------
    # 2. Source
    # ------------------------------------------------------------------
    source_type_id = fields.Many2one(
        "smq.risk.source.type", string="Type de source", required=True
    )
    process_id = fields.Many2one(
        "smq.process", string="Processus porteur", required=True, tracking=True
    )
    stakeholder_id = fields.Many2one("smq.stakeholder", string="Partie intéressée")
    source_description = fields.Text(string="Description de la source")

    # ------------------------------------------------------------------
    # 3. Évaluation
    # ------------------------------------------------------------------
    probability_id = fields.Many2one(
        "smq.risk.probability", string="Probabilité", required=True
    )
    impact_id = fields.Many2one("smq.risk.impact", string="Impact", required=True)
    risk_score = fields.Integer(
        string="Score", compute="_compute_risk_score", store=True
    )
    criticality_level_id = fields.Many2one(
        "smq.risk.criticality.level",
        string="Criticité",
        compute="_compute_criticality_level_id",
        store=True,
    )

    # ------------------------------------------------------------------
    # 4. Traitement / risque résiduel
    # ------------------------------------------------------------------
    current_control_description = fields.Text(string="Mesures de maîtrise existantes")
    residual_probability_id = fields.Many2one(
        "smq.risk.probability", string="Probabilité résiduelle"
    )
    residual_impact_id = fields.Many2one(
        "smq.risk.impact", string="Impact résiduel"
    )
    residual_risk_score = fields.Integer(
        string="Score résiduel",
        compute="_compute_residual_risk_score",
        store=True,
    )

    # ------------------------------------------------------------------
    # 5. Actions (réutilisation pure de mgmtsystem.action — aucun moteur
    # d'action parallèle : la table de relation est détenue ici, l'inverse
    # est ajouté côté smq_quality_bridge, même pattern que
    # mgmtsystem.nonconformity.action_ids / mgmtsystem.action.nonconformity_ids)
    # ------------------------------------------------------------------
    action_ids = fields.Many2many(
        "mgmtsystem.action",
        "smq_risk_action_rel",
        "risk_id",
        "action_id",
        string="Actions",
    )
    action_count = fields.Integer(compute="_compute_action_count")

    # ------------------------------------------------------------------
    # 6. Statut / responsable / société
    # ------------------------------------------------------------------
    state = fields.Selection(
        [
            ("nouveau", "Nouveau"),
            ("en_traitement", "En traitement"),
            ("sous_surveillance", "Sous surveillance"),
            ("cloture", "Clôturé"),
        ],
        default="nouveau",
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company", string="Société", default=lambda self: self.env.company
    )
    responsible_user_id = fields.Many2one(
        "res.users", string="Responsable", default=lambda self: self.env.user
    )

    _sql_constraints = [
        ("reference_uniq", "unique(reference)", "La référence doit être unique."),
    ]

    # ------------------------------------------------------------------
    # Calculs
    # ------------------------------------------------------------------
    @api.depends("probability_id.value", "impact_id.value")
    def _compute_risk_score(self):
        for risk in self:
            risk.risk_score = (risk.probability_id.value or 0) * (
                risk.impact_id.value or 0
            )

    @api.depends("risk_score")
    def _compute_criticality_level_id(self):
        Level = self.env["smq.risk.criticality.level"]
        for risk in self:
            risk.criticality_level_id = (
                Level.search(
                    [
                        ("min_score", "<=", risk.risk_score),
                        ("max_score", ">=", risk.risk_score),
                    ],
                    limit=1,
                )
                if risk.risk_score
                else False
            )

    @api.depends("residual_probability_id.value", "residual_impact_id.value")
    def _compute_residual_risk_score(self):
        for risk in self:
            if risk.residual_probability_id and risk.residual_impact_id:
                risk.residual_risk_score = (
                    risk.residual_probability_id.value * risk.residual_impact_id.value
                )
            else:
                risk.residual_risk_score = False

    @api.depends("action_ids")
    def _compute_action_count(self):
        for risk in self:
            risk.action_count = len(risk.action_ids)

    # ------------------------------------------------------------------
    # Cohérence de la source (section 4 de la conception validée) :
    # process_id reste obligatoire dans tous les cas (champ required),
    # cette contrainte ne couvre que les deux cas où le champ pertinent
    # dépend du type de source choisi.
    # ------------------------------------------------------------------
    @api.constrains("source_type_id", "stakeholder_id", "source_description")
    def _check_source_consistency(self):
        for risk in self:
            code = risk.source_type_id.code
            if code == "stakeholder" and not risk.stakeholder_id:
                raise ValidationError(
                    _(
                        "Une partie intéressée doit être renseignée lorsque le "
                        "type de source est « Partie intéressée »."
                    )
                )
            if code in ("context", "other") and not risk.source_description:
                raise ValidationError(
                    _(
                        "Une description de la source est requise lorsque le "
                        "type de source est « Enjeu / contexte » ou « Autre »."
                    )
                )

    # ------------------------------------------------------------------
    # Référence auto-générée — même pattern que mgmtsystem.action.create()
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", _("Nouveau")) == _("Nouveau"):
                vals["reference"] = self.env["ir.sequence"].next_by_code(
                    "smq.risk"
                ) or _("Nouveau")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Traitement — crée une mgmtsystem.action et la relie immédiatement à
    # ce risque (le lien est posé du côté que smq_risk possède réellement,
    # sans dépendre du champ inverse ajouté par smq_quality_bridge).
    # ------------------------------------------------------------------
    def action_create_treatment_action(self):
        self.ensure_one()
        default_type_action = "prevention" if self.nature == "risk" else "improvement"
        action = self.env["mgmtsystem.action"].create(
            {
                "name": self.name,
                "type_action": default_type_action,
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
