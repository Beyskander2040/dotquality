from odoo import api, fields, models


class SmqReferential(models.Model):
    _name = "smq.referential"
    _description = "SMQ Referential"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char()
    version = fields.Char(string="Version", help="ex. 2015")
    issuing_body = fields.Char(string="Organisme émetteur", help="ex. ISO, AFNOR, client...")
    description = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Société", default=lambda self: self.env.company, index=True
    )
    requirement_ids = fields.One2many(
        "smq.referential.requirement", "referential_id", string="Exigences"
    )
    requirement_count = fields.Integer(compute="_compute_requirement_count")

    _sql_constraints = [
        ("code_uniq", "unique(code, company_id)", "Le code du référentiel doit être unique."),
    ]

    @api.depends("requirement_ids")
    def _compute_requirement_count(self):
        for referential in self:
            referential.requirement_count = len(referential.requirement_ids)

    def action_view_requirements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Exigences",
            "res_model": "smq.referential.requirement",
            "view_mode": "tree,form",
            "domain": [("referential_id", "=", self.id)],
            "context": {"default_referential_id": self.id},
        }

    def action_generate_compliance_lines(self):
        """Crée une ligne de conformité (globale, sans processus) pour chaque
        exigence terminale (sans sous-exigence) qui n'en a pas encore."""
        ComplianceLine = self.env["smq.compliance.line"]
        for referential in self:
            leaf_requirements = referential.requirement_ids.filtered(lambda r: not r.child_ids)
            existing = ComplianceLine.search(
                [
                    ("requirement_id", "in", leaf_requirements.ids),
                    ("process_id", "=", False),
                ]
            ).requirement_id
            missing = leaf_requirements - existing
            for requirement in missing:
                ComplianceLine.create({"requirement_id": requirement.id})
