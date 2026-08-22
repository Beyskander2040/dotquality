/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class SmqComingSoonDialog extends Component {
    static components = { Dialog };
    static props = { moduleName: String, close: Function };
    static template = xml`
        <Dialog title="'À venir'" size="'md'">
            <div class="o_smq_coming_soon_dialog">
                <i class="fa fa-road o_smq_coming_soon_icon" />
                <p>
                    <strong t-esc="props.moduleName" /> fait partie de la roadmap du SMQ
                    et sera disponible prochainement.
                </p>
            </div>
            <t t-set-slot="footer">
                <button class="btn btn-primary" t-on-click="() => this.props.close()">
                    Compris
                </button>
            </t>
        </Dialog>
    `;
}
