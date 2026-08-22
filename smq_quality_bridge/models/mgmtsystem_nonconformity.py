from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError


def _check_user_can(env, group_xmlid, action_label):
    # Le "groups=" d'un bouton ne masque le bouton que côté client : sans ce
    # contrôle serveur, un utilisateur ayant seulement le droit d'écriture
    # (ex. Rédacteur) pourrait déclencher une transition réservée (ex.
    # Responsable Qualité) par RPC direct. Le superuser (données de
    # démonstration, scripts d'installation) reste exempté, comme pour
    # les ACL/ir.rule standard.
    if env.uid == SUPERUSER_ID:
        return
    if not env.user.has_group(group_xmlid):
        raise UserError(
            _("Vous n'avez pas les droits nécessaires pour : %s") % action_label
        )


class MgmtsystemNonconformity(models.Model):
    _inherit = "mgmtsystem.nonconformity"

    # ------------------------------------------------------------------
    # Champs SMQ
    # ------------------------------------------------------------------
    quality_process_id = fields.Many2one(
        "smq.process", string="Processus", tracking=True
    )
    smq_document_ids = fields.Many2many(
        "smq.document",
        "smq_nonconformity_document_rel",
        "nonconformity_id",
        "document_id",
        string="Documents liés",
    )
    smq_document_count = fields.Integer(compute="_compute_smq_document_count")
    action_count = fields.Integer(compute="_compute_action_count")
    next_action_deadline = fields.Date(
        string="Échéance",
        compute="_compute_next_action_deadline",
    )

    priority = fields.Selection(
        [
            ("0", "Basse"),
            ("1", "Normale"),
            ("2", "Haute"),
            ("3", "Critique"),
        ],
        string="Priorité",
        default="1",
        tracking=True,
    )
    impact = fields.Selection(
        [
            ("low", "Faible"),
            ("medium", "Moyen"),
            ("high", "Élevé"),
        ],
        string="Impact",
    )
    observation = fields.Text(string="Constat")
    requirement_concerned = fields.Char(string="Exigence concernée")
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "smq_nonconformity_attachment_rel",
        "nonconformity_id",
        "attachment_id",
        string="Preuves / Pièces jointes",
    )

    # Analyse — la taxonomie cause_ids/analysis existante reste disponible ;
    # ces trois champs couvrent ce qu'elle ne structure pas encore.
    immediate_cause = fields.Text(string="Cause immédiate")
    root_cause = fields.Text(string="Cause racine")
    analysis_method = fields.Selection(
        [
            ("5why", "5 Pourquoi"),
            ("ishikawa", "Ishikawa"),
            ("simple", "Analyse simple"),
            ("other", "Autre"),
        ],
        string="Méthode d'analyse",
    )

    closed_by_id = fields.Many2one(
        "res.users", string="Clôturé par", readonly=True, copy=False
    )

    # Relabellisation FR des champs ajoutés par mgmtsystem_nonconformity_type
    # et mgmtsystem_nonconformity_hr (mêmes valeurs/relation que l'OCA,
    # seuls les libellés changent — cf. convention déjà suivie ci-dessous).
    nc_type = fields.Selection(
        [
            ("internal", "Interne"),
            ("supplier", "Fournisseur"),
            ("customer", "Client"),
            ("external", "Externe"),
        ],
        string="Type",
        default="internal",
    )
    department_id = fields.Many2one(string="Département")

    # ------------------------------------------------------------------
    # Relabellisation FR de champs OCA existants (pas de nouveau mécanisme)
    # ------------------------------------------------------------------
    name = fields.Char(string="Titre", required=True)
    ref = fields.Char(string="Référence")
    date = fields.Datetime(string="Date de détection")
    description = fields.Text(string="Description de la non-conformité")
    analysis = fields.Text(string="Commentaire d'analyse")
    origin_ids = fields.Many2many(string="Source")
    severity_id = fields.Many2one(string="Gravité")
    action_comments = fields.Text(string="Plan d'action")
    evaluation_comments = fields.Text(string="Conclusion de la vérification d'efficacité")

    responsible_user_id = fields.Many2one(
        string="Responsable", default=lambda self: self.env.uid
    )
    manager_user_id = fields.Many2one(
        string="Responsable Qualité", default=lambda self: self.env.uid
    )
    user_id = fields.Many2one(string="Déclaré par")
    # Champ OCA requis mais hors périmètre SMQ (aucun lien ERP/tiers) :
    # on le neutralise avec un défaut automatique, sans le montrer dans le
    # formulaire SMQ.
    partner_id = fields.Many2one(
        default=lambda self: self.env.company.partner_id
    )

    @api.depends("smq_document_ids")
    def _compute_smq_document_count(self):
        for nc in self:
            nc.smq_document_count = len(nc.smq_document_ids)

    @api.depends("action_ids", "immediate_action_id")
    def _compute_action_count(self):
        for nc in self:
            nc.action_count = len(nc._get_all_actions())

    @api.depends("action_ids.date_deadline", "immediate_action_id.date_deadline")
    def _compute_next_action_deadline(self):
        for nc in self:
            deadlines = nc._get_all_actions().filtered("date_deadline").mapped(
                "date_deadline"
            )
            nc.next_action_deadline = min(deadlines) if deadlines else False

    def write(self, vals):
        before_state = {nc.id: nc.state for nc in self}
        result = super().write(vals)
        for nc in self:
            if nc.state == "done" and before_state.get(nc.id) != "done":
                nc.closed_by_id = self.env.user
            elif nc.state != "done" and nc.closed_by_id:
                nc.closed_by_id = False
        return result

    # ------------------------------------------------------------------
    # Workflow SMQ : 4 boutons pilotant les stages OCA existants.
    # ------------------------------------------------------------------
    def action_start_analysis(self):
        _check_user_can(
            self.env, "smq_quality.group_smq_verifier", _("commencer l'analyse")
        )
        stage = self.env.ref("mgmtsystem_nonconformity.stage_analysis")
        for nc in self:
            nc.write({"stage_id": stage.id})

    def action_start_treatment(self):
        _check_user_can(
            self.env,
            "smq_quality.group_smq_quality_manager",
            _("passer une non-conformité en traitement"),
        )
        stage = self.env.ref("mgmtsystem_nonconformity.stage_open")
        for nc in self:
            if not nc.action_comments:
                raise UserError(
                    _(
                        "Le plan d'action doit être renseigné avant de passer "
                        "la non-conformité en traitement."
                    )
                )
            nc.write({"stage_id": stage.id})

    def action_mark_resolved(self):
        _check_user_can(
            self.env,
            "smq_quality.group_smq_quality_manager",
            _("marquer une non-conformité comme résolue"),
        )
        stage = self.env.ref("smq_quality_bridge.stage_resolved")
        for nc in self:
            corrective_actions = nc._get_all_actions().filtered(
                lambda a: a.type_action == "correction"
            )
            if corrective_actions and not all(
                a.stage_id.is_ending for a in corrective_actions
            ):
                raise UserError(
                    _(
                        "Toutes les actions correctives doivent être terminées "
                        "avant de marquer la non-conformité comme résolue."
                    )
                )
            nc.write({"stage_id": stage.id})

    def action_close(self):
        _check_user_can(
            self.env,
            "smq_quality.group_smq_quality_manager",
            _("clôturer une non-conformité"),
        )
        stage = self.env.ref("mgmtsystem_nonconformity.stage_done")
        for nc in self:
            corrective_actions = nc._get_all_actions().filtered(
                lambda a: a.type_action == "correction"
            )
            if corrective_actions and not all(
                a.efficacy_result for a in corrective_actions
            ):
                raise UserError(
                    _(
                        "La vérification de l'efficacité doit être renseignée "
                        "pour chaque action corrective avant de clôturer la "
                        "non-conformité."
                    )
                )
            nc.write({"stage_id": stage.id})

    def action_view_actions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Actions correctives"),
            "res_model": "mgmtsystem.action",
            "view_mode": "tree,form",
            "domain": [("id", "in", self._get_all_actions().ids)],
            "context": {"default_type_action": "correction"},
        }

    def action_view_smq_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Documents liés"),
            "res_model": "smq.document",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.smq_document_ids.ids)],
        }
