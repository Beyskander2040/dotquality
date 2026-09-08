/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";
import { SmqSidebar } from "./smq_sidebar";

// Injection de la sidebar SMQ dans le webclient standard via l'API
// officielle d'extension OWL (patch()) — pas de modification des fichiers
// du core Odoo. Le composant lui-même décide de s'afficher ou non selon
// l'app active (voir SmqSidebar.isSmqApp) : hors SMQ, il ne rend rien et
// n'affecte aucune autre application.
patch(WebClient, {
    components: { ...WebClient.components, SmqSidebar },
});
