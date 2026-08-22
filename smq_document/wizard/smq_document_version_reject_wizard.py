from odoo import fields, models


class SmqDocumentVersionRejectWizard(models.TransientModel):
    _name = "smq.document.version.reject.wizard"
    _description = "Motif de rejet d'une version de document"

    version_id = fields.Many2one("smq.document.version", required=True)
    reason = fields.Text(string="Motif du rejet", required=True)

    def action_confirm(self):
        self.ensure_one()
        self.version_id.action_reject_confirm(self.reason)
