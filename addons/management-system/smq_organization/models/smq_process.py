from odoo import fields, models


class SmqProcess(models.Model):
    _inherit = "smq.process"

    site_id = fields.Many2one("smq.site", string="Site")
    department_id = fields.Many2one("hr.department", string="Département")
    smq_activity_ids = fields.Many2many(
        "smq.activity", string="Activités", help="Activités métier couvertes par ce processus."
    )
