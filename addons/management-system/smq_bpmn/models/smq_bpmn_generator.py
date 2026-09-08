"""LOT 12 — Générateur BPMN déterministe.

Responsabilité unique : transformer une description structurée
(smq.process.step / smq.process.step.transition) en BPMN XML valide,
affichable dans bpmn-js. Volontairement séparé de smq.process.version
(§14 du brief) : ce module ne connaît que des recordsets Odoo en entrée et
produit une chaîne XML en sortie — aucune écriture, aucun effet de bord.

Déterminisme (§17/§28) : les IDs BPMN sont dérivés de l'id technique
(immuable) de chaque enregistrement, jamais du nom ni de la position
d'affichage — une même description produit donc toujours le même XML,
y compris après un réordonnancement (changement de `sequence`).
"""

import xml.etree.ElementTree as ET

_BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
_BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
_DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
_DI_NS = "http://www.omg.org/spec/DD/20100524/DI"

ET.register_namespace("bpmn", _BPMN_NS)
ET.register_namespace("bpmndi", _BPMNDI_NS)
ET.register_namespace("dc", _DC_NS)
ET.register_namespace("di", _DI_NS)


def _bpmn(tag):
    return f"{{{_BPMN_NS}}}{tag}"


def _bpmndi(tag):
    return f"{{{_BPMNDI_NS}}}{tag}"


def _dc(tag):
    return f"{{{_DC_NS}}}{tag}"


def _di(tag):
    return f"{{{_DI_NS}}}{tag}"


# §16 — mapping déterministe step_type -> type BPMN réel. step_type reste
# une notion métier ; le type BPMN est toujours dérivé, jamais saisi.
_STEP_TYPE_TO_BPMN_TAG = {
    "manual": "userTask",
    "document": "userTask",
    "approval": "userTask",
    "notification": "serviceTask",
    "gateway": "exclusiveGateway",
    "start": "startEvent",
    "end": "endEvent",
}

# Dimensions de layout (§20-21) — simples et déterministes, pas de moteur
# de layout sophistiqué.
_EVENT_SIZE = (36, 36)
_GATEWAY_SIZE = (50, 50)
_TASK_SIZE = (100, 80)
_COLUMN_WIDTH = 180
_ROW_HEIGHT = 120
_MARGIN_X = 60
_MARGIN_Y = 60


def _element_id(step):
    prefix = {"gateway": "Gateway", "start": "Start", "end": "End"}.get(step.step_type, "Step")
    return f"{prefix}_{step.id}"


def _flow_id(transition):
    return f"Flow_{transition.id}"


def _element_size(step):
    if step.step_type in ("start", "end"):
        return _EVENT_SIZE
    if step.step_type == "gateway":
        return _GATEWAY_SIZE
    return _TASK_SIZE


def _compute_layout(steps, transitions):
    """BFS déterministe depuis les étapes "start" : niveau = colonne
    (profondeur depuis un départ), position dans le niveau = ligne. Les
    arcs arrière (boucles, §11) ne créent jamais de nouveau niveau — un
    noeud n'est positionné qu'une seule fois, à sa première découverte."""
    by_id = {step.id: step for step in steps}
    outgoing = {}
    for transition in transitions.sorted("sequence"):
        outgoing.setdefault(transition.source_step_id.id, []).append(transition.target_step_id.id)

    starts = [s.id for s in steps if s.step_type == "start"]
    level_of = {}
    frontier = list(starts)
    level = 0
    while frontier:
        next_frontier = []
        for step_id in frontier:
            if step_id in level_of:
                continue
            level_of[step_id] = level
            for target_id in outgoing.get(step_id, []):
                if target_id not in level_of:
                    next_frontier.append(target_id)
        frontier = next_frontier
        level += 1

    # Étapes jamais atteintes (ne devrait pas arriver après validation,
    # mais le générateur reste défensif et ne plante jamais) : placées à la
    # suite, chacune dans sa propre colonne.
    max_level = max(level_of.values(), default=-1)
    for step in steps:
        if step.id not in level_of:
            max_level += 1
            level_of[step.id] = max_level

    row_counters = {}
    positions = {}
    for step in steps:  # ordre déjà déterministe (process_version_id, sequence, id)
        lvl = level_of[step.id]
        row = row_counters.get(lvl, 0)
        row_counters[lvl] = row + 1
        width, height = _element_size(step)
        x = _MARGIN_X + lvl * _COLUMN_WIDTH
        y = _MARGIN_Y + row * _ROW_HEIGHT
        positions[step.id] = (x, y, width, height)
    return positions


