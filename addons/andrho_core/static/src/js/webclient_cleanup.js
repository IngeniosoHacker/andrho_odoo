import { registry } from "@web/core/registry";
import { session } from "@web/session";

// The top bar keeps only what serves the ERP: no messaging or activities
// (mail is neutralized, see hooks.py) and, in the user menu, no links to
// odoo.com. "Volver a AndRho" takes people back to their dashboard.
const systray = registry.category("systray");
for (const key of ["mail.messaging_menu", "mail.activity_menu", "discuss.CallMenu"]) {
    if (systray.contains(key)) {
        systray.remove(key);
    }
}

const userMenu = registry.category("user_menuitems");
for (const key of ["support", "odoo_account", "install_pwa", "shortcuts", "im_status"]) {
    if (userMenu.contains(key)) {
        userMenu.remove(key);
    }
}

const dashboardUrl = session.andrho_dashboard_url;
if (dashboardUrl) {
    userMenu.add("andrho_dashboard", () => ({
        type: "item",
        id: "andrho_dashboard",
        description: "Volver a AndRho",
        href: dashboardUrl,
        callback: () => {
            window.location.href = dashboardUrl;
        },
        sequence: 5,
    }));
}
