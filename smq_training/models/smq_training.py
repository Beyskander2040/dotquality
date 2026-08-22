from odoo import _, api, fields, models


class SmqTraining(models.Model):
    _name = "smq.training"
    _description = "SMQ Training"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"

    # ------------------------------------------------------------------
    # Identification
    # ------------------------------------------------------------------
    reference = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("Nouveau"),
    )
    name = fields.Char(string="Intitulé", required=True, tracking=True)
    description = fields.Text(string="Description")
    training_type = fields.Selection(
        [
            ("interne", "Interne"),
            ("externe", "Externe"),
            ("e_learning", "E-learning"),
        ],
        string="Type de formation",
        required=True,
        default="interne",
    )
    trainer = fields.Char(string="Formateur / Organisme")
    date_start = fields.Date(string="Date de début")
    date_end = fields.Date(string="Date de fin")
    process_id = fields.Many2one("smq.process", string="Processus concerné")

    # ------------------------------------------------------------------
    # Participants et compétences visées — référence pure aux modèles RH
    # standards (hr.employee / hr.skill), aucune donnée dupliquée.
    # ------------------------------------------------------------------
    employee_ids = fields.Many2many("hr.employee", string="Participants")
    skill_ids = fields.Many2many("hr.skill", string="Compétences visées")

    # ------------------------------------------------------------------
    # Actions (réutilisation pure de mgmtsystem.action — la relation est
    # détenue ici, l'inverse est ajouté côté smq_quality_bridge, même
    # pattern que smq.risk.action_ids / smq.complaint.action_ids)
    # ------------------------------------------------------------------
    action_ids = fields.Many2many(
        "mgmtsystem.action",
        "smq_training_action_rel",
        "training_id",
        "action_id",
        string="Actions",
    )
    action_count = fields.Integer(compute="_compute_action_count")

    # ------------------------------------------------------------------
    # Évaluation d'efficacité — globale à la session en V1 (pas par
    # participant), même vocabulaire à 3 niveaux que mgmtsystem.action.
    # ------------------------------------------------------------------
    efficacy_date = fields.Datetime(string="Date de vérification")
    efficacy_result = fields.Selection(
        [
            ("effective", "Efficace"),
            ("partial", "Partiellement efficace"),
            ("ineffective", "Non efficace"),
        ],
        string="Résultat de la vérification",
    )
    efficacy_user_id = fields.Many2one("res.users", string="Vérificateur")
    efficacy_comment = fields.Text(string="Commentaire de vérification")

    # ------------------------------------------------------------------
    # Statut / responsable / société
    # ------------------------------------------------------------------
    state = fields.Selection(
        [
            ("identifiee", "Identifiée"),
            ("planifiee", "Planifiée"),
            ("realisee", "Réalisée"),
            ("evaluee", "Évaluée"),
            ("annulee", "Annulée"),
        ],
        default="identifiee",
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

    @api.depends("action_ids")
    def _compute_action_count(self):
        for training in self:
            training.action_count = len(training.action_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", _("Nouveau")) == _("Nouveau"):
                vals["reference"] = self.env["ir.sequence"].next_by_code(
                    "smq.training"
                ) or _("Nouveau")
        return super().create(vals_list)

    def action_create_treatment_action(self):
        self.ensure_one()
        action = self.env["mgmtsystem.action"].create(
            {
                "name": self.name,
                "type_action": "improvement",
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
