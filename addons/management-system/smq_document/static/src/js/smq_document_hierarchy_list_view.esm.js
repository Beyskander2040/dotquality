/** @odoo-module **/

import {Component, useState, xml} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {Field} from "@web/views/fields/field";
import {listView} from "@web/views/list/list_view";

// Renderer JS branché via js_class="smq_document_hierarchy_list" sur
// view_smq_document_tree (type="tree" réel, inchangé — voir Odoo
// web/static/src/views/view.js: un arch avec js_class="X" fait remplacer
// tout le descripteur de vue par registry.category("views").get("X"), tout
// en gardant le vrai type Python "tree"). Donc : même liste "Tous les
// documents"/"Documents en validation"/etc. partout où elle est déjà
// utilisée, mêmes Controller/Model/ArchParser réels (recherche, filtres,
// tri, pagination inchangés) — seul le Renderer change, pour rendre les
// documents en arbre plié/déplié sur parent_document_id au lieu d'une
// liste plate, y compris à l'intérieur d'un regroupement natif ("Grouper
// par Processus" : le pliage du groupe réutilise la vraie méthode
// group.toggle() du modèle, seule l'imbrication document/document à
// l'intérieur d'un groupe est faite ici).
//
// Choix délibéré : ne PAS patcher/étendre le ListRenderer réel (~2200
// lignes, très couplé à l'édition inline, au drag&drop, à la pagination —
// disproportionné pour ce besoin). On délègue le rendu de chaque cellule
// au composant Field standard (mêmes widgets que la vraie liste) et on
// réutilise les classes CSS réelles d'Odoo (o_list_table, o_group_header,
// o_data_row...) pour un rendu visuellement identique à la liste standard.
//
// Limites assumées : pas d'édition inline, pas de tri par clic sur
// colonne, pas de drag&drop — cette vue est en lecture seule pour la
// hiérarchie (ouvrir une ligne va au formulaire réel). Un enfant pourrait
// être chargé sur une autre "page" que son parent au-delà de la limite
// ci-dessous ; vu le volume réel de documents SMQ, la limite est fixée
// haut plutôt que d'implémenter une pagination consciente de l'arbre. Un
// second niveau de regroupement natif empilé (ex. Processus puis Type)
// affiche un message au lieu de l'arbre pour ce cas précis.

const _STRUCTURAL_FIELD = "parent_document_id";

function buildTree(records) {
    const nodeByResId = new Map(records.map((record) => [record.resId, {record, children: []}]));
    const roots = [];
    for (const record of records) {
        const node = nodeByResId.get(record.resId);
        const parentValue = record.data[_STRUCTURAL_FIELD];
        const parentResId = parentValue ? parentValue[0] : false;
        if (parentResId && nodeByResId.has(parentResId)) {
            nodeByResId.get(parentResId).children.push(node);
        } else {
            roots.push(node);
        }
    }
    return roots;
}

class SmqDocumentTreeRows extends Component {
    static template = xml`
        <t t-foreach="props.nodes" t-as="node" t-key="node.record.id">
            <tr class="o_data_row">
                <td class="o_smq_doc_tree_toggle_cell"
                    t-att-style="'padding-left: ' + (props.level * 20) + 'px'">
                    <span class="o_smq_doc_tree_toggle" t-on-click.stop="() => props.toggle(node.record.resId)">
                        <i t-if="node.children.length"
                           t-attf-class="fa fa-fw {{props.isExpanded(node.record.resId) ? 'fa-caret-down' : 'fa-caret-right'}}"/>
                    </span>
                </td>
                <td t-foreach="props.columns" t-as="col" t-key="col.id" class="o_data_cell"
                    t-on-click="() => props.openRecord(node.record)">
                    <Field name="col.name" record="node.record" type="col.widget || undefined"/>
                </td>
            </tr>
            <t t-if="props.isExpanded(node.record.resId)">
                <SmqDocumentTreeRows
                    nodes="node.children" columns="props.columns" level="props.level + 1"
                    openRecord="props.openRecord" isExpanded="props.isExpanded" toggle="props.toggle"/>
            </t>
        </t>
    `;
    static props = ["nodes", "columns", "level", "openRecord", "isExpanded", "toggle"];
}
SmqDocumentTreeRows.components = {SmqDocumentTreeRows, Field};

