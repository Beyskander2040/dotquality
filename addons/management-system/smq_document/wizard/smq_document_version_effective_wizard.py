from odoo import fields, models


class SmqDocumentVersionEffectiveWizard(models.TransientModel):
    _name = "smq.document.version.effective.wizard"
    _description = "Date d'entrée en vigueur d'une version de document"

    version_id = fields.Many2one("smq.document.version", required=True)
    effective_date = fields.Date(
        string="Date d'entrée en vigueur",
        required=True,
        default=fields.Date.context_today,
    )

    def action_confirm(self):
        self.ensure_one()
        effective_datetime = fields.Datetime.to_datetime(self.effective_date)
        self.version_id.action_set_effective_confirm(effective_datetime)
