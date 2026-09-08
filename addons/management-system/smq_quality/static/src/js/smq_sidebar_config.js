/** @odoo-module **/

// Arborescence statique de la sidebar SMQ, regroupée par domaine
// fonctionnel plutôt que par ordre de création. "actionXmlId" = écran réel
// déjà existant (aucune route/modèle recréé). "comingSoon: true" = aucun
// modèle derrière ce point d'entrée ; le clic ouvre une information "à
// venir", jamais une donnée fictive.
export const SMQ_SIDEBAR_APP_XMLID = "smq_quality.menu_smq_root";

export const SMQ_NAV = [
    {
        key: "overview",
        label: "Tableau de bord",
        icon: "fa-home",
        actionXmlId: "smq_quality.action_smq_dashboard_client",
    },
    {
        key: "organization",
        label: "Organisation & Périmètre",
        icon: "fa-sitemap",
        sectionLabel: "Qualité",
        children: [
            { key: "site_list", label: "Sites", actionXmlId: "smq_organization.action_smq_site" },
            { key: "department_list", label: "Départements", actionXmlId: "hr.hr_department_kanban_action" },
            { key: "activity_list", label: "Activités", actionXmlId: "smq_organization.action_smq_activity" },
            { key: "stakeholder_list", label: "Parties intéressées", actionXmlId: "smq_organization.action_smq_stakeholder" },
            { key: "scope_list", label: "Périmètre du SMQ", actionXmlId: "smq_organization.action_smq_scope" },
        ],
    },
    {
        key: "quality_management",
        label: "Management de la qualité",
        icon: "fa-folder-o",
        children: [
            { key: "doc_all", label: "Documents", actionXmlId: "smq_document.action_smq_document_all" },
            { key: "doc_validation", label: "Documents en validation", actionXmlId: "smq_document.action_smq_document_in_validation" },
            { key: "process_list", label: "Processus", actionXmlId: "smq_quality.action_smq_process" },
            { key: "risk_list", label: "Risques & Opportunités", actionXmlId: "smq_risk.action_smq_risk" },
            { key: "objectives_list", label: "Objectifs qualité", comingSoon: true },
            { key: "indicators", label: "Indicateurs", comingSoon: true },
        ],
    },
    {
        key: "referential",
        label: "Référentiels & Conformité",
        icon: "fa-check-square-o",
        children: [
            { key: "referential_list", label: "Référentiels", actionXmlId: "smq_referential.action_smq_referential" },
            { key: "requirement_list", label: "Exigences", actionXmlId: "smq_referential.action_smq_referential_requirement" },
            { key: "compliance_matrix", label: "Matrice de conformité", actionXmlId: "smq_referential.action_smq_compliance_line" },
        ],
    },
    {
        key: "improvement",
        label: "Amélioration",
        icon: "fa-exclamation-triangle",
        sectionLabel: "Amélioration & Parties prenantes",
        children: [
            { key: "nc", label: "Non-conformités", actionXmlId: "smq_quality_bridge.action_smq_nonconformity" },
            { key: "actions", label: "Actions correctives", actionXmlId: "smq_quality_bridge.action_smq_corrective_action" },
            { key: "action_templates", label: "Modèles d'actions", actionXmlId: "mgmtsystem_action_template.mgmtsystem_action_template_act_window" },
            { key: "audit_list", label: "Audits internes", actionXmlId: "smq_quality_bridge.action_smq_audit" },
        ],
    },
    {
        key: "people_partners",
        label: "Personnes & partenaires",
        icon: "fa-handshake-o",
        children: [
            { key: "competency_list", label: "Compétences", actionXmlId: "smq_quality_bridge.action_smq_employee_skill" },
            { key: "training_list", label: "Formations", actionXmlId: "smq_training.action_smq_training" },
            { key: "complaints", label: "Réclamations clients", actionXmlId: "smq_complaint.action_smq_complaint" },
            { key: "suppliers", label: "Fournisseurs", actionXmlId: "smq_supplier.action_smq_supplier_evaluation" },
        ],
    },
    {
        key: "governance",
        label: "Gouvernance",
        icon: "fa-briefcase",
        children: [
            { key: "mgmt_review", label: "Revue de direction", actionXmlId: "smq_quality_bridge.action_smq_management_review" },
            { key: "revisions", label: "Révisions", actionXmlId: "smq_document.action_smq_document_to_review" },
        ],
    },
    {
        key: "admin",
        label: "Administration",
        icon: "fa-cog",
        sectionLabel: "Administration",
        children: [
            { key: "users", label: "Utilisateurs", actionXmlId: "base.action_res_users" },
            { key: "groups", label: "Rôles & permissions", actionXmlId: "base.action_res_groups" },
            { key: "company", label: "Société", actionXmlId: "base.action_res_company_form" },
            // "Paramètres SMQ" retiré (Lot 6) : aucun besoin métier concret
            // identifié à ce jour qui justifierait un smq.config.settings
            // dédié — tout le paramétrage réel existant (catégories de
            // processus, types/statuts de document, échelles de risque,
            // taxonomie NC, critères/niveaux fournisseur...) est déjà
            // accessible via le menu Configuration natif. Pas de destination
            // unique cohérente vers laquelle rediriger cette entrée : mieux
            // vaut la retirer que promettre un écran vide ou mal étiqueté.
        ],
    },
];