def generate_bpmn_xml(process_version):
    """@param process_version: recordset smq.process.version (un seul
    enregistrement). @return: chaîne XML BPMN complète (str)."""
    process_version.ensure_one()
    steps = process_version.step_ids.sorted(lambda s: (s.sequence, s.id))
    transitions = process_version.transition_ids.sorted(lambda t: (t.sequence, t.id))

    definitions = ET.Element(
        _bpmn("definitions"),
        {"id": "Definitions_1", "targetNamespace": "http://bpmn.io/schema/bpmn"},
    )
    process_el = ET.SubElement(definitions, _bpmn("process"), {"id": "Process_1", "isExecutable": "false"})

    incoming_by_step = {}
    outgoing_by_step = {}
    for transition in transitions:
        outgoing_by_step.setdefault(transition.source_step_id.id, []).append(_flow_id(transition))
        incoming_by_step.setdefault(transition.target_step_id.id, []).append(_flow_id(transition))

    step_elements = {}
    for step in steps:
        tag = _STEP_TYPE_TO_BPMN_TAG[step.step_type]
        element_id = _element_id(step)
        attrs = {"id": element_id}
        if step.name:
            attrs["name"] = step.name
        el = ET.SubElement(process_el, _bpmn(tag), attrs)
        step_elements[step.id] = el
        # §18 : documentation uniquement si un texte est réellement présent
        # — jamais de <bpmn:documentation/> vide.
        if step.description:
            doc_el = ET.SubElement(el, _bpmn("documentation"))
            doc_el.text = step.description
        for flow_id in incoming_by_step.get(step.id, []):
            ET.SubElement(el, _bpmn("incoming")).text = flow_id
        for flow_id in outgoing_by_step.get(step.id, []):
            ET.SubElement(el, _bpmn("outgoing")).text = flow_id

    for transition in transitions:
        attrs = {
            "id": _flow_id(transition),
            "sourceRef": _element_id(transition.source_step_id),
            "targetRef": _element_id(transition.target_step_id),
        }
        # §19 : la condition est un texte déclaratif porté par l'étiquette
        # visuelle du flux (name) — jamais une expression exécutable.
        if transition.condition:
            attrs["name"] = transition.condition
        ET.SubElement(process_el, _bpmn("sequenceFlow"), attrs)

    # Diagram Interchange (§20) — layout simple et déterministe (§21).
    positions = _compute_layout(steps, transitions)
    diagram = ET.SubElement(definitions, _bpmndi("BPMNDiagram"), {"id": "BPMNDiagram_1"})
    plane = ET.SubElement(diagram, _bpmndi("BPMNPlane"), {"id": "BPMNPlane_1", "bpmnElement": "Process_1"})

    for step in steps:
        x, y, width, height = positions[step.id]
        shape = ET.SubElement(
            plane, _bpmndi("BPMNShape"),
            {"id": f"{_element_id(step)}_di", "bpmnElement": _element_id(step)},
        )
        ET.SubElement(
            shape, _dc("Bounds"),
            {"x": str(x), "y": str(y), "width": str(width), "height": str(height)},
        )

    for transition in transitions:
        sx, sy, sw, sh = positions[transition.source_step_id.id]
        tx, ty, tw, th = positions[transition.target_step_id.id]
        edge = ET.SubElement(
            plane, _bpmndi("BPMNEdge"),
            {"id": f"{_flow_id(transition)}_di", "bpmnElement": _flow_id(transition)},
        )
        ET.SubElement(edge, _di("waypoint"), {"x": str(sx + sw), "y": str(sy + sh // 2)})
        ET.SubElement(edge, _di("waypoint"), {"x": str(tx), "y": str(ty + th // 2)})

    xml_body = ET.tostring(definitions, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_body}'
