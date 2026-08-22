from odoo import fields, models


class SmqActivity(models.Model):
    _name = "smq.activity"
    _description = "SMQ Activity"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char()
    description = fields.Text()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Société", default=lambda self: self.env.company, index=True
    )
