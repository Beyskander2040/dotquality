/** @odoo-module **/

import { Component, useState, useEffect, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SMQ_NAV, SMQ_SIDEBAR_APP_XMLID } from "./smq_sidebar_config";
import { SmqComingSoonDialog } from "./smq_coming_soon_dialog";

const STORAGE_KEY = "smq.sidebar.collapsed";

export class SmqSidebar extends Component {
    static template = "smq_quality.SmqSidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.nav = SMQ_NAV;

        this.state = useState({
            collapsed: window.localStorage.getItem(STORAGE_KEY) === "1",
            // Accordéon : un module (groupe) n'affiche ses sous-modules
            // qu'une fois déplié ; tous repliés par défaut.
            expandedGroups: {},
        });

        // Au premier rendu (déclenché par le mount initial du WebClient),
        // menuService n'a pas encore résolu l'app courante : elle n'est
        // fixée qu'ensuite, dans webclient.js/onMounted -> loadRouterState(),
        // qui déclenche l'évènement bus "MENUS:APP-CHANGED" une fois prêt.
        // Sans écouter cet évènement, ce composant ne se re-rend jamais et
        // reste bloqué sur son état initial (isSmqApp toujours faux) — c'est
        // exactement le même bus event que NavBar écoute pour la même
        // raison (voir web/static/src/webclient/navbar/navbar.js).
        const renderOnAppChange = () => this.render();
        this.env.bus.addEventListener("MENUS:APP-CHANGED", renderOnAppChange);
        onWillUnmount(() => {
            this.env.bus.removeEventListener("MENUS:APP-CHANGED", renderOnAppChange);
        });

        // WebClient monte NavBar / ActionContainer / SmqSidebar comme
        // enfants directs de <body> (voir web/static/src/start.js) : il n'y
        // a pas de conteneur commun à mettre en display:flex. On réserve
        // donc la place pour la sidebar via une marge sur .o_action_manager
        // (classe déjà existante côté Odoo), pilotée par ces classes sur
        // <body>, elles-mêmes actives seulement pendant que l'app SMQ est
        // affichée — aucune autre application n'est donc affectée.
        useEffect(
            (isSmqApp, collapsed) => {
                document.body.classList.toggle("o_smq_app_active", isSmqApp);
                document.body.classList.toggle("o_smq_sidebar_is_collapsed", isSmqApp && collapsed);
                return () => {
                    document.body.classList.remove("o_smq_app_active");
                    document.body.classList.remove("o_smq_sidebar_is_collapsed");
                };
            },
            () => [this.isSmqApp, this.state.collapsed]
        );
    }

    get isSmqApp() {
        const currentApp = this.menuService.getCurrentApp();
        return Boolean(currentApp && currentApp.xmlid === SMQ_SIDEBAR_APP_XMLID);
    }

    toggleCollapsed() {
        this.state.collapsed = !this.state.collapsed;
        window.localStorage.setItem(STORAGE_KEY, this.state.collapsed ? "1" : "0");
    }

    isGroupExpanded(key) {
        return Boolean(this.state.expandedGroups[key]);
    }

    toggleGroup(key) {
        this.state.expandedGroups[key] = !this.isGroupExpanded(key);
    }

    onGroupHeaderClick(group) {
        if (this.state.collapsed) {
            // En mode réduit, un clic ré-ouvre la sidebar plutôt que de
            // déplier un sous-menu flottant (pas de flyout dans cette version).
            this.toggleCollapsed();
            return;
        }
        this.toggleGroup(group.key);
    }

    onItemClick(item) {
        if (this.state.collapsed) {
            // En mode réduit, un clic ré-ouvre la sidebar au lieu d'ouvrir
            // un sous-menu flottant (pas de flyout dans cette version).
            this.toggleCollapsed();
            return;
        }
        if (item.comingSoon || !item.actionXmlId) {
            this.dialog.add(SmqComingSoonDialog, { moduleName: item.label });
            return;
        }
        this.actionService.doAction(item.actionXmlId);
    }

    onKeydown(action, ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            action();
        }
    }
}
