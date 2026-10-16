# andrho_odoo

La imagen Docker del ERP de AndRho: Odoo 19 Community con el módulo
`andrho_core`. Cada cliente que se registra en AndRho recibe un contenedor con
esta imagen (`VPS/odoo/provision-client.sh`), su propia base de datos con
Inventario (`stock`) y los módulos que la API decidió en el registro.

```sh
docker build -t andrho-odoo:19.0 .
```

### Qué hace `andrho_core` (`addons/andrho_core`)

| Pieza | Archivo |
|---|---|
| **Entrada sin login** desde el botón ERP del panel: `/andrho/sso?t=<token>` valida un token firmado por andrho-api (HMAC-SHA256 con `andrho.sso_secret`, 60 s, un solo uso), crea al usuario de AndRho si es su primera vez (dueño y admins con los permisos del administrador; el resto, usuario de inventario) y abre la sesión. | `models/sso.py`, `models/res_users.py`, `controllers/main.py` |
| `/web/login` y el cierre de sesión llevan de vuelta al panel de AndRho (`andrho.dashboard_url`). `?local=1` deja el formulario de Odoo para soporte. | `controllers/main.py` |
| **Marca AndRho**: barra tinta con la línea menta, acciones en teal, Inter y Space Grotesk, el logo de AndRho en el menú de apps, título "AndRho ERP", sin "Powered by Odoo" ni enlaces a odoo.com, y "Volver a AndRho" en el menú del usuario. | `static/src/scss/*`, `static/src/js/webclient_cleanup.js`, `views/webclient_templates.xml` |
| **`mail` neutralizado** (sección 3): ningún correo sale (`ir.mail_server.send_email`), crons de correo, *publisher warranty* y digest apagados, Discuss oculto, chatter y actividades ocultos. El tracking se conserva. | `hooks.py`, `models/ir_mail_server.py` |

El script de la VPS crea la base de datos, el administrador (el correo y nombre
del dueño en AndRho, así que no hay paso de "crear la cuenta" en el navegador),
la empresa, `andrho.sso_secret` y `andrho.dashboard_url`, y desinstala
`mail_bot`. La propuesta original sigue abajo; `tu_saas_core` es `andrho_core`.

---

## Propuesta técnica: MVP de Odoo Community (solo Inventario) como servicio gestionado

**Versión objetivo:** Odoo 19.0 Community (LGPLv3)
**Fecha:** 16 de octubre de 2026
**Alcance del MVP:** imagen Docker propia + aprovisionamiento automático por cliente + Inventario (`stock`) controlado por la plataforma externa.

---

## 1. Resumen

El MVP consiste en una imagen Docker de Odoo 19 Community con nuestros módulos propios incluidos. Cada cliente que se registra en nuestra plataforma recibe su propia base de datos de Odoo, con **solo Inventario** instalado, y su propio contenedor.

Nuestra plataforma externa (sign up, despliegue y monitoreo) es la **fuente de verdad** para usuarios, notificaciones y supervisión. Odoo queda como **motor de inventario**: guarda los datos y aplica la lógica de stock, pero no envía correos, no notifica a usuarios y no se comunica con servicios de Odoo S.A.

---

## 2. Qué instala realmente `stock` en Odoo 19

Dependencias declaradas en los manifiestos de la rama `19.0`:

| Módulo | Depende de |
|---|---|
| `stock` | `product`, `barcodes_gs1_nomenclature`, `digest` |
| `product` | `base`, **`mail`**, `uom` |
| `digest` | **`mail`**, `portal`, `resource` |
| `barcodes_gs1_nomenclature` | `barcodes`, `uom` |
| `barcodes` | `web` |
| `uom` | `base` |

Para el roadmap posterior:

| Módulo | Depende de |
|---|---|
| `point_of_sale` | `resource`, `stock_account`, `barcodes`, `html_editor`, `digest`, `phone_validation`, `partner_autocomplete`, `iot_base`, `google_address_autocomplete` |
| `stock_account` | `stock`, `account` (Contabilidad) |

