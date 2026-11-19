{
    "name": "AndRho Personal en obra",
    "summary": "Personal por obra, cuadrillas y su ubicación, reportados por WhatsApp a AndRho",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "AndRho",
    "category": "Human Resources",
    # andrho-api talks to WhatsApp (supervisors write from the site) and
    # calls this module's andrho_* methods over JSON-RPC. The photos of the
    # workers live only here, in the client's ERP.
    "depends": ["hr", "andrho_core"],
    "data": [
        "security/ir.model.access.csv",
        "views/crew_views.xml",
        "views/hr_employee_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
