from odoo import api, fields, models


class SmqProcess(models.Model):
    _inherit = "smq.process"

    nonconformity_ids = fields.One2many(
        "mgmtsystem.nonconformity", "quality_process_id", string="Non-conformités"
    )
    nonconformity_count = fields.Integer(compute="_compute_nonconformity_count")
    audit_ids = fields.One2many(
        "mgmtsystem.audit", "quality_process_id", string="Audits"
    )
    audit_count = fields.Integer(compute="_compute_audit_count")

    @api.depends("nonconformity_ids")
    def _compute_nonconformity_count(self):
        for process in self:
            process.nonconformity_count = len(process.nonconformity_ids)

    @api.depends("audit_ids")
    def _compute_audit_count(self):
        for process in self:
            process.audit_count = len(process.audit_ids)

    def action_view_audits(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Audits",
            "res_model": "mgmtsystem.audit",
            "view_mode": "tree,form",
            "domain": [("quality_process_id", "=", self.id)],
            "context": {"default_quality_process_id": self.id},
        }

    def action_view_nonconformities(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Non-conformités",
            "res_model": "mgmtsystem.nonconformity",
            "view_mode": "tree,form",
            "domain": [("quality_process_id", "=", self.id)],
            "context": {"default_quality_process_id": self.id},
        }
