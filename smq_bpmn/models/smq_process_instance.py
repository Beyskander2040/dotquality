from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .smq_bpmn_instance_engine import parse_graph

_STATE_SELECTION = [
    ("running", "En cours"),
    ("completed", "Terminée"),
    ("cancelled", "Annulée"),
]


class SmqProcessInstance(models.Model):
    _name = "smq.process.instance"
    _description = "SMQ Process Instance"
    _inherit = ["mail.thread"]
    _order = "id desc"

    process_version_id = fields.Many2one(
        "smq.process.version", string="Version de processus", required=True,
        ondelete="restrict", index=True, tracking=True,
    )
    # Même convention que mgmtsystem.nonconformity (res_model/res_id Char +
    # Integer bruts) : res_model_id n'est qu'un confort de saisie (sudo() car
    # ir.model est réservé au groupe technique, comme pour odoo_model_id sur
    # smq.bpmn.task.mapping) — la valeur réellement utilisée à l'exécution
    # est toujours le champ technique res_model.
    res_model_id = fields.Many2one(
        "ir.model", string="Modèle de l'enregistrement métier",
        help="Le modèle Odoo réel concerné par ce cas (ex. mgmtsystem.nonconformity).",
    )
    res_model = fields.Char(compute="_compute_res_model", store=True, readonly=True)
    res_id = fields.Integer(string="ID de l'enregistrement métier")
    res_record_display_name = fields.Char(compute="_compute_res_record_display_name")

    current_element_id = fields.Char(string="Élément BPMN courant", readonly=True, tracking=True)
    current_element_name = fields.Char(compute="_compute_current_element_info")
    current_element_tag = fields.Char(compute="_compute_current_element_info")

    state = fields.Selection(_STATE_SELECTION, default="running", required=True, tracking=True)
    started_by = fields.Many2one("res.users", readonly=True, default=lambda self: self.env.uid)
    start_date = fields.Datetime(readonly=True, default=fields.Datetime.now)
    end_date = fields.Datetime(readonly=True)

    @api.depends("res_model_id")
    def _compute_res_model(self):
        for instance in self:
            instance.res_model = instance.res_model_id.sudo().model if instance.res_model_id else False

    @api.depends("res_model", "res_id")
    def _compute_res_record_display_name(self):
        for instance in self:
            instance.res_record_display_name = False
            if instance.res_model and instance.res_id and instance.res_model in instance.env:
                record = instance.env[instance.res_model].browse(instance.res_id)
                if record.exists():
                    instance.res_record_display_name = record.display_name

    @api.depends("current_element_id", "process_version_id.bpmn_xml")
    def _compute_current_element_info(self):
        for instance in self:
            instance.current_element_name = False
            instance.current_element_tag = False
            if not (instance.current_element_id and instance.process_version_id.bpmn_xml):
                continue
            try:
                graph = parse_graph(instance.process_version_id.bpmn_xml)
            except UserError:
                continue
            instance.current_element_name = graph.name(instance.current_element_id)
            instance.current_element_tag = graph.tag(instance.current_element_id)

    # ------------------------------------------------------------------
    # Sécurité — mêmes 3 groupes réutilisés que partout ailleurs dans le
    # module (aucun nouveau groupe créé pour LOT 13).
    # ------------------------------------------------------------------

    def _check_can_operate(self, action_label):
        if not self.env.user.has_group("smq_quality.group_smq_writer"):
            raise UserError(_("Vous n'avez pas les droits nécessaires pour : %s") % action_label)

    def _check_can_cancel(self):
        if not self.env.user.has_group("smq_quality.group_smq_quality_manager"):
            raise UserError(_("Seul un Responsable Qualité peut annuler une instance."))

    # ------------------------------------------------------------------
    # Graphe et exécution.
    # ------------------------------------------------------------------

    def _get_graph(self):
        self.ensure_one()
        return parse_graph(self.process_version_id.bpmn_xml)

    def _get_mapping_for_element(self, element_id):
        self.ensure_one()
        return self.env["smq.bpmn.task.mapping"].search(
            [
                ("process_version_id", "=", self.process_version_id.id),
                ("bpmn_element_id", "=", element_id),
                ("active", "=", True),
            ],
            limit=1,
        )

    def _arrive_at(self, element_id, graph):
        """Positionne le token sur element_id : exécute le mapping s'il
        existe et concerne le même modèle que res_model (§ portée V1 : une
        discordance de modèle n'exécute rien, silencieusement — le mapping
        reste valide pour de la documentation même s'il ne s'applique pas à
        cette instance précise), puis marque la fin si endEvent."""
        self.ensure_one()
        self.write({"current_element_id": element_id})
        tag = graph.tag(element_id)
        mapping = self._get_mapping_for_element(element_id)
        if (
            mapping
            and mapping.odoo_model_id
            and mapping.odoo_method
            and self.res_model
            and mapping.odoo_model_id.sudo().model == self.res_model
            and self.res_id
        ):
            target = self.env[self.res_model].browse(self.res_id)
            if target.exists():
                getattr(target, mapping.odoo_method)()
                self.message_post(
                    body=_(
                        "Action exécutée à l'arrivée sur « %(name)s » : %(method)s.",
                        name=graph.name(element_id) or element_id,
                        method=mapping.odoo_method,
                    )
                )
        if tag == "endEvent":
            self.write({"state": "completed", "end_date": fields.Datetime.now()})
            self.message_post(body=_("Instance terminée."))

    def _auto_advance_loop(self, graph):
        self.ensure_one()
        while self.state == "running" and graph.is_auto_advance(self.current_element_id):
            outgoing = graph.outgoing(self.current_element_id)
            if not outgoing:
                raise UserError(
                    _("Aucun flux sortant depuis « %s » — le diagramme est mal formé.")
                    % (graph.name(self.current_element_id) or self.current_element_id)
                )
            if len(outgoing) > 1:
                # Défensif : un événement de début ou une tâche de service
                # avec plusieurs flux sortants n'est pas un cas d'usage
                # prévu (ambiguïté réservée aux passerelles) — on s'arrête
                # plutôt que de choisir arbitrairement.
                break
            _flow_id, target_id, _label = outgoing[0]
            self._arrive_at(target_id, graph)

    def get_pending_branches(self):
        """Utilisé par l'assistant "Avancer" : liste des flux sortants
        depuis l'élément courant, avec un libellé lisible."""
        self.ensure_one()
        graph = self._get_graph()
        branches = []
        for flow_id, target_id, condition_label in graph.outgoing(self.current_element_id):
            label = condition_label or graph.name(target_id) or target_id
            branches.append((flow_id, label))
        return branches

    def action_advance(self, chosen_flow_id=None):
        self.ensure_one()
        self._check_can_operate(_("faire avancer une instance de processus"))
        if self.state != "running":
            raise UserError(_("Cette instance n'est plus en cours d'exécution."))
        graph = self._get_graph()
        current_tag = graph.tag(self.current_element_id)
        if current_tag is None:
            raise UserError(
                _("L'élément courant « %s » n'existe plus dans le diagramme de cette version.")
                % self.current_element_id
            )
        if current_tag == "endEvent":
            raise UserError(_("Cette instance est déjà arrivée à la fin du processus."))
        outgoing = graph.outgoing(self.current_element_id)
        if not outgoing:
            raise UserError(
                _("Aucun flux sortant depuis l'élément courant — le diagramme est mal formé.")
            )
        if len(outgoing) == 1:
            target_id = outgoing[0][1]
        else:
            if not chosen_flow_id:
                raise UserError(
                    _("Plusieurs branches sont possibles depuis cette étape — précisez laquelle suivre.")
                )
            matches = [o for o in outgoing if o[0] == chosen_flow_id]
            if not matches:
                raise UserError(_("Branche « %s » inconnue depuis l'élément courant.") % chosen_flow_id)
            target_id = matches[0][1]
        self._arrive_at(target_id, graph)
        self._auto_advance_loop(graph)

    def action_cancel(self):
        for instance in self:
            instance._check_can_cancel()
            if instance.state != "running":
                raise UserError(_("Seule une instance en cours peut être annulée."))
            instance.write({"state": "cancelled", "end_date": fields.Datetime.now()})
            instance.message_post(body=_("Instance annulée par %s.") % self.env.user.name)
