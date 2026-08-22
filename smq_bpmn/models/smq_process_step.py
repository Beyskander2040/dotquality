from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# LOT 12 §6 — V1 volontairement restreinte (mêmes principes que task_type au
# LOT 10 : "ne pas ajouter arbitrairement des types BPMN supplémentaires si
# le besoin n'est pas démontré").
_STEP_TYPE_SELECTION = [
    ("manual", "Manuel"),
    ("document", "Document"),
    ("approval", "Approbation"),
    ("notification", "Notification"),
    ("gateway", "Passerelle"),
    ("start", "Début"),
    ("end", "Fin"),
]


class SmqProcessStep(models.Model):
    _name = "smq.process.step"
    _description = "SMQ Process Step (description structurée)"
    _order = "process_version_id, sequence, id"

    process_version_id = fields.Many2one(
        "smq.process.version", string="Version de processus", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(required=True, default=10)
    code = fields.Char(required=True)
    name = fields.Char(required=True)
    step_type = fields.Selection(_STEP_TYPE_SELECTION, string="Type", required=True)
    responsible_user_id = fields.Many2one(
        "res.users", string="Responsable",
        help="Métadonnée métier uniquement — aucun mécanisme d'assignation runtime.",
    )
    description = fields.Text(
        string="Description",
        help="Deviendra la documentation BPMN (<bpmn:documentation>) de l'élément généré.",
    )

    _sql_constraints = [
        (
            "process_version_code_uniq",
            "unique(process_version_id, code)",
            "Le code d'une étape doit être unique au sein d'une même version.",
        ),
    ]

    # ------------------------------------------------------------------
    # Verrouillage (même principe que smq.bpmn.task.mapping, LOT 10) : une
    # étape suit l'état de sa version — éditable seulement en draft, sans
    # exception de rôle.
    # ------------------------------------------------------------------

    def _check_version_editable(self, versions=None):
        for version in versions or self.mapped("process_version_id"):
            if version.state != "draft":
                raise ValidationError(
                    _(
                        "La version « %(version)s » n'est plus en brouillon : sa description "
                        "structurée ne peut plus être créée, modifiée ou supprimée. Créez une "
                        "nouvelle version pour la faire évoluer.",
                        version=version.display_name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        version_ids = {v.get("process_version_id") for v in vals_list if v.get("process_version_id")}
        self._check_version_editable(self.env["smq.process.version"].browse(version_ids))
        return super().create(vals_list)

    def write(self, vals):
        self._check_version_editable()
        if "process_version_id" in vals:
            self._check_version_editable(self.env["smq.process.version"].browse(vals["process_version_id"]))
        return super().write(vals)

    def unlink(self):
        self._check_version_editable()
        return super().unlink()
