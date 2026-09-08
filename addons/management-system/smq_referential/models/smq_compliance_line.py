from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SmqComplianceLine(models.Model):
    _name = "smq.compliance.line"
    _description = "SMQ Compliance Line"
    _order = "requirement_id, process_id"

    requirement_id = fields.Many2one(
        "smq.referential.requirement", string="Exigence", required=True, ondelete="cascade", index=True
    )
    referential_id = fields.Many2one(
        "smq.referential", related="requirement_id.referential_id", store=True, string="Référentiel"
    )
    process_id = fields.Many2one(
        "smq.process", string="Processus concerné", help="Laisser vide pour une évaluation globale."
    )
    applicable = fields.Boolean(string="Applicable", default=True)
    state = fields.Selection(
        [
            ("not_evaluated", "Non évaluée"),
            ("compliant", "Conforme"),
            ("partial", "Partiellement conforme"),
            ("non_compliant", "Non conforme"),
        ],
        default="not_evaluated",
        required=True,
    )
    evidence_document_ids = fields.Many2many(
        "smq.document", string="Documents justificatifs"
    )
    evidence_attachment_ids = fields.Many2many(
        "ir.attachment", string="Preuves / pièces jointes"
    )
    gap_description = fields.Text(string="Écart constaté")
    evaluation_date = fields.Date(string="Date d'évaluation")
    evaluated_by = fields.Many2one("res.users", string="Évalué par")
    company_id = fields.Many2one(
        "res.company", string="Société", default=lambda self: self.env.company, index=True
    )

    _sql_constraints = [
        (
            "requirement_process_uniq",
            "unique(requirement_id, process_id)",
            "Il existe déjà une ligne de conformité pour cette exigence et ce processus.",
        ),
    ]

    @api.constrains("requirement_id", "process_id")
    def _check_requirement_process_unique(self):
        # La contrainte SQL ci-dessus ne détecte pas les doublons quand
        # process_id est vide (Postgres ne considère jamais deux NULL comme
        # égaux) : cas des lignes d'évaluation globales, sans processus.
        for line in self:
            domain = [
                ("requirement_id", "=", line.requirement_id.id),
                ("process_id", "=", line.process_id.id if line.process_id else False),
                ("id", "!=", line.id),
            ]
            if self.search_count(domain):
                raise ValidationError(
                    "Il existe déjà une ligne de conformité pour cette exigence et ce processus."
                )
