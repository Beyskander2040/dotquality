/** @odoo-module **/

import {Component, onMounted, useRef, useState, xml} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {SmqBpmnEditor} from "./smq_bpmn_editor.esm";
import {SmqBpmnPropertiesPanel} from "./smq_bpmn_properties_panel.esm";

// LOT 9/10 : widget de champ Odoo encapsulant l'éditeur graphique bpmn-js
// pour smq.process.version.bpmn_xml, complété au LOT 10 par un panneau de
// propriétés (sélection → BPMN Element + mapping Odoo, §14-17). Le backend
// (LOT 8 write() verrouillé + checksum serveur ; LOT 10 verrouillage des
// mappings + validations) reste seul décisionnaire : ce widget ne fait que
// proposer/refléter l'état, jamais l'appliquer lui-même.
export class SmqBpmnEditorWidget extends Component {
    static template = xml`
        <div class="o_smq_bpmn_editor_widget" t-ref="container">
            <div class="o_smq_bpmn_editor_toolbar">
                <div class="o_smq_bpmn_editor_toolbar_group">
                    <button
                        t-if="!props.readonly"
                        type="button"
                        class="btn btn-primary btn-sm"
                        t-on-click="onSaveClick"
                        title="Enregistrer le diagramme BPMN et les mappings"
                    >
                        <i class="fa fa-save"/> Enregistrer
                    </button>
                    <button
                        t-if="!props.readonly"
                        type="button"
                        class="btn btn-secondary btn-sm"
                        t-on-click="onImportClick"
                        title="Importer un fichier BPMN/XML"
                    >
                        <i class="fa fa-upload"/> Importer
                    </button>
                    <button
                        type="button"
                        class="btn btn-secondary btn-sm"
                        t-on-click="onExportClick"
                        title="Exporter le diagramme en fichier .bpmn"
                    >
                        <i class="fa fa-download"/> Exporter
                    </button>
                    <input
                        type="file"
                        accept=".bpmn,.xml"
                        t-ref="fileInput"
                        class="o_smq_bpmn_editor_file_input"
                        t-on-change="onFileSelected"
                    />
                </div>
                <div class="o_smq_bpmn_editor_toolbar_group">
                    <button type="button" class="btn btn-secondary btn-sm" t-on-click="onZoomOutClick" title="Zoom arrière">
                        <i class="fa fa-search-minus"/>
                    </button>
                    <button type="button" class="btn btn-secondary btn-sm" t-on-click="onZoomFitClick" title="Ajuster à la fenêtre">
                        <i class="fa fa-arrows-alt"/>
                    </button>
                    <button type="button" class="btn btn-secondary btn-sm" t-on-click="onZoomInClick" title="Zoom avant">
                        <i class="fa fa-search-plus"/>
                    </button>
                </div>
                <div class="o_smq_bpmn_editor_status">
                    <span t-if="props.readonly" class="badge text-bg-secondary">
                        <i class="fa fa-lock"/> Version verrouillée (lecture seule)
                    </span>
                    <span t-elif="isDirty" class="badge text-bg-warning">
                        Modifications non enregistrées
                    </span>
                </div>
            </div>
            <div class="o_smq_bpmn_editor_body">
                <SmqBpmnEditor
                    bpmnXml="props.record.data[props.name] || ''"
                    readonly="props.readonly"
                    onChange="(xmlContent) => this._onChange(xmlContent)"
                    onReady="(api) => this._onReady(api)"
                    onImportError="() => this._onImportError()"
                    onSelectionChanged="(info) => this._onSelectionChanged(info)"
                />
                <SmqBpmnPropertiesPanel
                    selection="state.currentSelection"
                    mappingInfo="state.mappingInfo"
                    readonly="props.readonly"
                    availableModels="state.availableModels"
                    availableActions="state.availableActions"
                    availableDocuments="state.availableDocuments"
                    onElementPropertyChange="(elementId, vals) => this._onElementPropertyChange(elementId, vals)"
                    onMappingChange="(elementId, vals) => this._onMappingChange(elementId, vals)"
                />
            </div>
        </div>
    `;

    static components = {SmqBpmnEditor, SmqBpmnPropertiesPanel};
    static props = {...standardFieldProps};

    setup() {
        this.bpmnApi = null;
        this.fileInputRef = useRef("fileInput");
        this.containerRef = useRef("container");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.state = useState({
            currentSelection: false,
            mappingInfo: null,
            pendingMappings: {},
            availableModels: [],
            availableActions: [],
            availableDocuments: [],
            mappingsDirty: false,
        });

        onMounted(() => this._loadReferenceData());
    }

