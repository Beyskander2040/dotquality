from odoo import fields, models


class DocumentPage(models.Model):
    _inherit = "document.page"

    document_ids = fields.One2many(
        "ir.attachment",
        "res_id",
        string="Fichiers joints",
        domain=lambda self: [("res_model", "=", self._name)],
        help="Fichiers (PDF, Word, ...) associés à ce document. "
        "Les fichiers précédemment déposés restent listés ici.",
    )