**Conclusión:** Inventario funciona solo, sin Ventas, Compras ni Contabilidad. Pero **`mail` siempre se instala**, porque lo exigen `product` y `digest`.

---

## 3. El problema de `mail` y la decisión propuesta

### 3.1 Por qué no se puede quitar

`mail` no es solo "correo". Proporciona la clase `mail.thread`, de la que heredan los modelos centrales de Inventario: `product.template`, `stock.picking`, `stock.lot` y otros. Esa herencia aporta:

- **Chatter**: el historial de mensajes en cada formulario.
- **Tracking**: registro automático de cambios de campos (quién cambió qué y cuándo).
- **Actividades**: tareas asignadas con fecha de vencimiento.
- **Seguidores y notificaciones**: correos y avisos internos.
- **Discuss**: la app de mensajería interna y el bot (OdooBot).

Desinstalar `mail` desinstala `product` y, en cascada, `stock`. Hacer un fork del core para eliminarlo rompería cada actualización. **Quitarlo no es viable.**

### 3.2 Por qué no nos conviene tal como viene

Nuestra plataforma externa va a monitorear y gestionar cada instancia. Si `mail` queda con su comportamiento por defecto:

1. **Canales duplicados**: Odoo enviaría sus propias notificaciones y correos (invitaciones, actividades, resúmenes *digest*) en paralelo con los nuestros, con otra marca y otro tono.
2. **Correos fallidos acumulados**: sin servidor SMTP configurado, los correos quedan en cola como errores y la cola crece sin límite.
3. **Llamadas a Odoo S.A.**: `mail` incluye una tarea programada que contacta a los servidores de Odoo (*publisher warranty*). No queremos tráfico saliente que no controlamos.
4. **Interfaz con ruido**: el chatter, el ícono de actividades y Discuss compiten con la experiencia que queremos dar y con nuestra UI propia.
5. **Datos dispersos**: si los usuarios dejan notas en el chatter, parte de la operación queda dentro de Odoo y fuera de nuestro monitoreo.

### 3.3 Decisión: mantener `mail` instalado, pero neutralizado

Nuestro módulo base (`tu_saas_core`) apaga todo lo que `mail` hace **hacia afuera y hacia el usuario**, y conserva lo que nos sirve **hacia adentro**:

| Componente de `mail` | Decisión | Motivo |
|---|---|---|
| Envío de correos | **Apagar** | Las notificaciones las envía nuestra plataforma. |
| Cron de cola de correo | **Desactivar** | Evita acumular correos fallidos. |
| Cron *publisher warranty* | **Desactivar** | Sin tráfico hacia Odoo S.A. |
| Digest (resúmenes por correo) | **Desactivar** | Canal duplicado. |
| Invitación por correo al crear usuarios | **Suprimir** | Los usuarios se crean y avisan desde nuestra plataforma. |
| OdooBot (`mail_bot`) | **Desinstalar** | Es `auto_install`, se puede quitar sin romper nada. |
| Discuss (menú) | **Ocultar** | Mensajería fuera de alcance. |
| Chatter y actividades en la UI | **Ocultar** | Interfaz limpia; se reemplaza en la fase de UI nueva. |
| **Tracking de cambios** | **Conservar** | Es un registro de auditoría gratuito que nuestra plataforma puede leer. |

El tracking es la pieza que convierte a `mail` de problema en ventaja: cada cambio de estado en una transferencia o de campo en un producto queda en `mail.tracking.value`, y nuestra plataforma lo puede consultar por API como log de auditoría.

---

## 4. Integración con la plataforma externa

La plataforma necesita tres cosas de cada instancia: **crearla**, **controlarla** y **enterarse de lo que pasa**.

### 4.1 Crear (aprovisionamiento)

Flujo disparado al completar el sign up:

1. Plataforma genera `tenant_id`, subdominio y credenciales.
2. Crea la base de datos del cliente con los módulos elegidos (en el MVP: `stock` + `tu_saas_core`).
3. Crea un usuario técnico de integración con API key.
4. Levanta el contenedor de servicio del cliente con su `db-filter`.
5. Configura el proxy inverso para el subdominio.
6. Ejecuta un health check y marca la instancia como activa.

