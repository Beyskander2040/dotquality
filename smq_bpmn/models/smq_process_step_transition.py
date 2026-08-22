from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SmqProcessStepTransition(models.Model):
    _name = "smq.process.step.transition"
    _description = "SMQ Process Step Transition (description structurée)"
    _order = "process_version_id, sequence, id"

    process_version_id = fields.Many2one(
        "smq.process.version", string="Version de processus", required=True, ondelete="cascade", index=True
    )
    source_step_id = fields.Many2one(
        "smq.process.step", string="Depuis", required=True, ondelete="cascade"
    )
    target_step_id = fields.Many2one(
        "smq.process.step", string="Vers", required=True, ondelete="cascade"
    )
    condition = fields.Char(
        string="Condition",
        help="Texte déclaratif uniquement (ex. « conforme »). Deviendra l'étiquette du "
        "sequenceFlow généré — jamais une expression exécutable.",
    )
    sequence = fields.Integer(required=True, default=10)

    # ------------------------------------------------------------------
    # Contraintes (§10) : même version pour la transition et ses deux
    # extrémités, pas de self-loop, pas de transition inter-version.
    # ------------------------------------------------------------------

    @api.constrains("process_version_id", "source_step_id", "target_step_id")
    def _check_same_version(self):
        for transition in self:
            versions = {
                transition.process_version_id.id,
                transition.source_step_id.process_version_id.id,
                transition.target_step_id.process_version_id.id,
            }
            if len(versions) > 1:
                raise ValidationError(
                    _(
                        "Une transition doit relier deux étapes de la même version de "
                        "processus — jamais deux versions différentes."
                    )
                )

    @api.constrains("source_step_id", "target_step_id")
    def _check_no_self_loop(self):
        for transition in self:
            if transition.source_step_id == transition.target_step_id:
                raise ValidationError(
                    _("Une étape ne peut pas être reliée à elle-même (« %s »).")
                    % transition.source_step_id.name
                )

    # ------------------------------------------------------------------
    # Verrouillage — même principe que smq.process.step.
    # ------------------------------------------------------------------

    def _check_version_editable(self, versions=None):
        for version in versions or self.mapped("process_version_id"):
            if version.state != "draft":
                raise ValidationError(
                    _(
                        "La version « %(version)s » n'est plus en brouillon : ses transitions "
                        "ne peuvent plus être créées, modifiées ou supprimées. Créez une "
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
