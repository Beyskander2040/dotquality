from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SmqSupplierEvaluationLine(models.Model):
    _name = "smq.supplier.evaluation.line"
    _description = "SMQ Supplier Evaluation Line"
    _order = "id"

    evaluation_id = fields.Many2one(
        "smq.supplier.evaluation", required=True, ondelete="cascade", index=True
    )
    criterion_id = fields.Many2one(
        "smq.supplier.criterion", string="Critère", required=True
    )
    weight = fields.Integer(related="criterion_id.weight", string="Pondération")
    score = fields.Integer(string="Note", required=True, default=0)
    comment = fields.Char(string="Commentaire")

    @api.constrains("score")
    def _check_score_range(self):
        for line in self:
            if not 0 <= line.score <= 5:
                raise ValidationError(_("La note doit être comprise entre 0 et 5."))
