from odoo import api, fields, models


class SmqProcess(models.Model):
    """LOT 8 : ajoute uniquement le lien vers les versions BPMN du processus.
    Aucun champ métier déjà présent (code, name, description, active,
    responsible_id, company_id, status...) n'est redéfini ici."""

    _inherit = "smq.process"

    version_ids = fields.One2many(
        "smq.process.version", "process_id", string="Versions BPMN"
    )
    current_version_id = fields.Many2one(
        "smq.process.version",
        string="Version BPMN courante",
        copy=False,
        help="Version actuellement en vigueur (effective) pour ce processus. "
        "Maintenu automatiquement par action_make_effective().",
    )
    version_count = fields.Integer(compute="_compute_version_count")

    @api.depends("version_ids")
    def _compute_version_count(self):
        for process in self:
            process.version_count = len(process.version_ids)

    def action_view_process_versions(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "smq_bpmn.action_smq_process_version"
        )
        action["domain"] = [("process_id", "=", self.id)]
        action["context"] = {"default_process_id": self.id}
        return action
