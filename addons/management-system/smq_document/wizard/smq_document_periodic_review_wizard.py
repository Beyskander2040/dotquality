from odoo import fields, models


class SmqDocumentPeriodicReviewWizard(models.TransientModel):
    _name = "smq.document.periodic.review.wizard"
    _description = "Revue périodique d'un document"

    document_id = fields.Many2one("smq.document", required=True)
    review_date = fields.Date(
        string="Date de la revue", required=True, default=fields.Date.context_today
    )
    comment = fields.Text(string="Observation")

    def action_confirm(self):
        self.ensure_one()
        review_datetime = fields.Datetime.to_datetime(self.review_date)
        self.document_id.action_periodic_review_confirm(review_datetime, self.comment)
