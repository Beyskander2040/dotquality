import hashlib
import re
import xml.etree.ElementTree as ET

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .smq_bpmn_generator import generate_bpmn_xml
from .smq_bpmn_instance_engine import parse_graph

# Champs figés dès qu'une version quitte le brouillon (mêmes principes que
# smq_document/models/smq_document_version.py : une version qui n'est plus en
# brouillon ne se modifie plus, seule une nouvelle version le peut). "state"
# n'est pas dans cet ensemble : il est protégé séparément ci-dessous, y
# compris en brouillon (pas de changement d'état arbitraire depuis les vues).
# Inchangé depuis le LOT 8 : "review"/"approved"/"effective"/"rejected"/
# "obsolete" sont tous des états "non draft" et restent donc tous verrouillés
# au même titre que l'ancien "to_validate" — le brief LOT 11 ne mentionne pas
# explicitement "review" dans sa liste d'immutabilité (§6), mais le principe
# déjà établi ici (et dans smq_document_version.py) est "seul draft est
# éditable" ; y déroger pour "review" serait un recul de rigueur non demandé.
_LOCKED_FIELDS = {"process_id", "version", "name", "bpmn_xml"}

# Clé de contexte utilisée par les méthodes internes du workflow pour être
# seules autorisées à modifier "state" — un write() direct (UI générique,
# import, RPC) sur ce champ est refusé.
_ALLOW_STATE_WRITE_KEY = "smq_bpmn_allow_state_write"

# LOT 11 : machine à 6 états. "to_validate" (LOT 8) devient "review" ;
# l'ancien "approved" (qui faisait à la fois office de "validé" ET de
# "version courante en vigueur") est scindé en deux états distincts
# "approved" (validé, pas encore en vigueur) et "effective" (en vigueur) —
# §3/§24 du brief. Libellés en français, cohérents avec le reste du module
# (le brief donne des libellés anglais au §3, traités comme un gabarit
# indicatif, pas une exigence d'interface — toutes les autres chaînes de ce
# module sont en français).
_STATE_SELECTION = [
    ("draft", "Brouillon"),
    ("review", "En révision"),
    ("approved", "Approuvée"),
    ("effective", "En vigueur"),
    ("rejected", "Rejetée"),
    ("obsolete", "Obsolète"),
]
_STATE_LABELS = dict(_STATE_SELECTION)

_MAPPABLE_ELEMENT_TYPES = ("task", "user_task", "service_task", "manual_task", "script_task")

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")


