from odoo import fields, models


class SmqScope(models.Model):
    _name = "smq.scope"
    _description = "SMQ Scope (périmètre de certification)"
    _order = "name"

    name = fields.Char(required=True)
    description = fields.Text(string="Énoncé du périmètre")
    site_ids = fields.Many2many("smq.site", string="Sites couverts")
    activity_ids = fields.Many2many("smq.activity", string="Activités couvertes")
    process_ids = fields.Many2many("smq.process", string="Processus concernés")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Société", default=lambda self: self.env.company, index=True
    )