### 4.2 Controlar (API)

Odoo 19 incluye la nueva **API JSON-2** (`/json/2/<modelo>/<método>`) con autenticación por API key. Es la que debe usar la plataforma; XML-RPC y JSON-RPC clásicos quedaron marcados como obsoletos.

Usos típicos: crear usuarios, leer niveles de stock, leer movimientos y consultar el log de tracking.

> Al crear usuarios por API, pasar el contexto `{"no_reset_password": true}` para que Odoo no envíe la invitación por correo.

### 4.3 Enterarse (eventos)

Dos mecanismos, del más simple al más reactivo:

- **Polling**: la plataforma consulta periódicamente `stock.move`, `stock.picking` y `mail.tracking.value` filtrando por `write_date`. Simple y suficiente para el MVP.
- **Webhooks**: el módulo `base_automation` (Community) permite reglas de automatización con la acción *Enviar notificación por webhook*. Nuestro módulo puede crear reglas que envían un POST a la plataforma cuando, por ejemplo, una transferencia pasa a `done` o un producto baja de su stock mínimo.

**Recomendación:** polling en el MVP, webhooks en cuanto la plataforma tenga el endpoint listo.

### 4.4 Salud de la instancia

- `GET /web/health` para saber si el contenedor responde.
- Métricas del contenedor (CPU, RAM) desde el orquestador.
- Una tarea programada propia en Odoo que reporte un *heartbeat* a la plataforma (opcional).

---

## 5. Arquitectura del MVP

```
┌─────────────────────────────┐
│   Plataforma externa        │  sign up · facturación · monitoreo · notificaciones
│   (backend propio)          │
└──────┬───────────────┬──────┘
       │ aprovisiona   │ API JSON-2 / webhooks
       ▼               ▼
┌─────────────────────────────┐
│ Proxy inverso (Traefik/Nginx)│  cliente1.tudominio.com → contenedor cliente1
└──────┬──────────────────────┘
       ▼
┌──────────────┐ ┌──────────────┐
│ odoo-cliente1│ │ odoo-cliente2│  misma imagen: mi-odoo:19.0
└──────┬───────┘ └──────┬───────┘
       └───────┬────────┘
               ▼
       ┌──────────────┐
       │  PostgreSQL  │  una base de datos por cliente
       └──────────────┘
```

Un contenedor por cliente es lo más simple para el MVP. Si el número de clientes crece mucho, se puede migrar a un grupo de contenedores compartidos con `dbfilter = ^%d$` sin cambiar la imagen.

---

## 6. Implementación

### 6.1 Estructura del repositorio

```
odoo-saas/
├── Dockerfile
├── odoo.conf
├── scripts/
│   └── provision_tenant.sh
└── addons/
    └── tu_saas_core/
        ├── __init__.py
        ├── __manifest__.py
        ├── hooks.py
        ├── data/
        │   └── ir_config_parameter.xml
        └── static/src/
            ├── scss/hide_mail.scss
            └── js/systray_cleanup.js
```

### 6.2 Dockerfile

```dockerfile
FROM odoo:19.0
USER root
COPY ./addons /mnt/extra-addons
COPY ./odoo.conf /etc/odoo/odoo.conf
USER odoo
```

### 6.3 odoo.conf

```ini
[options]
addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons
list_db = False
proxy_mode = True
without_demo = all
; contraseña maestra inyectada por el orquestador, nunca en el repo
admin_passwd = ${ODOO_MASTER_PASSWORD}
```

> La imagen oficial no expande variables dentro de `odoo.conf`. Inyectar `admin_passwd` en el arranque (plantilla con `envsubst` o parámetro `--admin-passwd`) desde el orquestador.

### 6.4 Módulo `tu_saas_core`

**`__manifest__.py`**

```python
{
    "name": "SaaS Core",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "depends": ["stock", "base_automation"],
    "data": ["data/ir_config_parameter.xml"],
    "assets": {
        "web.assets_backend": [
            "tu_saas_core/static/src/scss/hide_mail.scss",
            "tu_saas_core/static/src/js/systray_cleanup.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
}
```

