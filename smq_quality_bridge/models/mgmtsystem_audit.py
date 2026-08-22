from odoo import _, api, fields, models


class MgmtsystemAudit(models.Model):
    _inherit = "mgmtsystem.audit"

    # La traduction fr_FR livrée par mgmtsystem_audit ("Ouverte"/"Fermée",
    # accord féminin implicite du module OCA) fonctionne déjà, mais diffère
    # du vocabulaire SMQ déjà en usage pour le même concept sur les NC et la
    # revue de direction ("Clôturée") — harmonisation uniquement, avec
    # l'accord masculin correct ("un audit"). Valeurs techniques ("open"/
    # "done") inchangées.
    state = fields.Selection([("open", "Ouvert"), ("done", "Clôturé")])

    quality_process_id = fields.Many2one(
        "smq.process", string="Processus", tracking=True
    )
    smq_document_ids = fields.Many2many(
        "smq.document",
        "smq_audit_document_rel",
        "audit_id",
        "document_id",
        string="Documents audités",
    )
    smq_document_count = fields.Integer(compute="_compute_smq_document_count")
    nonconformity_count = fields.Integer(compute="_compute_nonconformity_count")
    imp_opp_count = fields.Integer(compute="_compute_imp_opp_count")

    @api.depends("smq_document_ids")
    def _compute_smq_document_count(self):
        for audit in self:
            audit.smq_document_count = len(audit.smq_document_ids)

    @api.depends("nonconformity_ids")
    def _compute_nonconformity_count(self):
        for audit in self:
            audit.nonconformity_count = len(audit.nonconformity_ids)

    @api.depends("imp_opp_ids")
    def _compute_imp_opp_count(self):
        for audit in self:
            audit.imp_opp_count = len(audit.imp_opp_ids)

    def action_view_smq_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Documents audités"),
            "res_model": "smq.document",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.smq_document_ids.ids)],
        }

    def action_view_nonconformities(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Non-conformités"),
            "res_model": "mgmtsystem.nonconformity",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.nonconformity_ids.ids)],
            "context": {"default_quality_process_id": self.quality_process_id.id},
        }

    def action_view_imp_opp(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Actions / améliorations"),
            "res_model": "mgmtsystem.action",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.imp_opp_ids.ids)],
            "context": {"default_type_action": "improvement"},
        }
