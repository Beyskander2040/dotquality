{
    "name": "SMQ - Référentiels & Conformité",
    "summary": "Référentiels normatifs, exigences et matrice de conformité du SMQ",
    "version": "17.0.1.0.0",
    "category": "Quality",
    "author": "Medianet",
    "license": "AGPL-3",
    "application": False,
    "depends": ["smq_quality", "smq_document"],
    "data": [
        "security/ir.model.access.csv",
        "views/smq_referential_views.xml",
        "views/smq_referential_requirement_views.xml",
        "views/smq_compliance_line_views.xml",
        "views/smq_referential_menus.xml",
        "demo/smq_referential_demo.xml",
    ],
}
