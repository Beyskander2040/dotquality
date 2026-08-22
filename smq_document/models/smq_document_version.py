from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Champs figés dès qu'une version quitte le brouillon (règle R1/R2 : une version
# validée/approuvée/publiée/en vigueur ne se modifie plus, seule une nouvelle
# version le peut).
_LOCKED_FIELDS = {
    "attachment_ids",
    "change_reason",
    "change_description",
    "author_id",
    "version_number",
    "document_id",
}

# Clé de contexte utilisée par les méthodes internes du workflow pour être
# seules autorisées à modifier "state" — un write() direct (UI générique,
# import, RPC) sur ce champ est refusé (règle : ne pas pouvoir contourner le
# workflow en modifiant directement le statut).
_ALLOW_STATE_WRITE_KEY = "smq_allow_state_write"

_CHANGE_REASON_SELECTION = [
    ("regulatory_update", "Mise à jour réglementaire"),
    ("process_improvement", "Amélioration du processus"),
    ("error_correction", "Correction d'une erreur"),
    ("audit_result", "Résultat d'audit"),
    ("corrective_action", "Action corrective"),
    ("periodic_review", "Révision périodique"),
    ("other", "Autre"),
]


class SmqDocumentVersion(models.Model):
    _name = "smq.document.version"
    _inherit = ["mail.thread"]
    _description = "SMQ Document Version"
    _order = "document_id, version_number desc"

    document_id = fields.Many2one(
        "smq.document", required=True, ondelete="cascade", index=True
    )
    version_number = fields.Integer(readonly=True, copy=False)
    display_version = fields.Char(compute="_compute_display_version")
    previous_version_id = fields.Many2one(
        "smq.document.version", string="Version précédente", readonly=True, copy=False
    )
    attachment_ids = fields.One2many(
        "ir.attachment",
        "res_id",
        string="Fichiers joints",
        domain=lambda self: [("res_model", "=", self._name)],
    )
    author_id = fields.Many2one(
        "res.users", default=lambda self: self.env.uid, tracking=True
    )
    change_reason = fields.Selection(
        _CHANGE_REASON_SELECTION, string="Motif de la modification"
    )
    change_description = fields.Text(string="Description des changements")
    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("in_validation", "En validation"),
            ("approved", "Approuvé"),
            ("published", "Publié"),
            ("effective", "En vigueur"),
            ("obsolete", "Obsolète"),
        ],
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )

    # Traçabilité — chaque transition enregistre qui et quand. L'historique
    # complet (y compris les rejets et resoumissions répétés) vit dans le
    # chatter ; ces champs donnent un instantané rapide du dernier cycle.
    submitted_by = fields.Many2one("res.users", readonly=True, copy=False)
    submission_date = fields.Datetime(readonly=True, copy=False)
    validated_by = fields.Many2one("res.users", readonly=True, copy=False)
    approval_date = fields.Datetime(readonly=True, copy=False)
    rejected_by = fields.Many2one("res.users", readonly=True, copy=False)
    rejection_date = fields.Datetime(readonly=True, copy=False)
    rejection_reason = fields.Text(readonly=True, copy=False)
    published_by = fields.Many2one("res.users", readonly=True, copy=False)
    publication_date = fields.Datetime(readonly=True, copy=False)
    set_effective_by = fields.Many2one("res.users", readonly=True, copy=False)
    effective_date = fields.Datetime(readonly=True, copy=False)
    obsolete_date = fields.Datetime(readonly=True, copy=False)

    company_id = fields.Many2one(related="document_id.company_id", store=True)

    _sql_constraints = [
        (
            "version_number_uniq",
            "unique(document_id, version_number)",
            "Deux versions d'un même document ne peuvent pas partager le même numéro.",
        ),
    ]

    @api.depends("version_number")
    def _compute_display_version(self):
        for version in self:
            version.display_version = f"V{version.version_number}.0"

    @api.constrains("change_reason", "version_number")
    def _check_change_reason_required_from_v2(self):
        for version in self:
            if version.version_number > 1 and not version.change_reason:
                raise ValidationError(
                    _("Le motif de la modification est obligatoire à partir de la V2.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("version_number") and vals.get("document_id"):
                last = self.search(
                    [("document_id", "=", vals["document_id"])],
                    order="version_number desc",
                    limit=1,
                )
                vals["version_number"] = (last.version_number if last else 0) + 1
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals and not self.env.context.get(_ALLOW_STATE_WRITE_KEY):
            raise ValidationError(
                _("Le statut d'une version ne peut être changé que via les boutons du workflow.")
            )
        for version in self:
            if version.state != "draft":
                locked = _LOCKED_FIELDS & set(vals)
                if locked:
                    raise ValidationError(
                        _(
                            "Cette version n'est plus en brouillon : "
                            "les champs %(fields)s ne peuvent plus être modifiés. "
                            "Créez une nouvelle version pour la faire évoluer.",
                            fields=", ".join(sorted(locked)),
                        )
                    )
        return super().write(vals)

    def _write_state(self, vals):
        return self.with_context(**{_ALLOW_STATE_WRITE_KEY: True}).write(vals)

    def _check_transition(self, expected_from):
        self.ensure_one()
        if self.state != expected_from:
            raise UserError(
                _(
                    "Transition impossible : cette version est '%(current)s', "
                    "pas '%(expected)s'.",
                    current=self.state,
                    expected=expected_from,
                )
            )

    def _check_user_can(self, group_xmlid, action_label):
        if not self.env.user.has_group(group_xmlid):
            raise UserError(
                _("Vous n'avez pas les droits nécessaires pour %(action)s.", action=action_label)
            )

    # -- Soumission ---------------------------------------------------------

    def action_submit_validation(self):
        for version in self:
            version._check_transition("draft")
            if not version.attachment_ids:
                raise UserError(
                    _("Impossible de soumettre une version sans fichier joint.")
                )
            version._write_state(
                {
                    "state": "in_validation",
                    "submitted_by": self.env.uid,
                    "submission_date": fields.Datetime.now(),
                }
            )
            version.message_post(
                body=_("Soumis en validation par %s.") % self.env.user.name
            )

    # -- Validation / rejet --------------------------------------------------

    def action_validate(self):
        for version in self:
            version._check_transition("in_validation")
            version._check_user_can("smq_quality.group_smq_verifier", _("valider une version"))
            version._write_state(
                {
                    "state": "approved",
                    "validated_by": self.env.uid,
                    "approval_date": fields.Datetime.now(),
                }
            )
            version.message_post(body=_("Validée par %s.") % self.env.user.name)

    def action_reject(self):
        self.ensure_one()
        self._check_transition("in_validation")
        self._check_user_can("smq_quality.group_smq_verifier", _("rejeter une version"))
        return {
            "type": "ir.actions.act_window",
            "name": _("Motif du rejet"),
            "res_model": "smq.document.version.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_version_id": self.id},
        }

    def action_reject_confirm(self, reason):
        self.ensure_one()
        self._check_transition("in_validation")
        self._write_state(
            {
                "state": "draft",
                "rejected_by": self.env.uid,
                "rejection_date": fields.Datetime.now(),
                "rejection_reason": reason,
            }
        )
        self.message_post(
            body=_("Rejetée par %(user)s. Motif : %(reason)s")
            % {"user": self.env.user.name, "reason": reason}
        )

    # -- Publication ----------------------------------------------------------

    def action_publish(self):
        for version in self:
            version._check_transition("approved")
            version._check_user_can(
                "smq_quality.group_smq_quality_manager", _("publier une version")
            )
            version._write_state(
                {
                    "state": "published",
                    "published_by": self.env.uid,
                    "publication_date": fields.Datetime.now(),
                }
            )
            version.message_post(body=_("Publiée par %s.") % self.env.user.name)

    # -- Entrée en vigueur ----------------------------------------------------

    def action_set_effective(self):
        self.ensure_one()
        self._check_transition("published")
        self._check_user_can(
            "smq_quality.group_smq_quality_manager", _("mettre en vigueur une version")
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Date d'entrée en vigueur"),
            "res_model": "smq.document.version.effective.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_version_id": self.id},
        }

    def action_set_effective_confirm(self, effective_date):
        self.ensure_one()
        self._check_transition("published")
        previous_effective = self.document_id.version_ids.filtered(
            lambda v: v.state == "effective" and v.id != self.id
        )
        previous_effective._write_state(
            {"state": "obsolete", "obsolete_date": fields.Datetime.now()}
        )
        self._write_state({"state": "effective", "effective_date": effective_date, "set_effective_by": self.env.uid})
        self.message_post(
            body=_("Mise en vigueur par %(user)s à compter du %(date)s.")
            % {"user": self.env.user.name, "date": effective_date}
        )
        if previous_effective:
            previous_effective.message_post(
                body=_("Rendue obsolète — remplacée par %s.") % self.display_version
            )

    # -- Obsolescence manuelle -------------------------------------------------

    def action_set_obsolete(self):
        for version in self:
            version._write_state(
                {"state": "obsolete", "obsolete_date": fields.Datetime.now()}
            )
            version.message_post(body=_("Rendue obsolète par %s.") % self.env.user.name)
