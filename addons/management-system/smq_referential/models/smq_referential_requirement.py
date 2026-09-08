from odoo import api, fields, models


class SmqReferentialRequirement(models.Model):
    _name = "smq.referential.requirement"
    _description = "SMQ Referential Requirement"
    _order = "sequence, code"

    referential_id = fields.Many2one(
        "smq.referential", string="Référentiel", required=True, ondelete="cascade", index=True
    )
    parent_id = fields.Many2one(
        "smq.referential.requirement", string="Exigence parente", ondelete="cascade"
    )
    child_ids = fields.One2many("smq.referential.requirement", "parent_id", string="Sous-exigences")
    code = fields.Char(string="Clause", help="ex. 7.5.3.2")
    name = fields.Char(required=True)
    description = fields.Text()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    complete_name = fields.Char(compute="_compute_complete_name", store=True, recursive=True)
    compliance_line_ids = fields.One2many(
        "smq.compliance.line", "requirement_id", string="Lignes de conformité"
    )
    compliance_count = fields.Integer(compute="_compute_compliance_count")

    @api.depends("code", "name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for requirement in self:
            label = f"{requirement.code} — {requirement.name}" if requirement.code else requirement.name
            if requirement.parent_id:
                requirement.complete_name = f"{requirement.parent_id.complete_name} / {label}"
            else:
                requirement.complete_name = label

    @api.depends("compliance_line_ids")
    def _compute_compliance_count(self):
        for requirement in self:
            requirement.compliance_count = len(requirement.compliance_line_ids)
