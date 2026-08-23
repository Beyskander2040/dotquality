{
    "name": "SMQ - BPMN",
    "summary": "Architecture de processus versionnés (BPMN) pour le SMQ — fondation V1",
    "version": "17.0.1.0.0",
    "category": "Quality",
    "author": "Medianet",
    "license": "AGPL-3",
    "application": False,
    "depends": ["smq_quality", "smq_document", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/smq_bpmn_task_mapping_views.xml",
        "views/smq_process_version_reject_wizard_views.xml",
        "views/smq_process_version_views.xml",
        "views/smq_process_views.xml",
        "views/smq_bpmn_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # bpmn-js v18.9.1 — vendu localement (aucun CDN), chargé avant
            # tout le reste du module.
            "smq_bpmn/static/src/lib/bpmn-js/bpmn-modeler.development.js",
            "smq_bpmn/static/src/lib/bpmn-js/assets/diagram-js.css",
            "smq_bpmn/static/src/lib/bpmn-js/assets/bpmn-js.css",
            "smq_bpmn/static/src/lib/bpmn-js/assets/bpmn-font/css/bpmn.css",
            "smq_bpmn/static/src/scss/smq_bpmn_editor.scss",
            "smq_bpmn/static/src/js/smq_bpmn_editor.esm.js",
            "smq_bpmn/static/src/js/smq_bpmn_properties_panel.esm.js",
            "smq_bpmn/static/src/js/smq_bpmn_editor_widget.esm.js",
        ],
    },
}
