from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class SmqProcessVersionSaveAsTemplateWizard(models.TransientModel):
    _name = "smq.process.version.save.as.template.wizard"
    _description = "Enregistrer une version comme modèle de processus"

    version_id = fields.Many2one("smq.process.version", required=True)
    template_name = fields.Char(string="Nom du modèle", required=True)
    description = fields.Text()
    category_id = fields.Many2one("smq.process.category", string="Catégorie")

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group("smq_quality.group_smq_admin"):
            raise UserError(_("Seul un Administrateur SMQ peut créer un modèle de processus."))
        version = self.version_id
        if not version.step_ids:
            raise ValidationError(
                _(
                    "Cette version n'a pas de description structurée (tableau d'activités) — "
                    "seule une version décrite via ce tableau peut être enregistrée comme modèle."
                )
            )

        Template = self.env["smq.process.template"]
        template = Template.create(
            {
                "name": self.template_name,
                "description": self.description,
                "category_id": self.category_id.id or version.process_id.category_id.id,
            }
        )
        TemplateStep = self.env["smq.process.template.step"]
        new_step_id_by_old_id = {}
        for step in version.step_ids:
            template_step = TemplateStep.create(
                {
                    "template_id": template.id,
                    "sequence": step.sequence,
                    "code": step.code,
                    "name": step.name,
                    "step_type": step.step_type,
                    "description": step.description,
                }
            )
            new_step_id_by_old_id[step.id] = template_step.id
        TemplateTransition = self.env["smq.process.template.step.transition"]
        for transition in version.transition_ids:
            TemplateTransition.create(
                {
                    "template_id": template.id,
                    "source_step_id": new_step_id_by_old_id[transition.source_step_id.id],
                    "target_step_id": new_step_id_by_old_id[transition.target_step_id.id],
                    "condition": transition.condition,
                    "sequence": transition.sequence,
                }
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Modèle créé"),
            "res_model": "smq.process.template",
            "view_mode": "form",
            "res_id": template.id,
            "target": "current",
        }
