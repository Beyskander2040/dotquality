from odoo import fields, models


class SmqRiskCriticalityLevel(models.Model):
    _name = "smq.risk.criticality.level"
    _description = "SMQ Risk Criticality Band"
    _order = "sequence, min_score"

    name = fields.Char(required=True, translate=True)
    min_score = fields.Integer(required=True)
    max_score = fields.Integer(required=True)
    color = fields.Integer(string="Couleur")
    sequence = fields.Integer(default=10)
