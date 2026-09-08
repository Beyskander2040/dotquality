from odoo import fields, models


class SmqProcessVersionRejectWizard(models.TransientModel):
    """LOT 11 — mêmes principes que
    smq_document/wizard/smq_document_version_reject_wizard.py : motif de
    rejet obligatoire, capturé via un assistant plutôt qu'un paramètre de
    méthode nu."""

    _name = "smq.process.version.reject.wizard"
    _description = "Motif de rejet d'une version de processus BPMN"

    version_id = fields.Many2one("smq.process.version", required=True)
    reason = fields.Text(string="Motif du rejet", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.version_id.action_reject_confirm(self.reason)
