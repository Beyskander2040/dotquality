from odoo import _, models, fields


class SmqDocument(models.Model):
    _inherit = "smq.document"

    # Relation inverse de smq.bpmn.task.mapping.procedure_document_id/
    # form_document_id : ces deux champs vivent sur le mapping (côté
    # smq_bpmn, qui dépend de smq_document — jamais l'inverse), donc cette
    # extension est le seul endroit possible pour rendre la relation visible
    # depuis la fiche du document lui-même. Calculé à la lecture, jamais
    # stocké : dépend de mappings potentiellement répartis sur plusieurs
    # versions de plusieurs processus.
    bpmn_task_mapping_count = fields.Integer(
        compute="_compute_bpmn_task_mapping_count",
        help="Nombre d'activités (tâches BPMN) qui référencent ce document comme "
        "Procédure ou comme Formulaire.",
    )

    def _compute_bpmn_task_mapping_count(self):
        Mapping = self.env["smq.bpmn.task.mapping"]
        for doc in self:
            doc.bpmn_task_mapping_count = Mapping.search_count(
                ["|", ("procedure_document_id", "=", doc.id), ("form_document_id", "=", doc.id)]
            )

    def action_view_bpmn_task_mappings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Activités BPMN liées"),
            "res_model": "smq.bpmn.task.mapping",
            "view_mode": "tree,form",
            "domain": [
                "|",
                ("procedure_document_id", "=", self.id),
                ("form_document_id", "=", self.id),
            ],
        }
