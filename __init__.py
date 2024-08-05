# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models

from odoo.addons.payment import setup_provider, reset_payment_provider


def post_init_hook(env):
    # Search for the "zalopay" provider in the "payment.provider" model
    payment_zalopay = env["payment.provider"].search([("code", "=", "zalopay")], limit=1)
    # Search for the "zalopay" method in the "payment.method" model
    method_zalopay = env["payment.method"].search([("code", "=", "zalopay")], limit=1)
    # Search for the "zalopayqr" method in the "payment.method" model
    method_zalopay_qr = env["payment.method"].search([("code", "=", "zalopayqr")], limit=1)

    # Link the found payment method to the found payment provider
    if method_zalopay.id is not False and method_zalopay_qr.id is not False:
        payment_zalopay.write(
            {
                "payment_method_ids": [(6, 0, [method_zalopay.id, method_zalopay_qr.id])],
            }
        )

    website = env["website"].get_current_website()
    website_id = website.id
    # Searching for the first website record (current website) and getting its first associated company ID (current company)
    company_id = (
        env["website"]
        .search([("id", "=", website_id)], limit=1)
        .read()[0]["company_id"][0]
    )

    # Search for the "zalopay-QR" payment method in the "pos.payment.method" model
    pos_payment_method_zalopay = env["pos.payment.method"].search(
        [("name", "=", "ZaloPay-QR")], limit=1
    )

    # Link the found payment method and company to the found payment provider
    if company_id is not False:
        pos_payment_method_zalopay.write(
            {
                "company_id": [(6, 0, [company_id])],
                "online_payment_provider_ids": [(6, 0, [payment_zalopay.id])],
            }
        )
