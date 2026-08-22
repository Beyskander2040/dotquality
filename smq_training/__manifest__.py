{
    "name": "SMQ - Formations",
    "summary": "Suivi des formations qualité (ISO 9001 §7.2 Compétence)",
    "version": "17.0.1.0.0",
    "category": "Quality",
    "author": "Medianet",
    "license": "AGPL-3",
    "application": False,
    "depends": [
        "smq_quality",
        "hr_skills",
        "mgmtsystem_action",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/smq_dashboard_tile_data.xml",
        "views/smq_training_views.xml",
        "views/smq_training_menus.xml",
        "demo/smq_training_demo.xml",
    ],
}
