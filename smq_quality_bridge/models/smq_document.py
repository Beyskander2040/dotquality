from odoo import api, fields, models


class SmqDocument(models.Model):
    _inherit = "smq.document"

    nonconformity_ids = fields.Many2many(
        "mgmtsystem.nonconformity",
        "smq_nonconformity_document_rel",
        "document_id",
        "nonconformity_id",
        string="Non-conformités liées",
    )
    nonconformity_count = fields.Integer(compute="_compute_nonconformity_count")
    audit_ids = fields.Many2many(
        "mgmtsystem.audit",
        "smq_audit_document_rel",
        "document_id",
        "audit_id",
        string="Audits liés",
    )
    audit_count = fields.Integer(compute="_compute_audit_count")

    @api.depends("nonconformity_ids")
    def _compute_nonconformity_count(self):
        for doc in self:
            doc.nonconformity_count = len(doc.nonconformity_ids)

    @api.depends("audit_ids")
    def _compute_audit_count(self):
        for doc in self:
            doc.audit_count = len(doc.audit_ids)

    def action_view_nonconformities(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Non-conformités",
            "res_model": "mgmtsystem.nonconformity",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.nonconformity_ids.ids)],
        }

    def action_view_audits(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Audits",
            "res_model": "mgmtsystem.audit",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.audit_ids.ids)],
        }
