from odoo import _, api, fields, models


class SmqComplaint(models.Model):
    _name = "smq.complaint"
    _description = "SMQ Customer Complaint"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_received desc, id desc"

    # ------------------------------------------------------------------
    # Identification
    # ------------------------------------------------------------------
    reference = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("Nouveau"),
    )
    name = fields.Char(string="Objet", required=True, tracking=True)
    description = fields.Text(string="Description", required=True)
    partner_id = fields.Many2one(
        "res.partner", string="Client", required=True, tracking=True
    )
    stakeholder_id = fields.Many2one(
        "smq.stakeholder",
        string="Partie intéressée",
        domain="[('category', '=', 'customer')]",
    )

    # ------------------------------------------------------------------
    # Réception
    # ------------------------------------------------------------------
    channel = fields.Selection(
        [
            ("email", "E-mail"),
            ("phone", "Téléphone"),
            ("mail", "Courrier"),
            ("in_person", "En personne"),
            ("other", "Autre"),
        ],
        string="Canal de réception",
        required=True,
        default="email",
    )
    date_received = fields.Datetime(
        string="Date de réception", default=fields.Datetime.now, required=True
    )
    process_id = fields.Many2one("smq.process", string="Processus concerné")
    severity = fields.Selection(
        [
            ("minor", "Mineure"),
            ("major", "Majeure"),
            ("critical", "Critique"),
        ],
        string="Sévérité",
        default="minor",
        required=True,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Traitement / réponse
    # ------------------------------------------------------------------
    response_due_date = fields.Date(string="Échéance de réponse")
    response_sent_date = fields.Datetime(string="Date d'envoi de la réponse")
    response_summary = fields.Text(string="Résumé de la réponse")
    satisfaction_after_treatment = fields.Selection(
        [
            ("very_unsatisfied", "Très insatisfait"),
            ("unsatisfied", "Insatisfait"),
            ("neutral", "Neutre"),
            ("satisfied", "Satisfait"),
            ("very_satisfied", "Très satisfait"),
        ],
        string="Satisfaction après traitement",
    )

    # ------------------------------------------------------------------
    # Actions (réutilisation pure de mgmtsystem.action — la relation est
    # détenue ici, l'inverse est ajouté côté smq_quality_bridge, même
    # pattern que smq.risk.action_ids / mgmtsystem.action.risk_ids)
    # ------------------------------------------------------------------
    action_ids = fields.Many2many(
        "mgmtsystem.action",
        "smq_complaint_action_rel",
        "complaint_id",
        "action_id",
        string="Actions",
    )
    action_count = fields.Integer(compute="_compute_action_count")

    # ------------------------------------------------------------------
    # Statut / responsable / société
    # ------------------------------------------------------------------
    state = fields.Selection(
        [
            ("nouvelle", "Nouvelle"),
            ("qualification", "Qualification"),
            ("traitement", "En traitement"),
            ("reponse_envoyee", "Réponse envoyée"),
            ("cloturee", "Clôturée"),
        ],
        default="nouvelle",
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
        for complaint in self:
            complaint.action_count = len(complaint.action_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", _("Nouveau")) == _("Nouveau"):
                vals["reference"] = self.env["ir.sequence"].next_by_code(
                    "smq.complaint"
                ) or _("Nouveau")
        return super().create(vals_list)

    def action_create_treatment_action(self):
        self.ensure_one()
        action = self.env["mgmtsystem.action"].create(
            {
                "name": self.name,
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
