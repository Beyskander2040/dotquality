from odoo import fields, models


class SmqRiskProbability(models.Model):
    _name = "smq.risk.probability"
    _description = "SMQ Risk Probability Scale"
    _order = "sequence, value"

    name = fields.Char(required=True, translate=True)
    value = fields.Integer(required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", string="Société")