**`__init__.py`**

```python
from .hooks import post_init_hook
```

**`hooks.py`**: desactiva lo que sale de la instancia.

```python
CRONS_TO_DISABLE = [
    "mail.ir_cron_mail_scheduler_action",        # cola de correo saliente
    "mail.ir_cron_module_update_notification",   # publisher warranty (Odoo S.A.)
    "digest.ir_cron_digest_scheduler_action",    # resúmenes digest
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

    bot = env["ir.module.module"].search(
        [("name", "=", "mail_bot"), ("state", "=", "installed")]
    )
    if bot:
        bot.button_immediate_uninstall()
```

> Los identificadores XML de crons y menús deben verificarse contra el código de la rama 19.0 durante la fase de validación. El `raise_if_not_found=False` evita que la instalación falle si alguno cambió de nombre.

**`data/ir_config_parameter.xml`**: evita que Odoo use direcciones propias como remitente o *catchall*.

```xml
<odoo>
    <record id="param_catchall_domain" model="ir.config_parameter">
        <field name="key">mail.catchall.domain</field>
        <field name="value"></field>
    </record>
</odoo>
```

**`static/src/scss/hide_mail.scss`**: oculta el chatter mientras llega la UI nueva.

```scss
// Verificar el selector del contenedor de chatter en 19.0
.o-mail-Form-chatter {
    display: none !important;
}
```

**`static/src/js/systray_cleanup.js`**: quita los íconos de mensajería y actividades de la barra superior.

```javascript
import { registry } from "@web/core/registry";

const systray = registry.category("systray");
// Verificar las claves exactas en 19.0 con registry.category("systray").getEntries()
for (const key of ["mail.messaging_menu", "mail.activity_menu"]) {
    if (systray.contains(key)) {
        systray.remove(key);
    }
}
```

> Ocultar por CSS/JS es la solución rápida para el MVP. En la fase de UI nueva, el chatter se elimina directamente en el renderizado de formularios.

### 6.5 Script de aprovisionamiento

```bash
#!/usr/bin/env bash
# Uso: provision_tenant.sh <tenant_id> <modulos_separados_por_coma>
set -euo pipefail

TENANT="$1"
MODULES="${2:-stock}"
DB="t_${TENANT}"
IMAGE="mi-odoo:19.0"
NETWORK="saas"

# 1. Crear base de datos e instalar módulos
docker run --rm --network "$NETWORK" \
  -e HOST=postgres -e USER=odoo -e PASSWORD="$PG_PASSWORD" \
  "$IMAGE" \
  odoo -d "$DB" -i "${MODULES},tu_saas_core" \
       --without-demo=all --stop-after-init

# 2. Levantar el contenedor de servicio del cliente
docker run -d --name "odoo-${TENANT}" --network "$NETWORK" \
  -e HOST=postgres -e USER=odoo -e PASSWORD="$PG_PASSWORD" \
  --label "traefik.enable=true" \
  --label "traefik.http.routers.${TENANT}.rule=Host(\`${TENANT}.tudominio.com\`)" \
  "$IMAGE" \
  odoo --db-filter="^${DB}\$" --proxy-mode

# 3. Health check
for i in {1..30}; do
  if docker exec "odoo-${TENANT}" curl -fs http://localhost:8069/web/health >/dev/null; then
    echo "OK ${TENANT}"; exit 0
  fi
  sleep 2
done
echo "FALLO health check ${TENANT}" >&2; exit 1
```

La creación del usuario de integración y su API key se hace en un paso posterior, desde la plataforma, con un `odoo shell` o por API usando el usuario administrador inicial.

---

## 7. Pasos a seguir

### Fase 0 · Decisiones (1–2 días)
- [ ] Confirmar Odoo 19.0 como versión fija del producto.
- [ ] Elegir orquestador para el MVP (Docker + Traefik, o Kubernetes si ya existe).
- [ ] Definir esquema de nombres: `tenant_id`, base de datos, subdominio.
- [ ] Decidir mecanismo de eventos inicial: polling (recomendado) o webhooks.

