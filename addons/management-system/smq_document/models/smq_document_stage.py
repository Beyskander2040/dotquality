from odoo import fields, models


class SmqDocumentStage(models.Model):
    _name = "smq.document.stage"
    _description = "SMQ Document Stage"
    _order = "sequence"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(help="Colonne repliée par défaut dans la vue kanban.")

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Le code de statut doit être unique."),
    ]
