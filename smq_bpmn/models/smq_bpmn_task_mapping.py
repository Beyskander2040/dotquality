import xml.etree.ElementTree as ET

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# LOT 10 — task_type V1 volontairement restreint (§6 du brief : "ne pas créer
# 30 types prématurément"). L'exemple du §32 utilise "validation" pour
# "Réviser document" ; la liste V1 explicitement énumérée au §6 n'en
# comporte pas — traité ici comme une incohérence mineure du brief (l'énoncé
# "V1 :" est plus spécifique que l'"Exemple" qui le précède) : "Réviser
# document" est donc mappé sur task_type="manual" dans nos propres données de
# démonstration/tests, pas "validation".
_TASK_TYPE_SELECTION = [
    ("document", "Document"),
    ("approval", "Approbation"),
    ("notification", "Notification"),
    ("manual", "Manuel"),
    ("other", "Autre"),
]

_ELEMENT_TYPE_SELECTION = [
    ("task", "Tâche"),
    ("user_task", "Tâche utilisateur"),
    ("service_task", "Tâche de service"),
    ("manual_task", "Tâche manuelle"),
    ("script_task", "Tâche de script"),
    ("exclusive_gateway", "Passerelle exclusive"),
    ("parallel_gateway", "Passerelle parallèle"),
    ("inclusive_gateway", "Passerelle inclusive"),
    ("start_event", "Événement de début"),
    ("end_event", "Événement de fin"),
]

# Familles d'éléments pouvant porter un mapping Odoo métier (§21 : gateways,
# events et flows n'ont pas vocation à en avoir un).
_MAPPABLE_ELEMENT_TYPES = {"task", "user_task", "service_task", "manual_task", "script_task"}


