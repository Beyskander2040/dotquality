from odoo import fields, models


class SmqSupplierCriterion(models.Model):
    _name = "smq.supplier.criterion"
    _description = "SMQ Supplier Evaluation Criterion"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    weight = fields.Integer(required=True, default=1, help="Pondération relative du critère.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