    get isDirty() {
        return Boolean(this.props.record.dirty) || this.state.mappingsDirty;
    }

    /** @private */
    async _loadReferenceData() {
        // Chargées une seule fois par montage du panneau — jamais par
        // sélection ni par frappe (§36). ir.model est réservé au groupe
        // technique (base.group_system) : un Editor/Manager SMQ ordinaire ne
        // peut pas le lire directement, d'où l'appel à une méthode dédiée
        // (sudo() côté serveur) plutôt qu'un orm.searchRead("ir.model", ...)
        // direct qui échouerait par AccessError.
        this.state.availableModels = await this.orm.call(
            "smq.bpmn.task.mapping",
            "get_available_models",
            []
        );
        this.state.availableActions = await this.orm.call(
            "smq.bpmn.task.mapping",
            "get_available_actions",
            []
        );
        this.state.availableDocuments = await this.orm.call(
            "smq.bpmn.task.mapping",
            "get_available_documents",
            []
        );
    }

    /** @private */
    _onChange(xmlContent) {
        if (this.props.readonly) {
            return;
        }
        this.props.record.update({[this.props.name]: xmlContent});
    }

    /** @private */
    _onReady(api) {
        this.bpmnApi = api;
    }

    /** @private */
    _onImportError() {
        this.notification.add(
            _t("Impossible de charger le diagramme BPMN. Le fichier XML est invalide."),
            {type: "danger"}
        );
    }

    /**
     * §17 : la sélection déclenche le chargement (ou la ré-utilisation d'une
     * modification locale déjà en attente) du mapping Odoo correspondant.
     * Un seul appel RPC par sélection, jamais de polling.
     * @private
     */
    async _onSelectionChanged(info) {
        this.state.currentSelection = info;
        if (!info) {
            this.state.mappingInfo = null;
            return;
        }
        const pending = this.state.pendingMappings[info.elementId];
        if (pending) {
            this.state.mappingInfo = pending;
            return;
        }
        if (!this.props.record.resId) {
            this.state.mappingInfo = {found: false};
            return;
        }
        this.state.mappingInfo = null;
        this.state.mappingInfo = await this.orm.call(
            "smq.bpmn.task.mapping",
            "get_mapping_for_element",
            [this.props.record.resId, info.elementId]
        );
    }

    /**
     * Propriétés BPMN standard (Name/Documentation) — appliquées
     * immédiatement au diagramme en mémoire via bpmn-js (jamais persistées
     * sans clic sur "Enregistrer" : c'est commandStack.changed qui marque
     * le champ bpmn_xml local comme modifié, exactement comme au LOT 9).
     * @private
     */
    _onElementPropertyChange(elementId, vals) {
        if (this.props.readonly || !this.bpmnApi) {
            return;
        }
        if ("name" in vals) {
            this.bpmnApi.updateElementName(elementId, vals.name);
        }
        if ("documentation" in vals) {
            this.bpmnApi.updateElementDocumentation(elementId, vals.documentation);
        }
    }

    /**
     * Propriétés du mapping Odoo — accumulées localement (§37) : jamais de
     * RPC ici, uniquement au clic sur "Enregistrer".
     * @private
     */
    _onMappingChange(elementId, vals) {
        if (this.props.readonly) {
            return;
        }
        const existing = this.state.pendingMappings[elementId] || this.state.mappingInfo || {};
        const merged = {...existing, ...vals, bpmn_element_id: elementId, found: true};
        this.state.pendingMappings[elementId] = merged;
        this.state.mappingInfo = merged;
        this.state.mappingsDirty = true;
    }

    /** @private */
    _validateFile(file) {
        if (!file) {
            return false;
        }
        const name = file.name.toLowerCase();
        return name.endsWith(".bpmn") || name.endsWith(".xml");
    }

    onImportClick() {
        if (this.props.readonly) {
            return;
        }
        if (this.fileInputRef.el) {
            this.fileInputRef.el.click();
        }
    }

    async onFileSelected(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (this.fileInputRef.el) {
            this.fileInputRef.el.value = "";
        }
        if (!file) {
            return;
        }
        if (!this._validateFile(file)) {
            this.notification.add(_t("Fichier invalide. Sélectionnez un fichier .bpmn ou .xml."), {
                type: "danger",
            });
            return;
        }
        try {
            const xmlContent = await this._readFileAsText(file);
            if (this.bpmnApi) {
                // Import ≠ sauvegarde automatique : le diagramme importé ne
                // vit que dans le champ local (dirty) jusqu'au clic sur
                // "Enregistrer".
                await this.bpmnApi.importDiagram(xmlContent);
            }
        } catch (err) {
            console.error("Error importing BPMN file:", err);
            this.notification.add(
                _t("Impossible de charger le diagramme BPMN. Le fichier XML est invalide."),
                {type: "danger"}
            );
        }
    }

