/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { SmqComingSoonDialog } from "./smq_coming_soon_dialog";

// Actions rapides : ouvrent directement le formulaire de création des
// modèles existants (aucune nouvelle route, aucun nouveau modèle).
const QUICK_ACTIONS = [
    { label: "Nouveau document", icon: "fa-file-text-o", resModel: "smq.document" },
    { label: "Déclarer une non-conformité", icon: "fa-exclamation-triangle", resModel: "mgmtsystem.nonconformity" },
    { label: "Créer une action corrective", icon: "fa-check-square-o", resModel: "mgmtsystem.action", context: { default_type_action: "correction" } },
    { label: "Planifier un audit", icon: "fa-search", resModel: "mgmtsystem.audit" },
    { label: "Ajouter un processus", icon: "fa-sitemap", resModel: "smq.process" },
];

export class SmqDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.title = useService("title");
        this.dialog = useService("dialog");
        this.quickActions = QUICK_ACTIONS;

        this.state = useState({
            tiles: [],
            kpis: [],
            recentProcesses: [],
            moduleCategories: [],
            watchlist: [],
            myWork: [],
            qualityHealth: { score: null, label: "", components: [] },
            recentActivity: [],
            qualityChain: [],
            ncTrend: [],
            userName: "",
            companyName: "",
            healthDetailsOpen: false,
        });

        onWillStart(async () => {
            const data = await this.orm.call("smq.dashboard.tile", "get_dashboard_data", []);
            this.state.tiles = data.tiles;
            this.state.kpis = data.kpis;
            this.state.recentProcesses = data.recent_processes;
            this.state.moduleCategories = data.module_categories;
            this.state.watchlist = data.watchlist;
            this.state.myWork = data.my_work;
            this.state.qualityHealth = data.quality_health;
            this.state.recentActivity = data.recent_activity;
            this.state.qualityChain = data.quality_chain;
            this.state.ncTrend = data.nc_trend;
            this.state.userName = data.user_name;
            this.state.companyName = data.company_name;
        });

        onMounted(() => {
            document.body.classList.add("o_smq_dashboard_active");
            this.title.setParts({ zopenerp: false });
        });

        onWillUnmount(() => {
            document.body.classList.remove("o_smq_dashboard_active");
            this.title.setParts({ zopenerp: "Odoo" });
        });
    }

    get today() {
        return new Date().toLocaleDateString("fr-FR", {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
        });
    }

    // Regroupe les actions rapides par nature plutôt que par ordre de
    // création, en écho au découpage ISO 9001 : actes de pilotage planifiés
    // (documentation, audit, cartographie des processus) vs traitement
    // réactif d'un écart (non-conformité, action corrective — §10.2).
    get quickActionGroups() {
        const byModel = (resModel) => this.quickActions.find((qa) => qa.resModel === resModel);
        return [
            {
                label: "Piloter le système",
                actions: [byModel("smq.document"), byModel("mgmtsystem.audit"), byModel("smq.process")],
            },
            {
                label: "Traiter un écart",
                actions: [byModel("mgmtsystem.nonconformity"), byModel("mgmtsystem.action")],
            },
        ];
    }

    get healthScoreClass() {
        const score = this.state.qualityHealth.score;
        if (score === null) {
            return "o_smq_health_unknown";
        }
        if (score >= 85) {
            return "o_smq_health_good";
        }
        if (score >= 60) {
            return "o_smq_health_warning";
        }
        return "o_smq_health_critical";
    }

    get ncTrendMax() {
        let max = 1;
        for (const bucket of this.state.ncTrend) {
            max = Math.max(max, bucket.opened, bucket.closed);
        }
        return max;
    }

    barHeight(value) {
        return Math.round((value / this.ncTrendMax) * 100);
    }

    toggleHealthDetails() {
        this.state.healthDetailsOpen = !this.state.healthDetailsOpen;
    }

    onNavigate(actionXmlId) {
        if (actionXmlId) {
            this.action.doAction(actionXmlId);
        }
    }

    onOpenRecord(record) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: record.model,
            res_id: record.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onQuickAction(quickAction) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: quickAction.resModel,
            views: [[false, "form"]],
            target: "new",
            context: quickAction.context || {},
        });
    }

    onFutureClick(name) {
        this.dialog.add(SmqComingSoonDialog, { moduleName: name });
    }

    onModuleClick(module) {
        if (module.action_xmlid) {
            this.onNavigate(module.action_xmlid);
        } else {
            this.onFutureClick(module.name);
        }
    }

    onRecentActivityClick(activity) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: activity.model,
            res_id: activity.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

SmqDashboard.template = "smq_quality.SmqDashboard";
SmqDashboard.components = { Dropdown, DropdownItem };

registry.category("actions").add("smq_dashboard", SmqDashboard);
