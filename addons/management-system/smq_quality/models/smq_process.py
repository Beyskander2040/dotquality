from odoo import api, fields, models


class SmqProcessCategory(models.Model):
    _name = "smq.process.category"
    _description = "SMQ Process Category"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class SmqProcess(models.Model):
    _name = "smq.process"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "SMQ Quality Process"
    _order = "code"

    code = fields.Char(required=True, tracking=True)
    name = fields.Char(required=True, tracking=True)
    description = fields.Text()
    responsible_id = fields.Many2one("res.users", string="Responsable", tracking=True)
    category_id = fields.Many2one(
        "smq.process.category", string="Catégorie", tracking=True
    )
    status = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("active", "Actif"),
            ("archived", "Archivé"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Société",
        default=lambda self: self.env.company,
        index=True,
    )

    _sql_constraints = [
        ("code_uniq", "unique(code, company_id)", "Le code du processus doit être unique."),
    ]

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.code} - {rec.name}" if rec.code else rec.name
