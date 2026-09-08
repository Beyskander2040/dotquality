{
    "name": "SMQ - Document",
    "summary": "Gestion documentaire du SMQ : identité, types, statuts, versions contrôlées",
    "version": "17.0.1.0.0",
    "category": "Quality",
    "author": "Medianet",
    "license": "AGPL-3",
    "depends": ["smq_quality", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/smq_document_stage_data.xml",
        "data/smq_document_type_data.xml",
        "views/smq_document_type_views.xml",
        "views/smq_document_stage_views.xml",
        "views/smq_document_version_views.xml",
        "views/smq_document_wizard_views.xml",
        "views/smq_document_views.xml",
        "views/smq_document_menus.xml",
        "data/smq_document_demo_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "smq_document/static/src/scss/smq_document_hierarchy.scss",
            "smq_document/static/src/js/smq_document_hierarchy_list_view.esm.js",
        ],
    },
}
