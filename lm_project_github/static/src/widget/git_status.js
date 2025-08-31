/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

class GitConnectionStatus extends Component {
    get isConnected() {
        return this.props.record.data[this.props.name];
    }
}

GitConnectionStatus.template = "lm_project_git.GitConnectionStatus";

registry.category("fields").add("git_connection_status", {
    component: GitConnectionStatus,
});
