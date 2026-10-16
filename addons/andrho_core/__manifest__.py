{
    "name": "AndRho Core",
    "summary": "Odoo como el ERP de AndRho: entrada desde el panel, marca AndRho y sin canales propios de Odoo",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "AndRho",
    "category": "Hidden",
    # stock is every account's base (inventory); it already pulls in mail
    # and digest, which this module neutralizes.
    "depends": ["web", "mail", "digest", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "views/webclient_templates.xml",
    ],
    "assets": {
        # Before web's own variables: they are all !default.
        "web._assets_primary_variables": [
            ("prepend", "andrho_core/static/src/scss/primary_variables.scss"),
        ],
        "web.assets_backend": [
            "andrho_core/static/src/scss/backend.scss",
            "andrho_core/static/src/js/webclient_cleanup.js",
        ],
        "web.assets_frontend": [
            "andrho_core/static/src/scss/frontend.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
}
