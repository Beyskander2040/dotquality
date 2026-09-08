from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Priorité du statut le plus avancé parmi les versions non obsolètes d'un document.
_STAGE_PRIORITY = ["effective", "published", "approved", "in_validation", "draft"]


class SmqDocument(models.Model):
    _name = "smq.document"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "SMQ Document"
    _order = "code"

    code = fields.Char(copy=False, tracking=True)
    name = fields.Char(required=True, tracking=True)
    description = fields.Text()
    document_type_id = fields.Many2one(
        "smq.document.type", string="Type", required=True, tracking=True
    )
    process_id = fields.Many2one("smq.process", string="Processus", tracking=True)
    parent_document_id = fields.Many2one(
        "smq.document",
        string="Document parent",
        tracking=True,
        index=True,
        domain="[('id', '!=', id)]",
        help="Document dont celui-ci dépend dans la hiérarchie documentaire "
        "(ex. un Formulaire rattaché à la Procédure qui l'utilise). "
        "Purement documentaire : indépendant du lien Processus ci-dessus.",
    )
    child_document_ids = fields.One2many(
        "smq.document", "parent_document_id", string="Documents liés"
    )
    child_document_count = fields.Integer(compute="_compute_child_document_count")
    formulaire_ids = fields.Many2many(
        "smq.document",
        "smq_document_formulaire_rel",
        "procedure_id",
        "formulaire_id",
        string="Formulaires utilisés",
        help="Formulaires que cette procédure utilise pour capturer ses données — relation "
        "documentaire directe, indépendante de la hiérarchie (Document parent) et des "
        "activités BPMN qui peuvent séparément référencer les mêmes documents.",
    )
    effective_process_id = fields.Many2one(
        "smq.process",
        string="Processus (effectif)",
        compute="_compute_effective_process_id",
        store=True,
        recursive=True,
        help="process_id si renseigné, sinon celui hérité du document parent — "
        "utilisé pour le regroupement afin qu'un document sans Processus propre "
        "reste rattaché à celui de sa Procédure/Formulaire parent.",
    )
    complete_name = fields.Char(
        string="Hiérarchie",
        compute="_compute_complete_name",
        store=True,
        recursive=True,
    )
    responsible_id = fields.Many2one(
        "res.users",
        string="Responsable",
        required=True,
        default=lambda self: self.env.uid,
        tracking=True,
    )
    department = fields.Char(string="Service / Département")
    confidentiality_level = fields.Selection(
        [
            ("public", "Public"),
            ("internal", "Interne"),
            ("confidential", "Confidentiel"),
        ],
        default="internal",
        required=True,
        tracking=True,
    )
    review_period = fields.Integer(
        string="Fréquence de révision (mois)",
        help="Remplace la périodicité par défaut du type de document pour ce document précis. Laisser à 0 pour utiliser celle du type.",
    )
    stage_id = fields.Many2one(
        "smq.document.stage",
        string="Statut",
        compute="_compute_stage_id",
        store=True,
        tracking=True,
    )
    version_ids = fields.One2many("smq.document.version", "document_id", string="Versions")
    current_version_id = fields.Many2one(
        "smq.document.version",
        string="Version courante",
        compute="_compute_current_version_id",
        store=True,
    )
    workflow_version_id = fields.Many2one(
        "smq.document.version",
        string="Version active",
        compute="_compute_workflow_version_id",
        store=True,
        help="Version la plus récente non obsolète : celle sur laquelle agissent les boutons du workflow.",
    )
    workflow_state = fields.Selection(
        related="workflow_version_id.state", string="Statut (version active)"
    )
    # Instantané de la dernière décision sur la version active — l'historique
    # complet (validations et rejets successifs) reste dans le chatter.
    workflow_submitted_by = fields.Many2one(
        related="workflow_version_id.submitted_by", string="Soumis par (version active)"
    )
    workflow_submission_date = fields.Datetime(
        related="workflow_version_id.submission_date", string="Date de soumission (version active)"
    )
    workflow_validated_by = fields.Many2one(
        related="workflow_version_id.validated_by", string="Validé par (version active)"
    )
    workflow_approval_date = fields.Datetime(
        related="workflow_version_id.approval_date", string="Date de validation (version active)"
    )
    workflow_rejected_by = fields.Many2one(
        related="workflow_version_id.rejected_by", string="Rejeté par (version active)"
    )
    workflow_rejection_date = fields.Datetime(
        related="workflow_version_id.rejection_date", string="Date de rejet (version active)"
    )
    workflow_rejection_reason = fields.Text(
        related="workflow_version_id.rejection_reason", string="Motif de rejet (version active)"
    )
    workflow_attachment_ids = fields.Many2many(
        "ir.attachment",
        compute="_compute_workflow_attachment_ids",
        string="Fichiers de la version active",
    )
    has_revision_in_progress = fields.Boolean(
        compute="_compute_has_revision_in_progress",
        help="Une version plus récente que la version en vigueur est en cours d'élaboration.",
    )
    version_count = fields.Integer(compute="_compute_version_count")
    approval_date = fields.Datetime(compute="_compute_approval_date", store=True)
    publication_date = fields.Datetime(compute="_compute_publication_date", store=True)
    next_review_date = fields.Date(compute="_compute_next_review_date", store=True)
    last_periodic_review_date = fields.Datetime(
        string="Dernière revue périodique", readonly=True, copy=False
    )
    last_periodic_reviewer_id = fields.Many2one(
        "res.users", string="Dernier réviseur", readonly=True, copy=False
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_uniq", "unique(code, company_id)", "Le code du document doit être unique."),
    ]

    @api.depends("version_ids.state")
    def _compute_version_count(self):
        for doc in self:
            doc.version_count = len(doc.version_ids)

    @api.depends("child_document_ids")
    def _compute_child_document_count(self):
        for doc in self:
            doc.child_document_count = len(doc.child_document_ids)

    @api.depends("process_id", "parent_document_id.effective_process_id")
    def _compute_effective_process_id(self):
        for doc in self:
            doc.effective_process_id = doc.process_id or doc.parent_document_id.effective_process_id

    @api.depends("name", "parent_document_id.complete_name")
    def _compute_complete_name(self):
        for doc in self:
            if doc.parent_document_id:
                doc.complete_name = f"{doc.parent_document_id.complete_name} › {doc.name}"
            else:
                doc.complete_name = doc.name

    @api.constrains("parent_document_id")
    def _check_no_hierarchy_cycle(self):
        for doc in self:
            ancestor = doc.parent_document_id
            seen = set()
            while ancestor:
                if ancestor.id == doc.id or ancestor.id in seen:
                    raise ValidationError(
                        _(
                            "Le document « %(name)s » ne peut pas être son propre "
                            "ancêtre dans la hiérarchie documentaire.",
                            name=doc.display_name,
                        )
                    )
                seen.add(ancestor.id)
                ancestor = ancestor.parent_document_id

    @api.depends("version_ids.state", "version_ids.version_number")
    def _compute_workflow_version_id(self):
        for doc in self:
            candidates = doc.version_ids.filtered(lambda v: v.state != "obsolete")
            doc.workflow_version_id = (
                max(candidates, key=lambda v: v.version_number) if candidates else False
            )

    @api.depends("workflow_version_id.attachment_ids")
    def _compute_workflow_attachment_ids(self):
        for doc in self:
            doc.workflow_attachment_ids = doc.workflow_version_id.attachment_ids

    @api.depends("current_version_id", "workflow_version_id")
    def _compute_has_revision_in_progress(self):
        for doc in self:
            doc.has_revision_in_progress = bool(
                doc.current_version_id
                and doc.workflow_version_id
                and doc.workflow_version_id != doc.current_version_id
            )

    @api.depends("version_ids.state", "version_ids.version_number")
    def _compute_current_version_id(self):
        # "Courante" = réellement en vigueur. Une version "publiée" mais pas
        # encore en vigueur ne doit pas apparaître comme la version courante
        # (cf. MAN-001 dans les données de démonstration).
        for doc in self:
            candidates = doc.version_ids.filtered(lambda v: v.state == "effective")
            doc.current_version_id = (
                max(candidates, key=lambda v: v.version_number) if candidates else False
            )

    @api.depends("version_ids.state", "version_ids.approval_date")
    def _compute_approval_date(self):
        for doc in self:
            candidates = doc.version_ids.filtered(
                lambda v: v.state in ("approved", "published", "effective") and v.approval_date
            )
            doc.approval_date = (
                max(candidates.mapped("approval_date")) if candidates else False
            )

    @api.depends("version_ids.state", "version_ids.publication_date")
    def _compute_publication_date(self):
        for doc in self:
            candidates = doc.version_ids.filtered(
                lambda v: v.state in ("published", "effective") and v.publication_date
            )
            doc.publication_date = (
                max(candidates.mapped("publication_date")) if candidates else False
            )

    @api.depends("version_ids.state")
    def _compute_stage_id(self):
        stages = {s.code: s for s in self.env["smq.document.stage"].search([])}
        for doc in self:
            if not doc.version_ids:
                doc.stage_id = stages.get("draft")
                continue
            active_versions = doc.version_ids.filtered(lambda v: v.state != "obsolete")
            ref_versions = active_versions or doc.version_ids
            best = min(
                ref_versions,
                key=lambda v: _STAGE_PRIORITY.index(v.state)
                if v.state in _STAGE_PRIORITY
                else len(_STAGE_PRIORITY),
            )
            doc.stage_id = stages.get(best.state) or stages.get("draft")

    @api.depends(
        "current_version_id.effective_date",
        "document_type_id.review_period",
        "review_period",
        "last_periodic_review_date",
    )
    def _compute_next_review_date(self):
        # Le point de départ du calcul est la plus récente des deux dates
        # connues : l'entrée en vigueur de la version courante, ou la
        # dernière revue périodique confirmée (sans nouvelle version). Une
        # nouvelle version rend naturellement obsolète une revue périodique
        # plus ancienne, sans qu'il soit nécessaire de la réinitialiser.
        for doc in self:
            candidates = [
                d for d in (doc.current_version_id.effective_date, doc.last_periodic_review_date) if d
            ]
            base_date = max(candidates) if candidates else False
            months = doc.review_period or doc.document_type_id.review_period
            if base_date and months:
                doc.next_review_date = fields.Date.to_date(base_date) + relativedelta(
                    months=months
                )
            else:
                doc.next_review_date = False

    @api.constrains("code")
    def _check_code_required(self):
        # Contrainte plutôt que required=True sur le champ : le code est
        # rempli automatiquement par create() une fois le type choisi, un
        # required= côté client bloquerait la sauvegarde avant que ce
        # remplissage automatique n'ait eu lieu.
        for doc in self:
            if not doc.code:
                raise ValidationError(_("La référence du document est obligatoire."))

    @api.constrains("process_id", "document_type_id")
    def _check_process_required(self):
        for doc in self:
            if doc.document_type_id.requires_process and not doc.process_id:
                raise ValidationError(
                    _(
                        "Le type de document '%(type)s' exige un processus associé.",
                        type=doc.document_type_id.name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code") and vals.get("document_type_id"):
                doc_type = self.env["smq.document.type"].browse(vals["document_type_id"])
                count = self.search_count([("document_type_id", "=", doc_type.id)])
                vals["code"] = f"{doc_type.code_prefix}-{count + 1:03d}"
            self._inherit_process_from_parent(vals)
        documents = super().create(vals_list)
        for doc in documents:
            if not doc.version_ids:
                self.env["smq.document.version"].create({"document_id": doc.id})
        return documents

    def write(self, vals):
        if vals.get("parent_document_id") and not vals.get("process_id"):
            without_process = self.filtered(lambda d: not d.process_id)
            if without_process:
                child_vals = dict(vals)
                self._inherit_process_from_parent(child_vals)
                super(SmqDocument, without_process).write(child_vals)
            with_process = self - without_process
            if with_process:
                super(SmqDocument, with_process).write(vals)
            return True
        return super().write(vals)

    def _inherit_process_from_parent(self, vals):
        # Un Formulaire/Enregistrement rattaché à une Procédure appartient
        # normalement au même Processus qu'elle (§ échange utilisateur) —
        # complète process_id automatiquement quand il est absent, sans
        # jamais écraser une valeur déjà choisie explicitement.
        if vals.get("parent_document_id") and not vals.get("process_id"):
            parent = self.browse(vals["parent_document_id"])
            if parent.process_id:
                vals["process_id"] = parent.process_id.id

    def _get_workflow_version(self):
        self.ensure_one()
        if not self.workflow_version_id:
            raise UserError(_("Ce document n'a aucune version active."))
        return self.workflow_version_id

    def _demo_configure_first_version(self, vals):
        """Configure la version V1 auto-créée par create() — utilisé uniquement
        par les données de démonstration, pour éviter d'en créer une seconde
        en doublon."""
        self.ensure_one()
        version = self.version_ids[:1]
        version.with_context(smq_allow_state_write=True).write(vals)
        return version

    def _demo_add_next_version(self, vals):
        """Crée la version suivante en la liant à la plus récente existante —
        utilisé uniquement par les données de démonstration."""
        self.ensure_one()
        previous = max(self.version_ids, key=lambda v: v.version_number, default=False)
        vals = dict(vals, document_id=self.id, previous_version_id=previous.id if previous else False)
        return self.env["smq.document.version"].create(vals)

    def action_submit_validation(self):
        for doc in self:
            doc._get_workflow_version().action_submit_validation()

    def action_validate(self):
        for doc in self:
            doc._get_workflow_version().action_validate()

    def action_reject(self):
        self.ensure_one()
        return self._get_workflow_version().action_reject()

    def action_publish(self):
        for doc in self:
            doc._get_workflow_version().action_publish()

    def action_set_effective(self):
        self.ensure_one()
        return self._get_workflow_version().action_set_effective()

    def action_create_new_version(self):
        self.ensure_one()
        if not self.current_version_id:
            raise UserError(
                _("Une nouvelle version ne peut être créée que si le document a une version en vigueur.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Nouvelle version"),
            "res_model": "smq.document.version",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_document_id": self.id,
                "default_previous_version_id": self.current_version_id.id,
            },
        }

    def action_periodic_review(self):
        self.ensure_one()
        if self.stage_id.code != "effective":
            raise UserError(
                _("Seul un document en vigueur peut faire l'objet d'une revue périodique.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Revue périodique"),
            "res_model": "smq.document.periodic.review.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_document_id": self.id},
        }

    def action_periodic_review_confirm(self, review_date, comment=None):
        self.ensure_one()
        self.write(
            {
                "last_periodic_review_date": review_date,
                "last_periodic_reviewer_id": self.env.uid,
            }
        )
        body = _("Revue périodique effectuée par %(user)s le %(date)s.") % {
            "user": self.env.user.name,
            "date": review_date,
        }
        if comment:
            body += "<br/>" + comment
        self.message_post(body=body)

    def action_view_versions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Versions"),
            "res_model": "smq.document.version",
            "view_mode": "tree,form",
            "domain": [("document_id", "=", self.id)],
            "context": {"default_document_id": self.id},
        }

    def action_view_child_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Documents liés"),
            "res_model": "smq.document",
            "view_mode": "kanban,tree,form",
            "domain": [("parent_document_id", "=", self.id)],
            "context": {"default_parent_document_id": self.id},
        }
