from odoo import _, fields, models


class SmqProcessTemplateImportWizard(models.TransientModel):
    _name = "smq.process.template.import.wizard"
    _description = "Importer un modèle de processus"

    template_id = fields.Many2one("smq.process.template", required=True)
    process_code = fields.Char(string="Code du nouveau processus", required=True)
    process_name = fields.Char(string="Nom du nouveau processus", required=True)
    category_id = fields.Many2one("smq.process.category", string="Catégorie")
    responsible_id = fields.Many2one(
        "res.users", string="Responsable", default=lambda self: self.env.uid
    )

    def action_confirm(self):
        self.ensure_one()
        process = self.template_id.action_import(
            self.process_code,
            self.process_name,
            category_id=self.category_id.id,
            responsible_id=self.responsible_id.id,
        )
        # On ouvre directement la version importée (où vivent les activités
        # et le diagramme), pas la fiche du processus — sans quoi les
        # activités/le BPMN sont là mais invisibles sans un clic
        # supplémentaire sur le bouton statistique "Versions", ce qui a été
        # rapporté à tort comme "les activités ne sont pas importées".
        version = process.version_ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Version importée"),
            "res_model": "smq.process.version",
            "view_mode": "form",
            "res_id": version.id,
            "target": "current",
        }
