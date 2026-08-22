from odoo import models


class SmqDashboardTile(models.Model):
    _inherit = "smq.dashboard.tile"

    def _get_count(self):
        if self.key == "supplier":
            return self.env["smq.supplier.evaluation"].search_count([])
        return super()._get_count()
