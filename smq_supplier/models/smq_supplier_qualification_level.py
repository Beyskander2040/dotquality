from odoo import fields, models


class SmqSupplierQualificationLevel(models.Model):
    _name = "smq.supplier.qualification.level"
    _description = "SMQ Supplier Qualification Level"
    _order = "sequence, min_score"

    name = fields.Char(required=True, translate=True)
    min_score = fields.Integer(required=True)
    max_score = fields.Integer(required=True)
    color = fields.Integer(string="Couleur")
    sequence = fields.Integer(default=10)
