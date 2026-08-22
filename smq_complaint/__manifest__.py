{
    "name": "SMQ - Réclamations clients",
    "summary": "Registre des réclamations clients (ISO 9001 §9.1.2)",
    "version": "17.0.1.0.0",
    "category": "Quality",
    "author": "Medianet",
    "license": "AGPL-3",
    "application": False,
    "depends": [
        "smq_quality",
        "smq_organization",
        "mgmtsystem_action",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/smq_dashboard_tile_data.xml",
        "views/smq_complaint_views.xml",
        "views/smq_complaint_menus.xml",
        "demo/smq_complaint_demo.xml",
    ],
}
