from odoo import fields, models


class SmqRiskSourceType(models.Model):
    _name = "smq.risk.source.type"
    _description = "SMQ Risk Source Type"
    _order = "sequence, name"

    # "code" est la clé technique stable utilisée par les contraintes de
    # smq.risk (section 4 de la conception) : le libellé "name" reste
    # librement renommable/traduisible par l'administrateur sans jamais
    # casser cette logique, exactement comme mgmtsystem.nonconformity.stage
    # sépare son "state" technique de son "name" affiché.
    code = fields.Selection(
        [
            ("process", "Processus"),
            ("stakeholder", "Partie intéressée"),
            ("context", "Enjeu / contexte"),
            ("other", "Autre"),
        ],
        required=True,
    )
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Ce type de source existe déjà."),
    ]
