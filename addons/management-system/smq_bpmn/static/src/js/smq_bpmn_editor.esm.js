/** @odoo-module **/

import {Component, onMounted, onWillUnmount, onWillUpdateProps, useRef, xml} from "@odoo/owl";

// bpmn-js (window.BpmnJS) est chargé exclusivement via les assets Odoo
// (smq_bpmn/static/src/lib/bpmn-js/bpmn-modeler.development.js, déclaré avant
// ce fichier dans __manifest__.py) — aucun chargement dynamique, aucun CDN.

// LOT 9 : diagramme minimal proposé quand smq.process.version.bpmn_xml est
// vide, pour que l'utilisateur ne se retrouve jamais devant un canvas vide
// (Début → Tâche → Fin), conformément au brief. Jamais parsé ni interprété
// métier ici : bpmn-js le traite comme n'importe quel autre XML BPMN.
const DEFAULT_BPMN_XML = `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                   xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                   xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                   xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                   id="Definitions_1"
                   targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="StartEvent_1" name="Début">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:task id="Task_1" name="Tâche">
      <bpmn:incoming>Flow_1</bpmn:incoming>
      <bpmn:outgoing>Flow_2</bpmn:outgoing>
    </bpmn:task>
    <bpmn:endEvent id="EndEvent_1" name="Fin">
      <bpmn:incoming>Flow_2</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Task_1" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="EndEvent_1" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
        <dc:Bounds x="152" y="102" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Task_1_di" bpmnElement="Task_1">
        <dc:Bounds x="260" y="80" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="EndEvent_1_di" bpmnElement="EndEvent_1">
        <dc:Bounds x="432" y="102" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNEdge id="Flow_1_di" bpmnElement="Flow_1">
        <di:waypoint x="188" y="120" />
        <di:waypoint x="260" y="120" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_2_di" bpmnElement="Flow_2">
        <di:waypoint x="360" y="120" />
        <di:waypoint x="432" y="120" />
      </bpmndi:BPMNEdge>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>`;

// LOT 10 — correspondance entre le type BPMN réel exposé par bpmn-js
// (element.type, ex. "bpmn:UserTask") et les valeurs de la sélection Odoo
// smq.bpmn.task.mapping.element_type. Toute clé absente de cette table
// (gateways autres, événements, flows, pools/lanes...) n'a délibérément pas
// d'équivalent : ces éléments ne portent pas de mapping métier (§21).
const BPMN_TYPE_TO_ELEMENT_TYPE = {
    "bpmn:Task": "task",
    "bpmn:UserTask": "user_task",
    "bpmn:ServiceTask": "service_task",
    "bpmn:ManualTask": "manual_task",
    "bpmn:ScriptTask": "script_task",
    "bpmn:ExclusiveGateway": "exclusive_gateway",
    "bpmn:ParallelGateway": "parallel_gateway",
    "bpmn:InclusiveGateway": "inclusive_gateway",
    "bpmn:StartEvent": "start_event",
    "bpmn:EndEvent": "end_event",
};

export class SmqBpmnEditor extends Component {
    static template = xml`
        <div class="o_smq_bpmn_editor_canvas_wrapper">
            <div t-ref="canvas" class="o_smq_bpmn_editor_canvas"/>
        </div>
    `;

    static props = {
        bpmnXml: {type: String, optional: true},
        readonly: {type: Boolean, optional: true, default: false},
        onChange: {type: Function, optional: true},
        onReady: {type: Function, optional: true},
        onImportError: {type: Function, optional: true},
        onSelectionChanged: {type: Function, optional: true},
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.bpmnModeler = null;
        this._keyboardHandler = null;
        this._wheelHandler = null;

        onMounted(() => this._initModeler());

        onWillUpdateProps((nextProps) => {
            if (nextProps.bpmnXml !== this.props.bpmnXml) {
                this._importXML(nextProps.bpmnXml);
            }
        });

        onWillUnmount(() => {
            if (this.canvasRef.el && this._keyboardHandler) {
                this.canvasRef.el.removeEventListener("keydown", this._keyboardHandler);
            }
            if (this.canvasRef.el && this._wheelHandler) {
                this.canvasRef.el.removeEventListener("wheel", this._wheelHandler);
            }
            if (this.bpmnModeler) {
                this.bpmnModeler.destroy();
                this.bpmnModeler = null;
            }
        });
    }