class SmqProcessVersion(models.Model):
    _name = "smq.process.version"
    _inherit = ["mail.thread"]
    _description = "SMQ Process Version (BPMN)"
    _order = "process_id, id desc"

    process_id = fields.Many2one(
        "smq.process", string="Processus", required=True, ondelete="cascade", index=True
    )
    version = fields.Char(required=True)
    name = fields.Char(string="Libellé")
    state = fields.Selection(
        _STATE_SELECTION, default="draft", required=True, copy=False, tracking=True
    )
    bpmn_xml = fields.Text(string="BPMN XML")
    bpmn_checksum = fields.Char(
        string="Checksum BPMN (SHA-256)", compute="_compute_bpmn_checksum", store=True
    )
    created_by = fields.Many2one(
        "res.users", string="Auteur", default=lambda self: self.env.user, copy=False
    )
    created_date = fields.Datetime(
        string="Date de création", default=fields.Datetime.now, copy=False
    )
    approved_by = fields.Many2one(
        "res.users", string="Approuvé par", readonly=True, copy=False
    )
    approved_date = fields.Datetime(
        string="Date d'approbation", readonly=True, copy=False
    )
    effective_by = fields.Many2one(
        "res.users", string="Mise en vigueur par", readonly=True, copy=False
    )
    effective_date = fields.Datetime(
        string="Date de mise en vigueur", readonly=True, copy=False
    )
    rejected_by = fields.Many2one(
        "res.users", string="Rejetée par", readonly=True, copy=False
    )
    rejected_date = fields.Datetime(
        string="Date de rejet", readonly=True, copy=False
    )
    rejection_reason = fields.Text(
        string="Motif du rejet", readonly=True, copy=False
    )
    obsolete_date = fields.Datetime(
        string="Date d'obsolescence", readonly=True, copy=False
    )
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True)

    # LOT 10 : mappings BPMN → Odoo portés par cette version (source de
    # vérité pour task_type/odoo_model/odoo_method/odoo_action/active — le
    # BPMN XML reste seul responsable de id/type/name/documentation, §24).
    mapping_ids = fields.One2many(
        "smq.bpmn.task.mapping", "process_version_id", string="Mappings BPMN"
    )

    # LOT 12 — description structurée du processus, transformable en BPMN
    # XML de façon déterministe (smq_bpmn_generator.py). Reste une couche
    # séparée du BPMN XML lui-même : régénérer ne modifie jamais mapping_ids
    # (§24) et ne touche jamais l'état de la version (§26).
    step_ids = fields.One2many(
        "smq.process.step", "process_version_id", string="Étapes (description structurée)"
    )
    transition_ids = fields.One2many(
        "smq.process.step.transition", "process_version_id", string="Transitions (description structurée)"
    )

    # LOT 13 — instances d'exécution démarrées depuis cette version.
    instance_ids = fields.One2many(
        "smq.process.instance", "process_version_id", string="Instances"
    )
    instance_count = fields.Integer(compute="_compute_instance_count")

    _sql_constraints = [
        (
            "process_version_uniq",
            "unique(process_id, version)",
            "Cette version existe déjà pour ce processus.",
        ),
    ]

    @api.depends("process_id.code", "version", "name")
    def _compute_display_name(self):
        for rec in self:
            base = f"{rec.process_id.code} {rec.version}" if rec.process_id else (rec.version or "")
            rec.display_name = f"{base} — {rec.name}" if rec.name else base

    @api.depends("bpmn_xml")
    def _compute_bpmn_checksum(self):
        for rec in self:
            rec.bpmn_checksum = (
                hashlib.sha256(rec.bpmn_xml.encode("utf-8")).hexdigest()
                if rec.bpmn_xml
                else False
            )

    @api.depends("instance_ids")
    def _compute_instance_count(self):
        for version in self:
            version.instance_count = len(version.instance_ids)

    @api.constrains("state")
    def _check_single_effective_version(self):
        """Garde-fou défensif : action_make_effective() garantit déjà cette
        règle en séquençant ses écritures, mais toute autre voie d'écriture
        de "state" reste bloquée ici. LOT 11 : la contraine portait sur
        "approved" (LOT 8) ; elle porte maintenant sur "effective", le seul
        état désormais désigné comme "version courante en vigueur"."""
        for version in self:
            if version.state != "effective":
                continue
            others = version.process_id.version_ids.filtered(
                lambda v: v.state == "effective" and v.id != version.id
            )
            if others:
                raise ValidationError(
                    _("Un processus ne peut avoir qu'une seule version en vigueur (effective) à la fois.")
                )

    # ------------------------------------------------------------------
    # Verrouillage — côté Python, jamais seulement via readonly dans les vues.
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        # LOT 11 : ferme une lacune identifiée lors de l'analyse — rien
        # n'empêchait jusqu'ici un create() de démarrer directement dans un
        # état autre que "draft" (le champ a un défaut, mais aucune
        # protection explicite). Toute nouvelle version doit démarrer en
        # brouillon, sauf via le contexte interne du workflow.
        if not self.env.context.get(_ALLOW_STATE_WRITE_KEY):
            for vals in vals_list:
                if vals.get("state", "draft") != "draft":
                    raise ValidationError(
                        _("Une nouvelle version doit toujours démarrer en brouillon.")
                    )
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals and not self.env.context.get(_ALLOW_STATE_WRITE_KEY):
            raise ValidationError(
                _("L'état d'une version ne peut être changé que via les boutons du workflow.")
            )
        for version in self:
            if version.state != "draft":
                locked = _LOCKED_FIELDS & set(vals)
                if locked:
                    raise ValidationError(
                        _(
                            "Cette version n'est plus en brouillon : les champs "
                            "%(fields)s ne peuvent plus être modifiés. Créez une "
                            "nouvelle version pour la faire évoluer.",
                            fields=", ".join(sorted(locked)),
                        )
                    )
        return super().write(vals)

    def _write_state(self, vals):
        return self.with_context(**{_ALLOW_STATE_WRITE_KEY: True}).write(vals)

    def _check_transition(self, expected_from):
        self.ensure_one()
        if self.state != expected_from:
            raise UserError(
                _(
                    "Transition impossible : cette version est « %(current)s », "
                    "pas « %(expected)s ».",
                    current=_STATE_LABELS.get(self.state, self.state),
                    expected=_STATE_LABELS.get(expected_from, expected_from),
                )
            )

    def _check_user_can(self, group_xmlid, action_label):
        if not self.env.user.has_group(group_xmlid):
            raise UserError(
                _(
                    "Vous n'avez pas les droits nécessaires pour %(action)s.",
                    action=action_label,
                )
            )

    # ------------------------------------------------------------------
    # Préconditions (§11-12) — réutilisées par action_approve ET
    # action_make_effective. Par construction, le contenu (BPMN XML,
    # mappings) ne peut plus changer une fois la version sortie de "draft"
    # (verrouillage ci-dessus) : la ré-vérification à l'étape "effective"
    # est donc une défense en profondeur, jamais un cas où elle changerait
    # réellement le résultat entre les deux étapes.
    # ------------------------------------------------------------------

    def _get_mapping_issues(self):
        self.ensure_one()
        issues = []
        for mapping in self.mapping_ids:
            if mapping.is_orphaned:
                issues.append(
                    _(
                        "« %(element)s » (%(id)s) : mapping orphelin — cet élément n'existe "
                        "plus dans le BPMN XML courant.",
                        element=mapping.element_name or mapping.bpmn_element_id,
                        id=mapping.bpmn_element_id,
                    )
                )
            non_mappable_configured = (
                mapping.element_type
                and mapping.element_type not in _MAPPABLE_ELEMENT_TYPES
                and (mapping.task_type or mapping.odoo_model_id or mapping.odoo_method)
            )
            if non_mappable_configured:
                issues.append(
                    _(
                        "« %(element)s » : ce type d'élément (%(type)s) ne devrait pas porter "
                        "de configuration métier Odoo.",
                        element=mapping.element_name or mapping.bpmn_element_id,
                        type=mapping.element_type,
                    )
                )
        return issues

    def _check_approval_preconditions(self):
        self.ensure_one()
        if not self.bpmn_xml:
            raise ValidationError(
                _("Impossible de valider : aucun diagramme BPMN n'a été défini pour cette version.")
            )
        try:
            root = ET.fromstring(self.bpmn_xml)
        except ET.ParseError:
            raise ValidationError(
                _("Impossible de valider : le BPMN XML de cette version n'est pas un XML valide.")
            )
        if not any(el.tag.rsplit("}", 1)[-1] == "process" for el in root.iter()):
            raise ValidationError(
                _("Impossible de valider : aucun processus BPMN identifiable dans ce diagramme.")
            )
        issues = self._get_mapping_issues()
        if issues:
            raise ValidationError(
                _("Impossible de valider : \n%s") % "\n".join(issues)
            )

    def action_check_mappings(self):
        """§40 — contrôle de cohérence explicite. Ne modifie ni ne
        supprime rien ; se contente de signaler les problèmes détectés."""
        self.ensure_one()
        issues = self._get_mapping_issues()
        if issues:
            raise UserError("\n".join(issues))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": _("Aucun problème de mapping détecté."),
                "type": "success",
            },
        }

    # ------------------------------------------------------------------
    # Transitions explicites — jamais de changement arbitraire de "state".
    # ------------------------------------------------------------------

    def action_submit_review(self):
        for version in self:
            version._check_transition("draft")
            version._check_user_can("smq_quality.group_smq_writer", _("soumettre une version en révision"))
            version._write_state({"state": "review"})
            version.message_post(body=_("Soumise en révision par %s.") % self.env.user.name)

    def action_approve(self):
        for version in self:
            version._check_transition("review")
            version._check_user_can(
                "smq_quality.group_smq_quality_manager", _("approuver une version")
            )
            version._check_approval_preconditions()
            version._write_state(
                {
                    "state": "approved",
                    "approved_by": self.env.uid,
                    "approved_date": fields.Datetime.now(),
                }
            )
            version.message_post(body=_("Approuvée par %s.") % self.env.user.name)

    def action_reject(self):
        """Ouvre l'assistant de motif de rejet (obligatoire) — même pattern
        que smq_document/wizard/smq_document_version_reject_wizard.py."""
        self.ensure_one()
        self._check_transition("review")
        self._check_user_can("smq_quality.group_smq_quality_manager", _("rejeter une version"))
        return {
            "type": "ir.actions.act_window",
            "name": _("Motif du rejet"),
            "res_model": "smq.process.version.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_version_id": self.id},
        }

    def action_reject_confirm(self, reason):
        self.ensure_one()
        self._check_transition("review")
        self._check_user_can("smq_quality.group_smq_quality_manager", _("rejeter une version"))
        self._write_state(
            {
                "state": "rejected",
                "rejected_by": self.env.uid,
                "rejected_date": fields.Datetime.now(),
                "rejection_reason": reason,
            }
        )
        self.message_post(
            body=_("Rejetée par %(user)s. Motif : %(reason)s")
            % {"user": self.env.user.name, "reason": reason}
        )

    def action_reset_to_draft(self):
        # §5 : c'est l'Editor qui "corrige une version rejetée" — c'est donc
        # lui, pas le Manager, qui remet la version en brouillon pour la
        # corriger (changement délibéré par rapport au LOT 8, où ce même nom
        # de méthode servait à un Manager pour annuler une soumission).
        for version in self:
            version._check_transition("rejected")
            version._check_user_can(
                "smq_quality.group_smq_writer", _("remettre une version en brouillon")
            )
            version._write_state({"state": "draft"})
            version.message_post(body=_("Remise en brouillon par %s.") % self.env.user.name)

    def action_make_effective(self):
        for version in self:
            version._check_transition("approved")
            version._check_user_can(
                "smq_quality.group_smq_quality_manager", _("mettre une version en vigueur")
            )
            version._check_approval_preconditions()
            # §10/§12 : une seule version effective par processus — l'ancienne
            # devient automatiquement obsolète.
            siblings_effective = version.process_id.version_ids.filtered(
                lambda v: v.state == "effective" and v.id != version.id
            )
            siblings_effective._write_state(
                {"state": "obsolete", "obsolete_date": fields.Datetime.now()}
            )
            version._write_state(
                {
                    "state": "effective",
                    "effective_by": self.env.uid,
                    "effective_date": fields.Datetime.now(),
                }
            )
            version.process_id.current_version_id = version.id
            version.message_post(body=_("Mise en vigueur par %s.") % self.env.user.name)
            for old in siblings_effective:
                old.message_post(
                    body=_("Rendue obsolète — remplacée par %s.") % version.display_name
                )

    def action_obsolete(self):
        for version in self:
            version._check_transition("effective")
            version._check_user_can(
                "smq_quality.group_smq_quality_manager", _("rendre une version obsolète")
            )
            version._write_state(
                {"state": "obsolete", "obsolete_date": fields.Datetime.now()}
            )
            if version.process_id.current_version_id == version:
                version.process_id.current_version_id = False
            version.message_post(body=_("Rendue obsolète par %s.") % self.env.user.name)

    # ------------------------------------------------------------------
    # LOT 11 §8-9 — nouvelle version indépendante à partir d'une existante.
    # Clone le BPMN XML et les mappings (jamais les mêmes records), calcule
    # automatiquement le numéro major.minor suivant.
    # ------------------------------------------------------------------

    def _compute_next_version_label(self):
        self.ensure_one()
        candidates = []
        for sibling in self.process_id.version_ids:
            match = _VERSION_RE.match(sibling.version or "")
            if match:
                candidates.append((int(match.group(1)), int(match.group(2))))
        if not candidates:
            return "1.0"
        major, minor = max(candidates)
        return f"{major}.{minor + 1}"

    def action_create_new_version(self):
        self.ensure_one()
        self._check_user_can("smq_quality.group_smq_writer", _("créer une nouvelle version"))
        new_version = self.create(
            {
                "process_id": self.process_id.id,
                "version": self._compute_next_version_label(),
                "name": self.name,
                "bpmn_xml": self.bpmn_xml,
                "notes": self.notes,
            }
        )
        Mapping = self.env["smq.bpmn.task.mapping"]
        for mapping in self.mapping_ids:
            Mapping.create(
                {
                    "process_version_id": new_version.id,
                    "bpmn_element_id": mapping.bpmn_element_id,
                    "element_name": mapping.element_name,
                    "element_type": mapping.element_type,
                    "task_type": mapping.task_type,
                    "odoo_model_id": mapping.odoo_model_id.id,
                    "odoo_method": mapping.odoo_method,
                    "odoo_action_id": mapping.odoo_action_id.id,
                    "active": mapping.active,
                    "notes": mapping.notes,
                }
            )
        # LOT 12 : la description structurée appartient elle aussi à la
        # version (comme le BPMN XML et les mappings) — clonée en nouveaux
        # enregistrements indépendants, jamais partagés avec l'original.
        Step = self.env["smq.process.step"]
        new_step_id_by_old_id = {}
        for step in self.step_ids:
            new_step = Step.create(
                {
                    "process_version_id": new_version.id,
                    "sequence": step.sequence,
                    "code": step.code,
                    "name": step.name,
                    "step_type": step.step_type,
                    "responsible_user_id": step.responsible_user_id.id,
                    "description": step.description,
                }
            )
            new_step_id_by_old_id[step.id] = new_step.id
        Transition = self.env["smq.process.step.transition"]
        for transition in self.transition_ids:
            Transition.create(
                {
                    "process_version_id": new_version.id,
                    "source_step_id": new_step_id_by_old_id[transition.source_step_id.id],
                    "target_step_id": new_step_id_by_old_id[transition.target_step_id.id],
                    "condition": transition.condition,
                    "sequence": transition.sequence,
                }
            )
        self.message_post(body=_("Nouvelle version créée : %s.") % new_version.display_name)
        new_version.message_post(body=_("Créée à partir de %s.") % self.display_name)
        return {
            "type": "ir.actions.act_window",
            "res_model": "smq.process.version",
            "res_id": new_version.id,
            "view_mode": "form",
            "target": "current",
        }

    # ------------------------------------------------------------------
    # LOT 13 — démarrage d'une instance d'exécution. Réservé aux versions
    # "en vigueur" (§ portée V1 : on ne fait jamais tourner un diagramme non
    # encore approuvé/en vigueur, cohérent avec la gouvernance déjà en place
    # sur le reste du module).
    # ------------------------------------------------------------------

    def action_start_instance(self, res_model_id=False, res_id=False):
        self.ensure_one()
        if not self.env.user.has_group("smq_quality.group_smq_writer"):
            raise UserError(_("Vous n'avez pas les droits nécessaires pour démarrer une instance."))
        if self.state != "effective":
            raise UserError(
                _("Seule une version « En vigueur » peut être exécutée (état actuel : %s).")
                % _STATE_LABELS.get(self.state, self.state)
            )
        graph = parse_graph(self.bpmn_xml)
        start_id = graph.unique_start_id()
        instance = self.env["smq.process.instance"].create(
            {
                "process_version_id": self.id,
                "res_model_id": res_model_id,
                "res_id": res_id,
                "current_element_id": start_id,
            }
        )
        instance._arrive_at(start_id, graph)
        instance._auto_advance_loop(graph)
        return instance

    def action_start_instance_button(self):
        """Point d'entrée bouton (§ UI) : démarre sans enregistrement métier
        rattaché — l'utilisateur peut renseigner res_model_id/res_id après
        coup sur la fiche de l'instance nouvellement créée, évitant un
        assistant supplémentaire rien que pour cette saisie optionnelle."""
        self.ensure_one()
        instance = self.action_start_instance()
        return {
            "type": "ir.actions.act_window",
            "name": _("Instance de processus"),
            "res_model": "smq.process.instance",
            "view_mode": "form",
            "res_id": instance.id,
            "target": "current",
        }

    def action_view_instances(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Instances"),
            "res_model": "smq.process.instance",
            "view_mode": "tree,form",
            "domain": [("process_version_id", "=", self.id)],
            "context": {"default_process_version_id": self.id},
        }

    # ------------------------------------------------------------------
    # LOT 10 — sauvegarde combinée BPMN XML + mappings Odoo (§37-38).
    # Un seul appel RPC, une seule transaction : write() (verrouillage +
    # checksum du LOT 8) et les create()/write() de mapping (verrouillage du
    # LOT 10) sont exécutés dans le même contexte transactionnel Odoo — si
    # l'un échoue (version verrouillée, modèle/méthode invalide...),
    # l'exception remonte et la transaction complète est annulée : jamais
    # d'état où le XML est sauvegardé mais pas les mappings, ou l'inverse.
    # ------------------------------------------------------------------

    def action_save_bpmn_and_mappings(self, bpmn_xml, mapping_vals_list=None):
        self.ensure_one()
        self.write({"bpmn_xml": bpmn_xml})
        Mapping = self.env["smq.bpmn.task.mapping"]
        for vals in mapping_vals_list or []:
            vals = dict(vals)
            mapping_id = vals.pop("id", None)
            vals["process_version_id"] = self.id
            if mapping_id:
                Mapping.browse(mapping_id).write(vals)
            else:
                Mapping.create(vals)
        return True

    # ------------------------------------------------------------------
    # LOT 12 — description structurée → BPMN XML déterministe (§13, §22).
    # ------------------------------------------------------------------

    def _compute_reachable_step_ids(self, starts):
        """BFS déterministe depuis les étapes "start" via transition_ids."""
        self.ensure_one()
        visited = self.env["smq.process.step"]
        frontier = starts
        while frontier:
            visited |= frontier
            outgoing = self.transition_ids.filtered(lambda t: t.source_step_id in frontier)
            next_frontier = outgoing.mapped("target_step_id") - visited
            frontier = next_frontier
        return visited

    def _get_description_issues(self):
        """§13 — collecte les problèmes de la description structurée sans
        rien modifier. Utilisée à la fois par action_validate_process_
        description() (bouton informatif) et par action_generate_bpmn_
        from_description() (précondition bloquante)."""
        self.ensure_one()
        issues = []
        steps = self.step_ids
        if not steps:
            issues.append(_("Aucune étape définie dans la description structurée."))
            return issues

        starts = steps.filtered(lambda s: s.step_type == "start")
        ends = steps.filtered(lambda s: s.step_type == "end")
        if not starts:
            issues.append(_("Aucun point de départ (Début) défini."))
        elif len(starts) > 1:
            issues.append(
                _("Plusieurs points de départ (Début) définis (%d) ; il n'en faut qu'un.")
                % len(starts)
            )
        if not ends:
            issues.append(_("Aucun point de terminaison (Fin) défini."))

        if len(starts) == 1:
            reachable = self._compute_reachable_step_ids(starts)
            isolated = steps - reachable
            for step in isolated:
                issues.append(
                    _("« %s » n'est accessible depuis aucun point de départ.") % step.name
                )
        return issues

    def action_validate_process_description(self):
        """Bouton informatif — ne modifie ni ne supprime rien."""
        self.ensure_one()
        issues = self._get_description_issues()
        if issues:
            raise UserError("\n".join(issues))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": _("Description structurée valide : %d étape(s), %d transition(s).")
                % (len(self.step_ids), len(self.transition_ids)),
                "type": "success",
            },
        }

    def action_generate_bpmn_from_description(self):
        self.ensure_one()
        self._check_user_can(
            "smq_quality.group_smq_writer", _("générer le BPMN depuis la description structurée")
        )
        # §22 : jamais ailleurs qu'en draft (y compris "rejected" : il faut
        # d'abord repasser explicitement par action_reset_to_draft).
        if self.state != "draft":
            raise UserError(
                _("Le BPMN ne peut être généré que pour une version en brouillon.")
            )
        # §23 : ne jamais écraser silencieusement des mappings existants —
        # la stratégie MVP la plus sûre est le refus pur.
        if self.mapping_ids:
            raise ValidationError(
                _(
                    "Cette version possède déjà des mappings BPMN. Régénérez uniquement une "
                    "version draft sans mappings, ou supprimez-les avant de régénérer."
                )
            )
        issues = self._get_description_issues()
        if issues:
            raise ValidationError(_("Description structurée invalide :\n%s") % "\n".join(issues))

        xml_content = generate_bpmn_xml(self)
        self.write({"bpmn_xml": xml_content})
        self.message_post(
            body=_(
                "BPMN généré depuis la description structurée (%(steps)d étape(s), "
                "%(transitions)d transition(s)).",
                steps=len(self.step_ids),
                transitions=len(self.transition_ids),
            )
        )
        # Ne jamais renvoyer une action ir.actions.client "display_notification"
        # ici : vérifié dans le code source réel du client web (view_button_
        # hook.js / action_service.js) — un bouton objet ne recharge
        # l'enregistrement (onClose -> model.load()) QUE si la méthode Python
        # ne renvoie aucune action "réelle" (False/True/None). En renvoyer une
        # (même un simple toast) empêche ce rechargement automatique : le
        # widget BPMN continuait alors d'afficher l'ancien bpmn_xml (vide) au
        # lieu du diagramme pourtant bien généré et enregistré en base — bug
        # constaté et corrigé après vérification directe du bundle Odoo.
        return True
