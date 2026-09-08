from odoo import _, api, fields, models


class MgmtsystemAction(models.Model):
    _inherit = "mgmtsystem.action"

    # ------------------------------------------------------------------
    # Risques & Opportunités (smq_risk) — même pattern que
    # mgmtsystem_nonconformity : la relation M2M est détenue par smq.risk,
    # on ajoute ici uniquement l'inverse + un compteur + un accès rapide.
    # ------------------------------------------------------------------
    risk_ids = fields.Many2many(
        "smq.risk",
        "smq_risk_action_rel",
        "action_id",
        "risk_id",
        string="Risques",
        readonly=True,
    )
    risk_count = fields.Integer(compute="_compute_risk_count")

    @api.depends("risk_ids")
    def _compute_risk_count(self):
        for action in self:
            action.risk_count = len(action.risk_ids)

    def action_open_risks(self):
        self.ensure_one()
        return {
            "name": _("Risques"),
            "type": "ir.actions.act_window",
            "res_model": "smq.risk",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.risk_ids.ids)],
        }

    # ------------------------------------------------------------------
    # Réclamations clients (smq_complaint) — même pattern que risk_ids
    # ------------------------------------------------------------------
    complaint_ids = fields.Many2many(
        "smq.complaint",
        "smq_complaint_action_rel",
        "action_id",
        "complaint_id",
        string="Réclamations",
        readonly=True,
    )
    complaint_count = fields.Integer(compute="_compute_complaint_count")

    @api.depends("complaint_ids")
    def _compute_complaint_count(self):
        for action in self:
            action.complaint_count = len(action.complaint_ids)

    def action_open_complaints(self):
        self.ensure_one()
        return {
            "name": _("Réclamations"),
            "type": "ir.actions.act_window",
            "res_model": "smq.complaint",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.complaint_ids.ids)],
        }

    # ------------------------------------------------------------------
    # Formations (smq_training) — même pattern que risk_ids/complaint_ids
    # ------------------------------------------------------------------
    training_ids = fields.Many2many(
        "smq.training",
        "smq_training_action_rel",
        "action_id",
        "training_id",
        string="Formations",
        readonly=True,
    )
    training_count = fields.Integer(compute="_compute_training_count")

    @api.depends("training_ids")
    def _compute_training_count(self):
        for action in self:
            action.training_count = len(action.training_ids)

    def action_open_trainings(self):
        self.ensure_one()
        return {
            "name": _("Formations"),
            "type": "ir.actions.act_window",
            "res_model": "smq.training",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.training_ids.ids)],
        }

    # ------------------------------------------------------------------
    # Évaluations fournisseurs (smq_supplier) — même pattern que
    # risk_ids/complaint_ids/training_ids
    # ------------------------------------------------------------------
    supplier_evaluation_ids = fields.Many2many(
        "smq.supplier.evaluation",
        "smq_supplier_evaluation_action_rel",
        "action_id",
        "evaluation_id",
        string="Évaluations fournisseurs",
        readonly=True,
    )
    supplier_evaluation_count = fields.Integer(compute="_compute_supplier_evaluation_count")

    @api.depends("supplier_evaluation_ids")
    def _compute_supplier_evaluation_count(self):
        for action in self:
            action.supplier_evaluation_count = len(action.supplier_evaluation_ids)

    def action_open_supplier_evaluations(self):
        self.ensure_one()
        return {
            "name": _("Évaluations fournisseurs"),
            "type": "ir.actions.act_window",
            "res_model": "smq.supplier.evaluation",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.supplier_evaluation_ids.ids)],
        }

    # ------------------------------------------------------------------
    # Vérification de l'efficacité — s'appuie sur les champs déjà fournis
    # par mgmtsystem_action_efficacy (efficacy_value/user_id/description) :
    # on ajoute uniquement ce qui manque pour l'usage SMQ (une date, et un
    # résultat en trois niveaux plus lisible qu'une note 0/50/100).
    # ------------------------------------------------------------------
    _EFFICACY_VALUE_BY_RESULT = {
        "effective": 100,
        "partial": 50,
        "ineffective": 0,
    }

    efficacy_date = fields.Datetime(string="Date de vérification")
    efficacy_result = fields.Selection(
        [
            ("effective", "Efficace"),
            ("partial", "Partiellement efficace"),
            ("ineffective", "Non efficace"),
        ],
        string="Résultat de la vérification",
        compute="_compute_efficacy_result",
        inverse="_inverse_efficacy_result",
        store=True,
    )

    @api.depends("efficacy_value", "efficacy_date")
    def _compute_efficacy_result(self):
        # efficacy_value est un Integer OCA sans état "non renseigné" (NULL
        # se lit 0 côté ORM, la même valeur que "Non efficace") : on utilise
        # efficacy_date comme signal explicite qu'une vérification a bien
        # eu lieu, pour ne pas afficher "Non efficace" par défaut sur une
        # action jamais évaluée.
        by_value = {v: k for k, v in self._EFFICACY_VALUE_BY_RESULT.items()}
        for action in self:
            action.efficacy_result = (
                by_value.get(action.efficacy_value) if action.efficacy_date else False
            )

    def _inverse_efficacy_result(self):
        for action in self:
            if action.efficacy_result:
                action.efficacy_value = self._EFFICACY_VALUE_BY_RESULT[
                    action.efficacy_result
                ]
                if not action.efficacy_date:
                    action.efficacy_date = fields.Datetime.now()

    # ------------------------------------------------------------------
    # Relabellisation FR
    # ------------------------------------------------------------------
    name = fields.Char(string="Titre")
    user_id = fields.Many2one(string="Responsable")
    date_deadline = fields.Date(string="Échéance")
    reference = fields.Char(string="Référence")
    description = fields.Html(string="Description")
    type_action = fields.Selection(string="Type")
    # Seule option de ce formulaire sans traduction fr_FR fournie par le
    # module OCA (mgmtsystem_action/i18n/fr.po ne traduit pas "Low"/"Normal" :
    # msgstr vide) — les valeurs techniques ("0"/"1") restent inchangées,
    # seuls les libellés affichés sont relabellisés.
    priority = fields.Selection(
        [("0", "Faible"), ("1", "Normale")], string="Priorité"
    )
    efficacy_user_id = fields.Many2one(string="Vérificateur")
    efficacy_description = fields.Text(string="Commentaire de vérification")
    # Ajouté par mgmtsystem_action_template : le champ s'affiche déjà
    # automatiquement dans ce formulaire (les deux modules héritent
    # indépendamment de la même vue OCA de base, Odoo compose les deux
    # patches) — seule la relabellisation française manquait.
    template_id = fields.Many2one(string="Modèle d'action")
