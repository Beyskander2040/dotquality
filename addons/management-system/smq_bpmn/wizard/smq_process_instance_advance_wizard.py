from odoo import api, fields, models


class SmqProcessInstanceAdvanceWizard(models.TransientModel):
    """LOT 13 — un seul point d'entrée UI pour action_advance(), qu'il y ait
    une seule branche possible (cas courant : terminer une tâche humaine) ou
    plusieurs (passerelle exclusive nécessitant un choix humain, §19 du
    LOT 12 : les conditions sont du texte déclaratif, jamais une expression
    évaluée automatiquement)."""

    _name = "smq.process.instance.advance.wizard"
    _description = "Avancer une instance de processus BPMN"

    instance_id = fields.Many2one("smq.process.instance", required=True)
    chosen_flow_id = fields.Selection(selection="_selection_branches", string="Branche à suivre")

    @api.model
    def _selection_branches(self):
        instance_id = self.env.context.get("default_instance_id")
        if not instance_id:
            return []
        return self.env["smq.process.instance"].browse(instance_id).get_pending_branches()

    def action_confirm(self):
        self.ensure_one()
        self.instance_id.action_advance(self.chosen_flow_id or None)
