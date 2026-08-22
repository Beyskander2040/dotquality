/** @odoo-module **/

import {Component, xml} from "@odoo/owl";

// LOT 10 — panneau de propriétés. Aucun package officiel bpmn-js-properties-
// panel / @bpmn-io/properties-panel n'est vendu dans ce dépôt (vérifié : le
// bundle bpmn-modeler.development.js v18.9.1 ne contient que bpmn-js/
// diagram-js core, pas d'add-on properties-panel). Ce composant est donc un
// panneau OWL autonome, construit uniquement sur les services bpmn-js déjà
// vérifiés disponibles dans cette version (elementRegistry, modeling,
// bpmnFactory) — voir le rapport LOT 10 pour la justification complète.
//
// Composant purement présentationnel : aucun accès direct à bpmn-js ni à
// l'ORM ici. Toutes les données arrivent en props ; toute modification
// remonte via callback. Une seule source de sélection (SmqBpmnEditor), un
// seul panneau (celui-ci) — jamais de système concurrent.

const _ELEMENT_TYPE_LABELS = {
    task: "Tâche",
    user_task: "Tâche utilisateur",
    service_task: "Tâche de service",
    manual_task: "Tâche manuelle",
    script_task: "Tâche de script",
    exclusive_gateway: "Passerelle exclusive",
    parallel_gateway: "Passerelle parallèle",
    inclusive_gateway: "Passerelle inclusive",
    start_event: "Événement de début",
    end_event: "Événement de fin",
};

const _TASK_TYPE_OPTIONS = [
    ["document", "Document"],
    ["approval", "Approbation"],
    ["notification", "Notification"],
    ["manual", "Manuel"],
    ["other", "Autre"],
];

const _MAPPABLE_ELEMENT_TYPES = new Set([
    "task",
    "user_task",
    "service_task",
    "manual_task",
    "script_task",
]);

export class SmqBpmnPropertiesPanel extends Component {
    static template = xml`
        <div class="o_smq_bpmn_properties_panel">
            <t t-if="!props.selection">
                <p class="text-muted small p-2">
                    Sélectionnez un élément du diagramme pour voir ses propriétés.
                </p>
            </t>
            <t t-else="">
                <div class="o_smq_bpmn_properties_section">
                    <h6>Général</h6>
                    <div class="o_smq_bpmn_properties_field">
                        <label>ID</label>
                        <input type="text" t-att-value="props.selection.elementId" readonly="readonly"/>
                    </div>
                    <div class="o_smq_bpmn_properties_field">
                        <label>Type</label>
                        <input type="text" t-att-value="elementTypeLabel" readonly="readonly"/>
                    </div>
                    <div class="o_smq_bpmn_properties_field">
                        <label>Nom</label>
                        <input
                            type="text"
                            t-att-value="props.selection.name"
                            t-att-readonly="props.readonly"
                            t-on-change="onNameChange"
                        />
                    </div>
                    <div class="o_smq_bpmn_properties_field">
                        <label>Documentation</label>
                        <textarea
                            t-att-readonly="props.readonly"
                            t-on-change="onDocumentationChange"
                        ><t t-esc="props.selection.documentation"/></textarea>
                    </div>
                </div>

                <div class="o_smq_bpmn_properties_section" t-if="isMappable">
                    <h6>Mapping Odoo</h6>
                    <div t-if="props.mappingInfo === null" class="text-muted small">
                        Chargement…
                    </div>
                    <div t-elif="!hasMappingData" class="o_smq_bpmn_properties_no_mapping">
                        <p class="text-muted small">Aucun mapping Odoo configuré.</p>
                        <button
                            type="button"
                            class="btn btn-secondary btn-sm"
                            t-on-click="onConfigureMapping"
                            t-att-disabled="props.readonly"
                        >
                            Configurer le mapping
                        </button>
                    </div>
                    <t t-else="">
                        <span t-if="props.mappingInfo.is_orphaned" class="badge text-bg-danger mb-2">
                            Mapping orphelin — élément absent du BPMN courant
                        </span>
                        <div class="o_smq_bpmn_properties_field">
                            <label>Type métier</label>
                            <select t-att-disabled="props.readonly" t-on-change="onTaskTypeChange">
                                <option value="">-</option>
                                <t t-foreach="taskTypeOptions" t-as="opt" t-key="opt[0]">
                                    <option
                                        t-att-value="opt[0]"
                                        t-att-selected="opt[0] === currentTaskType"
                                    ><t t-esc="opt[1]"/></option>
                                </t>
                            </select>
                        </div>
                        <div class="o_smq_bpmn_properties_field">
                            <label>Modèle Odoo</label>
                            <select t-att-disabled="props.readonly" t-on-change="onModelChange">
                                <option value="">-</option>
                                <t t-foreach="props.availableModels" t-as="m" t-key="m.id">
                                    <option
                                        t-att-value="m.id"
                                        t-att-selected="m.id === currentModelId"
                                    ><t t-esc="m.name"/> (<t t-esc="m.model"/>)</option>
                                </t>
                            </select>
                        </div>
                        <div class="o_smq_bpmn_properties_field">
                            <label>Méthode Odoo</label>
                            <input
                                type="text"
                                t-att-value="currentMethod"
                                t-att-readonly="props.readonly"
                                placeholder="ex. action_approve"
                                t-on-change="onMethodChange"
                            />
                        </div>
                        <div class="o_smq_bpmn_properties_field">
                            <label>Action Odoo</label>
                            <select t-att-disabled="props.readonly" t-on-change="onActionChange">
                                <option value="">-</option>
                                <t t-foreach="props.availableActions" t-as="a" t-key="a.id">
                                    <option
                                        t-att-value="a.id"
                                        t-att-selected="a.id === currentActionId"
                                    ><t t-esc="a.name"/></option>
                                </t>
                            </select>
                        </div>
                        <div class="o_smq_bpmn_properties_field">
                            <label>
                                <input
                                    type="checkbox"
                                    t-att-checked="currentActive"
                                    t-att-disabled="props.readonly"
                                    t-on-change="onActiveChange"
                                /> Actif
                            </label>
                        </div>
                    </t>
                </div>
            </t>
        </div>
    `;