### Fase 1 · Imagen base (2–3 días)
- [ ] Crear repo con Dockerfile y `odoo.conf`.
- [ ] Construir la imagen y levantar una instancia manual con solo `stock`.
- [ ] Listar todos los módulos que quedaron instalados y documentarlo.

### Fase 2 · Módulo `tu_saas_core` (3–5 días)
- [ ] Implementar el hook de neutralización de `mail`.
- [ ] Verificar los identificadores XML de crons, menús y systray en 19.0.
- [ ] Ocultar chatter, actividades y Discuss.
- [ ] Desinstalar `mail_bot`.
- [ ] Prueba: operar una semana simulada (recepciones, entregas, ajustes) y confirmar que **no se crea ningún registro en `mail.mail`** y que no hay tráfico saliente.
- [ ] Prueba: confirmar que el tracking sigue registrando cambios en `mail.tracking.value`.

### Fase 3 · Aprovisionamiento automático (4–6 días)
- [ ] Script o servicio de aprovisionamiento llamado desde el backend.
- [ ] Creación del usuario de integración y API key por cliente, guardada en el gestor de secretos de la plataforma.
- [ ] Configuración automática del subdominio en el proxy.
- [ ] Health check y cambio de estado del tenant en la plataforma.
- [ ] Flujo inverso: suspender y eliminar un tenant (contenedor + base de datos + respaldo final).

### Fase 4 · Integración de monitoreo (4–6 días)
- [ ] Cliente de la API JSON-2 en la plataforma.
- [ ] Polling de movimientos de stock y log de tracking.
- [ ] Alertas de stock mínimo generadas por la plataforma.
- [ ] Respaldos automáticos por base de datos (`pg_dump` + filestore).

### Fase 5 · Validación del MVP (2–3 días)
- [ ] Prueba de punta a punta: sign up → instancia activa → operación → datos visibles en la plataforma.
- [ ] Prueba de carga: N tenants simultáneos en el mismo host; medir RAM por contenedor.
- [ ] Prueba de actualización: aplicar un cambio en `tu_saas_core` y actualizar todos los tenants (`-u tu_saas_core`).

**Estimación total del MVP:** 3–5 semanas para una persona, según el estado actual de la plataforma externa.

---

## 8. Fuera del MVP (siguientes fases)

| Fase | Contenido | Nota técnica |
|---|---|---|
| UI propia | Interfaz con estética tecnológica, sin apariencia de Odoo | Módulo de tema que sobrescribe SCSS y plantillas OWL vía `web.assets_backend`. No hacer fork de `web`. Aquí se elimina el chatter de raíz. |
| Branding | Nombre, logo y favicon propios | Community es LGPLv3 y se puede modificar, pero "Odoo" es marca registrada: no usarla en el producto. |
| POS | Punto de venta con fichas en markdown y comparativas por categoría | `point_of_sale` instala Contabilidad (`account`) vía `stock_account`. |
| POS · dependencias externas | — | `partner_autocomplete` y `google_address_autocomplete` llaman a servicios externos (IAP de Odoo, Google). Habrá que neutralizarlos igual que `mail`. |
| Módulos a la carta | Selección de módulos según las necesidades del sign up | Una sola imagen con todos los módulos; cada base de datos instala solo los suyos. |

---

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Un módulo futuro reactiva correos o crons de `mail` | Prueba automática en CI: tras instalar cualquier combinación de módulos, verificar que no hay crons de correo activos ni registros en `mail.mail`. |
| Los selectores CSS/JS cambian entre versiones | Fijar la versión 19.0 y revisar `tu_saas_core` en cada migración. |
| Consumo de RAM con muchos tenants | Medir en Fase 5 y tener lista la migración a contenedores compartidos con `dbfilter`. |
| Usuarios crean usuarios desde la UI de Odoo y se envían invitaciones | Restringir la gestión de usuarios a la plataforma (quitar permisos de administración de usuarios al administrador del cliente). |