    /**
     * @param {File} file
     * @returns {Promise<String>}
     * @private
     */
    _readFileAsText(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = (e) => reject(e);
            reader.readAsText(file);
        });
    }

    async onExportClick() {
        if (!this.bpmnApi) {
            return;
        }
        const xmlContent = await this.bpmnApi.exportDiagram();
        if (!xmlContent) {
            this.notification.add(_t("Impossible d'exporter le diagramme BPMN."), {type: "danger"});
            return;
        }
        const base = (this.props.record.data.display_name || "diagramme").replace(
            /[^a-zA-Z0-9_-]+/g,
            "_"
        );
        this._downloadFile(xmlContent, `${base}.bpmn`);
    }

    /** @private */
    _downloadFile(content, fileName) {
        const blob = new Blob([content], {type: "application/xml"});
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    onZoomInClick() {
        if (this.bpmnApi) this.bpmnApi.zoomIn();
    }

    onZoomOutClick() {
        if (this.bpmnApi) this.bpmnApi.zoomOut();
    }

    onZoomFitClick() {
        if (this.bpmnApi) this.bpmnApi.zoomFit();
    }

    /**
     * §37-38 : un seul clic "Enregistrer" sauvegarde le BPMN XML et tous les
     * mappings Odoo modifiés en un seul appel serveur (action_save_bpmn_
     * and_mappings), donc dans une seule transaction — jamais d'état
     * intermédiaire où l'un est sauvegardé et l'autre non. Vérifie d'abord
     * que bpmn-js peut réellement exporter le XML (§22) avant tout envoi.
     */
    async onSaveClick() {
        if (this.props.readonly) {
            this.notification.add(
                _t("Cette version du processus est verrouillée et ne peut plus être modifiée."),
                {type: "warning"}
            );
            return;
        }
        if (!this.bpmnApi) {
            return;
        }
        const xmlContent = await this.bpmnApi.exportDiagram();
        if (!xmlContent) {
            this.notification.add(_t("Impossible d'enregistrer le diagramme BPMN."), {type: "danger"});
            return;
        }

        if (!this.props.record.resId) {
            // Version pas encore créée : les mappings ne peuvent pas encore
            // référencer process_version_id — on se limite à l'enregistrement
            // standard du champ (comportement LOT 9), les mappings pourront
            // être configurés une fois la version sauvegardée.
            this.props.record.update({[this.props.name]: xmlContent});
            try {
                await this.props.record.save();
            } catch (err) {
                this.notification.add(
                    (err && err.data && err.data.message) ||
                        _t("Impossible d'enregistrer le diagramme BPMN."),
                    {type: "danger"}
                );
            }
            return;
        }

        const mappingValsList = Object.values(this.state.pendingMappings).map((vals) => {
            const copy = {...vals};
            delete copy._pendingNew;
            delete copy.found;
            delete copy.is_orphaned;
            delete copy.mappable_types;
            // odoo_model_id / odoo_action_id peuvent porter soit un tuple
            // [id, label] (jamais modifiés depuis leur lecture serveur),
            // soit un entier simple (modifiés via le <select> du panneau) —
            // write()/create() n'acceptent qu'un entier (ou False).
            if (Array.isArray(copy.odoo_model_id)) copy.odoo_model_id = copy.odoo_model_id[0];
            if (Array.isArray(copy.odoo_action_id)) copy.odoo_action_id = copy.odoo_action_id[0];
            if (Array.isArray(copy.procedure_document_id)) copy.procedure_document_id = copy.procedure_document_id[0];
            if (Array.isArray(copy.form_document_id)) copy.form_document_id = copy.form_document_id[0];
            return copy;
        });

        try {
            await this.orm.call("smq.process.version", "action_save_bpmn_and_mappings", [
                [this.props.record.resId],
                xmlContent,
                mappingValsList,
            ]);
        } catch (err) {
            this.notification.add(
                (err && err.data && err.data.message) ||
                    _t("Impossible d'enregistrer le diagramme BPMN."),
                {type: "danger"}
            );
            return;
        }

        this.state.pendingMappings = {};
        this.state.mappingsDirty = false;
        await this.props.record.load();
        if (this.state.currentSelection) {
            await this._onSelectionChanged(this.state.currentSelection);
        }
    }
}

export const smqBpmnEditorField = {
    component: SmqBpmnEditorWidget,
    supportedTypes: ["text"],
};

registry.category("fields").add("smq_bpmn_editor", smqBpmnEditorField);
