# AndRho's ERP: Odoo 19 Community plus AndRho's own modules (addons/).
# Every client's container runs this image (VPS/odoo/provision-client.sh);
# each client's database installs only the modules it needs.
#
#   docker build -t andrho-odoo:19.0 .
FROM odoo:19.0

USER root
COPY ./addons /mnt/extra-addons
COPY ./odoo.conf /etc/odoo/odoo.conf
RUN chown -R odoo: /mnt/extra-addons
USER odoo
