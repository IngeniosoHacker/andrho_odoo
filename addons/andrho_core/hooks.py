# What mail does towards the outside and the user is switched off: AndRho's
# platform sends the notifications and watches the instance. Field tracking
# (mail.tracking.value) stays: it's the audit log AndRho reads.

CRONS_TO_DISABLE = [
    "mail.ir_cron_mail_scheduler_action",       # outgoing mail queue
    "mail.ir_cron_module_update_notification",  # publisher warranty (Odoo S.A.)
    "digest.ir_cron_digest_scheduler_action",   # digest emails
]

MENUS_TO_HIDE = [
    "mail.menu_root_discuss",
]


def post_init_hook(env):
    for xmlid in CRONS_TO_DISABLE:
        cron = env.ref(xmlid, raise_if_not_found=False)
        if cron:
            cron.active = False

    for xmlid in MENUS_TO_HIDE:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu:
            menu.active = False

    env["digest.digest"].search([]).write({"state": "deactivated"})