    static props = {
        selection: {type: [Object, {value: false}], optional: true},
        mappingInfo: {type: [Object, {value: null}], optional: true},
        readonly: {type: Boolean, optional: true, default: false},
        availableModels: {type: Array, optional: true},
        availableActions: {type: Array, optional: true},
        onElementPropertyChange: {type: Function, optional: true},
        onMappingChange: {type: Function, optional: true},
    };

    get elementTypeLabel() {
        const elementType = this.props.selection && this.props.selection.elementType;
        return (elementType && _ELEMENT_TYPE_LABELS[elementType]) || this.props.selection.bpmnType;
    }

    get isMappable() {
        const elementType = this.props.selection && this.props.selection.elementType;
        return Boolean(elementType && _MAPPABLE_ELEMENT_TYPES.has(elementType));
    }

    get hasMappingData() {
        const info = this.props.mappingInfo;
        return Boolean(info && (info.found || info._pendingNew));
    }

    get taskTypeOptions() {
        return _TASK_TYPE_OPTIONS;
    }

    get currentTaskType() {
        return (this.props.mappingInfo && this.props.mappingInfo.task_type) || "";
    }

    get currentModelId() {
        // Peut être un tuple [id, label] (lecture serveur via
        // get_mapping_for_element) ou un entier simple (après une
        // modification locale via le <select> ci-dessous) — les deux formes
        // doivent être acceptées.
        const value = this.props.mappingInfo && this.props.mappingInfo.odoo_model_id;
        if (!value) return false;
        return Array.isArray(value) ? value[0] : value;
    }

    get currentMethod() {
        return (this.props.mappingInfo && this.props.mappingInfo.odoo_method) || "";
    }

    get currentActionId() {
        const value = this.props.mappingInfo && this.props.mappingInfo.odoo_action_id;
        if (!value) return false;
        return Array.isArray(value) ? value[0] : value;
    }

    get currentActive() {
        const info = this.props.mappingInfo;
        return info ? info.active !== false : true;
    }

    onNameChange(ev) {
        if (this.props.onElementPropertyChange) {
            this.props.onElementPropertyChange(this.props.selection.elementId, {name: ev.target.value});
        }
    }

    onDocumentationChange(ev) {
        if (this.props.onElementPropertyChange) {
            this.props.onElementPropertyChange(this.props.selection.elementId, {
                documentation: ev.target.value,
            });
        }
    }

    onConfigureMapping() {
        if (this.props.onMappingChange) {
            this.props.onMappingChange(this.props.selection.elementId, {
                element_type: this.props.selection.elementType,
                element_name: this.props.selection.name,
                _pendingNew: true,
            });
        }
    }

    onTaskTypeChange(ev) {
        this._emitMappingChange({task_type: ev.target.value || false});
    }

    onModelChange(ev) {
        const value = ev.target.value ? parseInt(ev.target.value, 10) : false;
        this._emitMappingChange({odoo_model_id: value});
    }

    onMethodChange(ev) {
        this._emitMappingChange({odoo_method: ev.target.value || false});
    }

    onActionChange(ev) {
        const value = ev.target.value ? parseInt(ev.target.value, 10) : false;
        this._emitMappingChange({odoo_action_id: value});
    }

    onActiveChange(ev) {
        this._emitMappingChange({active: ev.target.checked});
    }

    /** @private */
    _emitMappingChange(vals) {
        if (this.props.onMappingChange) {
            this.props.onMappingChange(this.props.selection.elementId, {
                element_type: this.props.selection.elementType,
                element_name: this.props.selection.name,
                ...vals,
            });
        }
    }
}
