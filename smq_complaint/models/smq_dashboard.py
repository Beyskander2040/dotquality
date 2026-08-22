from odoo import models


class SmqDashboardTile(models.Model):
    _inherit = "smq.dashboard.tile"

    def _get_domain(self):
        if self.key == "complaint":
            return [("state", "!=", "cloturee")]
        return super()._get_domain()

    def _get_count(self):
        if self.key == "complaint":
            return self.env["smq.complaint"].search_count(self._get_domain())
        return super()._get_count()
