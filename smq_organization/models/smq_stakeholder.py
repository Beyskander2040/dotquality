from odoo import fields, models


class SmqStakeholder(models.Model):
    _name = "smq.stakeholder"
    _description = "SMQ Interested Party"
    _order = "name"

    name = fields.Char(required=True)
    category = fields.Selection(
        [
            ("internal", "Interne"),
            ("customer", "Client"),
            ("supplier", "Fournisseur"),
            ("authority", "Autorité / Régulateur"),
            ("shareholder", "Actionnaire"),
            ("other", "Autre"),
        ],
        default="other",
        required=True,
    )
    partner_id = fields.Many2one("res.partner", string="Contact associé")
    expectations = fields.Text(string="Attentes / exigences")
    influence_level = fields.Selection(
        [("low", "Faible"), ("medium", "Moyenne"), ("high", "Élevée")],
        string="Niveau d'influence",
        default="medium",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Société", default=lambda self: self.env.company, index=True
    )
