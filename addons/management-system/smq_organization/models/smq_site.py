from odoo import fields, models


class SmqSite(models.Model):
    _name = "smq.site"
    _description = "SMQ Site"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char()
    address_id = fields.Many2one("res.partner", string="Adresse")
    description = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Société", default=lambda self: self.env.company, index=True
    )

    _sql_constraints = [
        ("code_uniq", "unique(code, company_id)", "Le code du site doit être unique."),
    ]