export class SmqDocumentHierarchyListRenderer extends Component {
    static template = xml`
        <div class="o_list_renderer o_renderer table-responsive o_smq_doc_hierarchy_list">
            <table t-attf-class="o_list_table table table-sm table-hover position-relative mb-0 {{props.list.isGrouped ? 'o_list_table_grouped' : 'o_list_table_ungrouped table-striped'}}">
                <thead>
                    <tr>
                        <th style="width: 28px;"/>
                        <th t-foreach="fieldColumns" t-as="col" t-key="col.id" class="opacity-trigger-hover">
                            <div class="d-flex">
                                <span class="d-block min-w-0 text-truncate flex-grow-1" t-esc="col.label || col.name"/>
                            </div>
                        </th>
                    </tr>
                </thead>
                <tbody>
                    <t t-if="props.list.isGrouped">
                        <t t-foreach="props.list.groups" t-as="group" t-key="group.id">
                            <tr t-attf-class="{{group.count > 0 ? 'o_group_has_content' : ''}} o_group_header {{!group.isFolded ? 'o_group_open' : ''}} cursor-pointer"
                                t-on-click="() => group.toggle()">
                                <th class="o_group_name fs-6 fw-bold" t-att-class="!group.isFolded ? 'text-900' : 'text-700'"
                                    t-att-colspan="fieldColumns.length + 1">
                                    <div class="d-flex align-items-center">
                                        <span t-attf-class="o_group_caret fa fa-fw me-1 {{group.isFolded ? 'fa-caret-right' : 'fa-caret-down'}}"/>
                                        <t t-esc="(group.displayName || 'Aucun') + ' (' + group.count + ')'"/>
                                    </div>
                                </th>
                            </tr>
                            <t t-if="!group.isFolded">
                                <tr t-if="group.list.isGrouped">
                                    <td t-att-colspan="fieldColumns.length + 1" class="text-muted small p-2">
                                        Un second niveau de regroupement n'est pas pris en charge par
                                        l'affichage hiérarchique.
                                    </td>
                                </tr>
                                <SmqDocumentTreeRows
                                    t-else=""
                                    nodes="buildTree(group.records)" columns="fieldColumns" level="1"
                                    openRecord="props.openRecord" isExpanded="isExpanded" toggle="toggle"/>
                            </t>
                        </t>
                    </t>
                    <SmqDocumentTreeRows
                        t-else=""
                        nodes="buildTree(props.list.records)" columns="fieldColumns" level="0"
                        openRecord="props.openRecord" isExpanded="isExpanded" toggle="toggle"/>
                </tbody>
            </table>
            <p t-if="!props.list.isGrouped and !props.list.records.length" class="text-muted p-3">
                Aucun document.
            </p>
        </div>
    `;
    static components = {SmqDocumentTreeRows};
    static props = ["list", "archInfo", "openRecord", "*"];

    setup() {
        this.state = useState({collapsedIds: new Set()});
        this.isExpanded = this.isExpanded.bind(this);
        this.toggle = this.toggle.bind(this);
        this.buildTree = buildTree;
    }

    get fieldColumns() {
        return this.props.archInfo.columns.filter(
            (col) => col.type === "field" && col.name !== _STRUCTURAL_FIELD
        );
    }

    isExpanded(resId) {
        return !this.state.collapsedIds.has(resId);
    }

    toggle(resId) {
        const next = new Set(this.state.collapsedIds);
        if (next.has(resId)) {
            next.delete(resId);
        } else {
            next.add(resId);
        }
        this.state.collapsedIds = next;
    }
}

export const smqDocumentHierarchyListView = {
    ...listView,
    Renderer: SmqDocumentHierarchyListRenderer,
    limit: 100000,
};

registry.category("views").add("smq_document_hierarchy_list", smqDocumentHierarchyListView);