    /** @private */
    _initModeler() {
        if (typeof window.BpmnJS === "undefined") {
            console.error(
                "bpmn-js introuvable : vérifier que bpmn-modeler.development.js est bien " +
                    "déclaré dans web.assets_backend avant les fichiers du module smq_bpmn."
            );
            return;
        }

        // Une seule instance bpmn-js pour toute la durée de vie du composant
        // (jamais recréée à chaque frappe) — détruite proprement à l'unmount.
        this.bpmnModeler = new window.BpmnJS({container: this.canvasRef.el});

        this.bpmnModeler.on("commandStack.changed", () => this._notifyChange());

        // LOT 10 : la sélection déclenche uniquement une lecture locale des
        // propriétés BPMN déjà présentes dans le canvas (aucune requête RPC
        // ici) — c'est au composant parent (properties panel) de décider
        // s'il doit résoudre un mapping Odoo pour cet élément.
        this.bpmnModeler.on("selection.changed", (event) => {
            this._handleSelectionChanged(event.newSelection || []);
        });

        if (!this.props.readonly) {
            this._setupKeyboardShortcuts();
        }
        this._setupMouseWheelZoom();

        if (this.props.onReady) {
            this.props.onReady({
                exportDiagram: () => this.exportDiagram(),
                importDiagram: (xmlContent) => this.importDiagram(xmlContent),
                zoomIn: () => this.zoomIn(),
                zoomOut: () => this.zoomOut(),
                zoomFit: () => this.zoomFit(),
                updateElementName: (elementId, name) => this.updateElementName(elementId, name),
                updateElementDocumentation: (elementId, text) =>
                    this.updateElementDocumentation(elementId, text),
            });
        }

        this._importXML(this.props.bpmnXml);
    }

    /**
     * @param {String} xmlString
     * @private
     */
    async _importXML(xmlString) {
        if (!this.bpmnModeler) {
            return;
        }
        try {
            await this.bpmnModeler.importXML(xmlString || DEFAULT_BPMN_XML);
            this.bpmnModeler.get("canvas").zoom("fit-viewport");
        } catch (err) {
            console.error("could not import BPMN diagram", err);
            if (this.props.onImportError) {
                this.props.onImportError(err);
            }
        }
    }

    /** @private */
    async _notifyChange() {
        if (!this.bpmnModeler || this.props.readonly || !this.props.onChange) {
            return;
        }
        try {
            const {xml: xmlContent} = await this.bpmnModeler.saveXML({format: true});
            this.props.onChange(xmlContent);
        } catch (err) {
            console.error("could not read current BPMN diagram", err);
        }
    }

    /**
     * @public
     * @returns {Promise<String|null>}
     */
    async exportDiagram() {
        if (!this.bpmnModeler) {
            return null;
        }
        try {
            const {xml: xmlContent} = await this.bpmnModeler.saveXML({format: true});
            return xmlContent;
        } catch (err) {
            console.error("could not export BPMN diagram", err);
            return null;
        }
    }

    /**
     * @public
     * @param {String} xmlContent
     */
    async importDiagram(xmlContent) {
        await this._importXML(xmlContent);
        await this._notifyChange();
    }

    /** @public */
    zoomIn() {
        if (!this.bpmnModeler) return;
        const canvas = this.bpmnModeler.get("canvas");
        canvas.zoom(Math.min(canvas.zoom() * 1.2, 3));
    }