class SmqBpmnTaskMapping(models.Model):
    _name = "smq.bpmn.task.mapping"
    _description = "SMQ BPMN Task Mapping"
    _order = "process_version_id, bpmn_element_id"

    process_version_id = fields.Many2one(
        "smq.process.version", string="Version de processus", required=True, ondelete="cascade", index=True
    )
    bpmn_element_id = fields.Char(string="Identifiant BPMN", required=True)
    element_name = fields.Char(
        string="Nom de l'élément",
        help="Synchronisé depuis le libellé BPMN — ne remplace jamais bpmn_element_id comme clé de liaison.",
    )
    element_type = fields.Selection(_ELEMENT_TYPE_SELECTION, string="Type d'élément BPMN")
    task_type = fields.Selection(_TASK_TYPE_SELECTION, string="Type métier")

    odoo_model_id = fields.Many2one(
        "ir.model", string="Modèle Odoo",
        help="Modèle Odoo concerné (ex. smq.document). Validé par référence directe à ir.model.",
    )
    odoo_model = fields.Char(
        compute="_compute_odoo_model", store=True, readonly=True, string="Modèle technique",
        help="Champ technique dérivé de odoo_model_id — jamais saisi directement.",
    )
    odoo_method = fields.Char(
        string="Méthode Odoo",
        help="Nom de méthode déclaratif uniquement (ex. action_approve). Jamais exécuté par ce module.",
    )
    odoo_action_id = fields.Many2one(
        "ir.actions.actions", string="Action Odoo", ondelete="set null"
    )

    active = fields.Boolean(default=True)
    notes = fields.Text()

    is_orphaned = fields.Boolean(
        string="Orphelin", compute="_compute_is_orphaned", store=False,
        help="Vrai si bpmn_element_id n'existe plus dans le BPMN XML courant de la version.",
    )

    _sql_constraints = [
        (
            "process_version_element_uniq",
            "unique(process_version_id, bpmn_element_id)",
            "Un élément BPMN ne peut avoir qu'un seul mapping principal par version.",
        ),
    ]

    # ------------------------------------------------------------------
    # Mappings orphelins (§39) — détection uniquement, jamais de suppression
    # automatique.
    # ------------------------------------------------------------------

    @api.depends("bpmn_element_id", "process_version_id.bpmn_xml")
    def _compute_is_orphaned(self):
        for mapping in self:
            if not mapping.bpmn_element_id:
                mapping.is_orphaned = False
                continue
            xml_content = mapping.process_version_id.bpmn_xml
            if not xml_content:
                mapping.is_orphaned = True
                continue
            try:
                root = ET.fromstring(xml_content)
            except ET.ParseError:
                mapping.is_orphaned = True
                continue
            found = any(el.get("id") == mapping.bpmn_element_id for el in root.iter())
            mapping.is_orphaned = not found

    # ------------------------------------------------------------------
    # Champ technique dérivé — ir.model est un modèle système dont la
    # lecture est réservée au groupe "Paramètres techniques" (base.group_
    # system) : un Editor/Manager SMQ ordinaire n'y a normalement pas accès.
    # sudo() est utilisé ici uniquement pour lire le nom technique déjà
    # référencé par odoo_model_id (jamais pour élargir ce que l'utilisateur
    # peut lire par ailleurs sur ir.model).
    # ------------------------------------------------------------------

    @api.depends("odoo_model_id")
    def _compute_odoo_model(self):
        for mapping in self:
            mapping.odoo_model = mapping.odoo_model_id.sudo().model if mapping.odoo_model_id else False

    # ------------------------------------------------------------------
    # Validation (§27-29) — introspection uniquement, jamais d'exécution.
    # ------------------------------------------------------------------

    @api.constrains("odoo_model_id")
    def _check_odoo_model_exists(self):
        for mapping in self:
            if mapping.odoo_model_id and mapping.odoo_model_id.sudo().model not in mapping.env:
                raise ValidationError(
                    _(
                        "Le modèle « %(model)s » n'est pas chargé dans l'environnement Odoo actuel.",
                        model=mapping.odoo_model_id.sudo().model,
                    )
                )

    @api.constrains("odoo_model_id", "odoo_method")
    def _check_odoo_method_exists(self):
        for mapping in self:
            if not mapping.odoo_method:
                continue
            if not mapping.odoo_model_id:
                raise ValidationError(
                    _("Une méthode Odoo ne peut être renseignée sans modèle Odoo associé.")
                )
            model_name = mapping.odoo_model_id.sudo().model
            if model_name not in mapping.env:
                continue  # déjà signalé par _check_odoo_model_exists
            target_model = mapping.env[model_name]
            method = getattr(target_model, mapping.odoo_method, None)
            # Introspection pure (getattr/callable) : la méthode n'est jamais
            # appelée pour cette validation.
            if method is None or not callable(method):
                raise ValidationError(
                    _(
                        "La méthode « %(method)s » n'existe pas sur le modèle « %(model)s ».",
                        method=mapping.odoo_method,
                        model=model_name,
                    )
                )

    @api.constrains("odoo_model_id", "odoo_action_id")
    def _check_odoo_action_compatible(self):
        # Validation "best effort" (§29) : uniquement pour les actions dont on
        # peut fiablement déterminer le modèle cible (ir.actions.act_window).
        # Pour les autres types d'action, aucune règle n'est inventée.
        for mapping in self:
            if not (mapping.odoo_action_id and mapping.odoo_model_id):
                continue
            action = mapping.odoo_action_id
            if action.type != "ir.actions.act_window":
                continue
            act_window = mapping.env["ir.actions.act_window"].browse(action.id)
            model_name = mapping.odoo_model_id.sudo().model
            if act_window.exists() and act_window.res_model and act_window.res_model != model_name:
                raise ValidationError(
                    _(
                        "L'action « %(action)s » cible le modèle « %(action_model)s », "
                        "incohérent avec le modèle Odoo « %(model)s » du mapping.",
                        action=action.display_name,
                        action_model=act_window.res_model,
                        model=model_name,
                    )
                )

    # ------------------------------------------------------------------
    # Verrouillage (§25-26) — un mapping suit l'état de sa version : lecture
    # possible dans tous les états, création/modification/suppression
    # possibles seulement si la version est "draft". Aucune exception pour
    # Manager : même règle que le BPMN XML lui-même (LOT 8).
    # ------------------------------------------------------------------

    def _check_version_editable(self, versions=None):
        for version in versions or self.mapped("process_version_id"):
            if version.state != "draft":
                raise ValidationError(
                    _(
                        "La version « %(version)s » n'est plus en brouillon : ses mappings BPMN "
                        "ne peuvent plus être créés, modifiés ou supprimés. Créez une nouvelle "
                        "version pour la faire évoluer.",
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

    # ------------------------------------------------------------------
    # Lecture pour le properties panel (§17) — un seul appel par sélection,
    # jamais de polling. Lecture pure, aucune écriture.
    # ------------------------------------------------------------------

    @api.model
    def get_mapping_for_element(self, process_version_id, bpmn_element_id):
        mapping = self.search(
            [
                ("process_version_id", "=", process_version_id),
                ("bpmn_element_id", "=", bpmn_element_id),
            ],
            limit=1,
        )
        if not mapping:
            return {"found": False, "mappable_types": sorted(_MAPPABLE_ELEMENT_TYPES)}
        return {
            "found": True,
            "id": mapping.id,
            "task_type": mapping.task_type,
            "odoo_model_id": (
                # sudo() : ir.model est réservé au groupe technique, mais son
                # display_name (nom + modèle technique) est ici une simple
                # étiquette d'affichage pour un mapping déjà lu par
                # l'utilisateur courant — pas une élévation de droit sur
                # ir.model lui-même.
                [mapping.odoo_model_id.id, mapping.odoo_model_id.sudo().display_name]
                if mapping.odoo_model_id
                else False
            ),
            "odoo_method": mapping.odoo_method,
            "odoo_action_id": (
                [mapping.odoo_action_id.id, mapping.odoo_action_id.display_name]
                if mapping.odoo_action_id
                else False
            ),
            "active": mapping.active,
            "notes": mapping.notes or "",
            "is_orphaned": mapping.is_orphaned,
            "mappable_types": sorted(_MAPPABLE_ELEMENT_TYPES),
        }

    @api.model
    def get_available_models(self):
        """Liste des modèles Odoo utilisables pour odoo_model_id (§7).

        sudo() : ir.model est réservé au groupe technique (base.group_system)
        alors qu'un Editor/Manager SMQ ordinaire doit pouvoir configurer un
        mapping — seuls id/model/name sont exposés, aucune autre métadonnée
        technique (champs, contraintes...).
        """
        return self.env["ir.model"].sudo().search_read([], ["id", "model", "name"], order="model")

    @api.model
    def get_available_actions(self):
        """Liste des actions fenêtre utilisables pour odoo_action_id (§9)."""
        return self.env["ir.actions.act_window"].sudo().search_read(
            [], ["id", "name", "res_model"], order="name", limit=500
        )
