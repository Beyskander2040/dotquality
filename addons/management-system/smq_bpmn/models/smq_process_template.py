from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .smq_bpmn_generator import generate_bpmn_xml
from .smq_process_step import _STEP_TYPE_SELECTION


class SmqProcessTemplate(models.Model):
    _name = "smq.process.template"
    _description = "SMQ Process Template"
    _order = "name"

    name = fields.Char(required=True)
    description = fields.Text(
        help="Objectif du modèle, contexte d'utilisation recommandé — affiché à "
        "l'utilisateur avant import."
    )
    category_id = fields.Many2one("smq.process.category", string="Catégorie")
    active = fields.Boolean(default=True)
    template_step_ids = fields.One2many(
        "smq.process.template.step", "template_id", string="Activités"
    )
    template_transition_ids = fields.One2many(
        "smq.process.template.step.transition", "template_id", string="Transitions"
    )
    step_count = fields.Integer(compute="_compute_step_count")

    @api.depends("template_step_ids")
    def _compute_step_count(self):
        for template in self:
            template.step_count = len(template.template_step_ids)

    # Gestion (create/write/unlink) réservée à smq_quality.group_smq_admin —
    # appliquée uniquement via ir.model.access.csv, jamais par un override
    # Python de create()/write() : un tel override bloquerait aussi le
    # chargement des données XML du module (exécuté par l'utilisateur
    # système, qui n'est pas nécessairement membre du groupe), comme pour
    # smq.document.type/smq.document.stage.

    def _get_description_issues(self):
        """Même logique que smq.process.version._get_description_issues,
        appliquée aux lignes du modèle — un modèle mal formé doit être
        détecté à l'import, jamais produire un processus avec un diagramme
        invalide."""
        self.ensure_one()
        issues = []
        steps = self.template_step_ids
        if not steps:
            issues.append(_("Aucune activité définie dans ce modèle."))
            return issues
        starts = steps.filtered(lambda s: s.step_type == "start")
        ends = steps.filtered(lambda s: s.step_type == "end")
        if not starts:
            issues.append(_("Aucun point de départ (Début) défini."))
        elif len(starts) > 1:
            issues.append(_("Plusieurs points de départ (Début) définis."))
        if not ends:
            issues.append(_("Aucun point de terminaison (Fin) défini."))
        if len(starts) == 1:
            visited = self.env["smq.process.template.step"]
            frontier = starts
            while frontier:
                visited |= frontier
                outgoing = self.template_transition_ids.filtered(lambda t: t.source_step_id in frontier)
                frontier = outgoing.mapped("target_step_id") - visited
            isolated = steps - visited
            for step in isolated:
                issues.append(_("« %s » n'est accessible depuis aucun point de départ.") % step.name)
        return issues

    def action_import(self, process_code, process_name, category_id=False, responsible_id=False):
        """Crée un Processus + une Version (brouillon) réels et indépendants
        à partir de ce modèle — jamais liés au modèle après coup : le
        modifier plus tard n'affecte aucun import déjà réalisé."""
        self.ensure_one()
        if not self.env.user.has_group("smq_quality.group_smq_writer"):
            raise UserError(_("Vous n'avez pas les droits nécessaires pour importer un modèle de processus."))
        issues = self._get_description_issues()
        if issues:
            raise ValidationError(_("Modèle invalide :\n%s") % "\n".join(issues))
        if self.env["smq.process"].search_count([("code", "=", process_code)]):
            raise UserError(_("Un processus avec le code « %s » existe déjà.") % process_code)

        process = self.env["smq.process"].create(
            {
                "code": process_code,
                "name": process_name,
                "category_id": category_id or self.category_id.id,
                "responsible_id": responsible_id or self.env.uid,
            }
        )
        version = self.env["smq.process.version"].create(
            {"process_id": process.id, "version": "1.0", "name": self.name}
        )
        Step = self.env["smq.process.step"]
        new_step_id_by_template_step_id = {}
        for template_step in self.template_step_ids:
            step = Step.create(
                {
                    "process_version_id": version.id,
                    "sequence": template_step.sequence,
                    "code": template_step.code,
                    "name": template_step.name,
                    "step_type": template_step.step_type,
                    "description": template_step.description,
                }
            )
            new_step_id_by_template_step_id[template_step.id] = step.id
        Transition = self.env["smq.process.step.transition"]
        for template_transition in self.template_transition_ids:
            Transition.create(
                {
                    "process_version_id": version.id,
                    "source_step_id": new_step_id_by_template_step_id[template_transition.source_step_id.id],
                    "target_step_id": new_step_id_by_template_step_id[template_transition.target_step_id.id],
                    "condition": template_transition.condition,
                    "sequence": template_transition.sequence,
                }
            )
        version.write({"bpmn_xml": generate_bpmn_xml(version)})
        process.message_post(body=_("Processus créé depuis le modèle « %s ».") % self.name)
        return process

    def action_open_import_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Importer le modèle"),
            "res_model": "smq.process.template.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_template_id": self.id,
                "default_process_name": self.name,
                "default_category_id": self.category_id.id,
            },
        }


class SmqProcessTemplateStep(models.Model):
    _name = "smq.process.template.step"
    _description = "SMQ Process Template Step"
    _order = "template_id, sequence, id"

    template_id = fields.Many2one(
        "smq.process.template", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(required=True, default=10)
    code = fields.Char(required=True)
    name = fields.Char(required=True)
    step_type = fields.Selection(_STEP_TYPE_SELECTION, string="Type", required=True)
    description = fields.Text()

    _sql_constraints = [
        (
            "template_code_uniq",
            "unique(template_id, code)",
            "Le code d'une activité doit être unique au sein d'un même modèle.",
        ),
    ]


class SmqProcessTemplateStepTransition(models.Model):
    _name = "smq.process.template.step.transition"
    _description = "SMQ Process Template Step Transition"
    _order = "template_id, sequence, id"

    template_id = fields.Many2one(
        "smq.process.template", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(required=True, default=10)
    source_step_id = fields.Many2one(
        "smq.process.template.step", string="Depuis", required=True, ondelete="cascade"
    )
    target_step_id = fields.Many2one(
        "smq.process.template.step", string="Vers", required=True, ondelete="cascade"
    )
    condition = fields.Char(string="Condition")

    @api.constrains("source_step_id", "target_step_id")
    def _check_same_template(self):
        for transition in self:
            if transition.source_step_id.template_id != transition.target_step_id.template_id:
                raise ValidationError(
                    _("Une transition ne peut relier que deux activités du même modèle.")
                )
