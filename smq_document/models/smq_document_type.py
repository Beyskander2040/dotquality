from odoo import fields, models


class SmqDocumentType(models.Model):
    _name = "smq.document.type"
    _description = "SMQ Document Type"
    _order = "sequence, name"

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    code_prefix = fields.Char(required=True, help="Préfixe utilisé pour générer le code (ex. PROC).")
    requires_process = fields.Boolean(
        string="Processus obligatoire",
        help="Si activé, un document de ce type doit être associé à un processus SMQ.",
    )
    review_period = fields.Integer(
        string="Périodicité de révision (mois)",
        help="Utilisé pour calculer la prochaine date de révision par défaut. Laisser à 0 pour ne pas en calculer.",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_prefix_uniq", "unique(code_prefix)", "Le préfixe de code doit être unique."),
    ]
