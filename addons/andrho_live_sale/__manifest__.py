{
    "name": "AndRho Venta en vivo",
    "summary": "Lives de Facebook e Instagram: orden de venta, apartados, confirmaciones, tarjetas de envío y clientes frecuentes",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "AndRho",
    "category": "Sales",
    # andrho-api does the talking with Meta (comments, Messenger) and calls
    # this module's andrho_* methods over JSON-RPC; Odoo keeps the
    # operational side: items, reservations in stock, shipping cards.
    "depends": ["stock", "andrho_core"],
    "data": [
        "security/live_sale_groups.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "report/paperformat.xml",
        "report/shipping_cards.xml",
        "views/live_sale_views.xml",
        "views/live_card_views.xml",
        "views/live_buyer_views.xml",
        "views/menus.xml",
    ],
    # Installed only when the seller turns live sales on in AndRho: it
    # starts enabled (post_init_hook).
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
    "auto_install": False,
}
