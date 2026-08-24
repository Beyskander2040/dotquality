"""LOT 13 — Interprétation du graphe BPMN pour l'exécution.

Responsabilité unique : lire le bpmn_xml d'une version (qu'il ait été dessiné
à la main dans l'éditeur bpmn-js ou généré depuis la description structurée,
LOT 12 — les deux produisent le même XML standard, ce module ne fait aucune
différence entre les deux) et exposer le graphe (éléments + flux sortants)
nécessaire à smq.process.instance pour avancer un pointeur. Aucune écriture,
aucun accès ORM ici — fonctions pures sur une chaîne XML en entrée, comme
smq_bpmn_generator.py dans l'autre sens.

Portée V1 (délibérément restreinte, comme chaque LOT précédent) : les seuls
tags BPMN reconnus sont ceux que l'éditeur/générateur de ce module savent
produire — startEvent, endEvent, userTask, serviceTask, exclusiveGateway,
sequenceFlow. Pas de passerelles parallèles/inclusives, pas de
sous-processus, pas de minuteurs : un élément d'un type non reconnu fait
échouer le démarrage avec un message explicite plutôt que de se comporter
de façon imprévisible.
"""

import xml.etree.ElementTree as ET

from odoo.exceptions import UserError
from odoo.tools.translate import _

_BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

# Tags du modèle sémantique BPMN (namespace _BPMN_NS uniquement — le
# namespace bpmndi/dc/di du diagramme visuel n'est jamais inspecté ici).
_RECOGNIZED_TAGS = {"startEvent", "endEvent", "userTask", "serviceTask", "exclusiveGateway"}
_IGNORED_STRUCTURAL_TAGS = {
    "definitions", "process", "extensionElements", "documentation", "incoming", "outgoing",
    "sequenceFlow",
}

# Tags dont le token traverse automatiquement, sans intervention humaine.
_AUTO_ADVANCE_TAGS = {"startEvent", "serviceTask"}


class BpmnGraph:
    """Graphe en mémoire d'une version BPMN — élément courant, ses voisins
    sortants, rien d'autre. Ne connaît rien de smq.process.instance."""

    def __init__(self, element_tag_by_id, element_name_by_id, outgoing_by_source):
        self.element_tag_by_id = element_tag_by_id
        self.element_name_by_id = element_name_by_id
        self.outgoing_by_source = outgoing_by_source

    def tag(self, element_id):
        return self.element_tag_by_id.get(element_id)

    def name(self, element_id):
        return self.element_name_by_id.get(element_id) or ""

    def is_auto_advance(self, element_id):
        return self.tag(element_id) in _AUTO_ADVANCE_TAGS

    def outgoing(self, element_id):
        """Liste de (flow_id, target_id, condition_label) — condition_label
        est un texte déclaratif (§19 LOT 12), jamais une expression évaluée."""
        return self.outgoing_by_source.get(element_id, [])

    def unique_start_id(self):
        starts = [eid for eid, tag in self.element_tag_by_id.items() if tag == "startEvent"]
        if len(starts) != 1:
            raise UserError(
                _(
                    "Le diagramme BPMN doit contenir exactement un événement de "
                    "début pour pouvoir démarrer une instance (trouvé : %(count)d).",
                    count=len(starts),
                )
            )
        return starts[0]


def parse_graph(bpmn_xml):
    """@param bpmn_xml: chaîne XML BPMN. @return: BpmnGraph."""
    if not bpmn_xml:
        raise UserError(_("Cette version n'a pas de diagramme BPMN à exécuter."))
    try:
        root = ET.fromstring(bpmn_xml)
    except ET.ParseError as exc:
        raise UserError(_("Le diagramme BPMN de cette version est invalide : %s", exc)) from exc

    bpmn_prefix = f"{{{_BPMN_NS}}}"
    element_tag_by_id = {}
    element_name_by_id = {}
    flows = []  # (flow_id, source_id, target_id, condition_label)
    unknown_tags = set()

    for el in root.iter():
        if not el.tag.startswith(bpmn_prefix):
            continue  # hors du namespace sémantique BPMN (bpmndi/dc/di ignorés)
        tag = el.tag[len(bpmn_prefix):]
        el_id = el.get("id")
        if tag == "sequenceFlow" and el_id:
            flows.append((el_id, el.get("sourceRef"), el.get("targetRef"), el.get("name") or False))
        elif tag in _RECOGNIZED_TAGS and el_id:
            element_tag_by_id[el_id] = tag
            element_name_by_id[el_id] = el.get("name") or False
        elif tag not in _IGNORED_STRUCTURAL_TAGS:
            # Défensif (§ portée V1) : un élément métier BPMN non reconnu
            # (ex. parallelGateway, subProcess, boundaryEvent, timerEvent...)
            # doit bloquer explicitement le démarrage plutôt que d'être
            # silencieusement ignoré et produire un comportement imprévisible.
            unknown_tags.add(tag)

    if unknown_tags:
        raise UserError(
            _(
                "Ce diagramme utilise des éléments BPMN non pris en charge par "
                "le moteur d'exécution V1 : %(tags)s.",
                tags=", ".join(sorted(unknown_tags)),
            )
        )

    outgoing_by_source = {}
    for flow_id, source_id, target_id, condition_label in flows:
        if source_id:
            outgoing_by_source.setdefault(source_id, []).append((flow_id, target_id, condition_label))
    # Ordre déterministe des branches (par flow_id) — important pour
    # action_advance() quand une seule branche existe (auto-suivie sans
    # ambiguïté possible).
    for source_id in outgoing_by_source:
        outgoing_by_source[source_id].sort(key=lambda t: t[0])

    return BpmnGraph(element_tag_by_id, element_name_by_id, outgoing_by_source)