    /** @public */
    zoomOut() {
        if (!this.bpmnModeler) return;
        const canvas = this.bpmnModeler.get("canvas");
        canvas.zoom(Math.max(canvas.zoom() / 1.2, 0.2));
    }

    /** @public */
    zoomFit() {
        if (!this.bpmnModeler) return;
        this.bpmnModeler.get("canvas").zoom("fit-viewport");
    }

    /** @private */
    _setupKeyboardShortcuts() {
        this._keyboardHandler = (ev) => {
            if (!ev.ctrlKey && !ev.metaKey) return;
            const tag = ev.target.tagName;
            if (tag === "INPUT" || tag === "TEXTAREA") return;
            const commandStack = this.bpmnModeler.get("commandStack");
            if (ev.key === "z" && !ev.shiftKey) {
                ev.preventDefault();
                if (commandStack.canUndo()) commandStack.undo();
            }
            if (ev.key === "y" || (ev.key === "z" && ev.shiftKey)) {
                ev.preventDefault();
                if (commandStack.canRedo()) commandStack.redo();
            }
        };
        if (this.canvasRef.el) {
            this.canvasRef.el.addEventListener("keydown", this._keyboardHandler);
            this.canvasRef.el.setAttribute("tabindex", "0");
        }
    }

    /** @private */
    _setupMouseWheelZoom() {
        this._wheelHandler = (ev) => {
            if (!ev.ctrlKey && !ev.metaKey) return;
            ev.preventDefault();
            const canvas = this.bpmnModeler.get("canvas");
            const delta = ev.deltaY > 0 ? 0.9 : 1.1;
            const newZoom = Math.max(0.2, Math.min(3, canvas.zoom() * delta));
            const rect = this.canvasRef.el.getBoundingClientRect();
            canvas.zoom(newZoom, {x: ev.clientX - rect.left, y: ev.clientY - rect.top});
        };
        if (this.canvasRef.el) {
            this.canvasRef.el.addEventListener("wheel", this._wheelHandler, {passive: false});
        }
    }

    /**
     * §17 : ne remonte des informations que pour une sélection unique et
     * non ambiguë (jamais pour une sélection vide ou multiple). bpmn_type
     * brut et element_type (converti pour Odoo) sont tous deux transmis ;
     * la résolution d'un éventuel mapping Odoo reste à la charge du
     * composant appelant (aucune requête RPC ici).
     * @param {Array} newSelection
     * @private
     */
    _handleSelectionChanged(newSelection) {
        if (!this.props.onSelectionChanged) {
            return;
        }
        if (newSelection.length !== 1 || !newSelection[0] || !newSelection[0].id) {
            this.props.onSelectionChanged(false);
            return;
        }
        const element = newSelection[0];
        const bo = element.businessObject || {};
        const documentation =
            bo.documentation && bo.documentation.length ? bo.documentation[0].text || "" : "";
        this.props.onSelectionChanged({
            elementId: element.id,
            name: bo.name || "",
            documentation,
            bpmnType: element.type,
            elementType: BPMN_TYPE_TO_ELEMENT_TYPE[element.type] || null,
        });
    }

    /**
     * @public
     * @param {String} elementId
     * @param {String} name
     */
    updateElementName(elementId, name) {
        if (!this.bpmnModeler) return;
        const element = this.bpmnModeler.get("elementRegistry").get(elementId);
        if (!element) return;
        this.bpmnModeler.get("modeling").updateProperties(element, {name});
    }

    /**
     * @public
     * @param {String} elementId
     * @param {String} text
     */
    updateElementDocumentation(elementId, text) {
        if (!this.bpmnModeler) return;
        const element = this.bpmnModeler.get("elementRegistry").get(elementId);
        if (!element) return;
        const bpmnFactory = this.bpmnModeler.get("bpmnFactory");
        const documentation = text ? [bpmnFactory.create("bpmn:Documentation", {text})] : [];
        this.bpmnModeler.get("modeling").updateProperties(element, {documentation});
    }
}
