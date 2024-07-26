# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import controllers
from . import models


def post_init_hook(env):
    # Search for the "zalopay" provider in the "payment.provider" model
    payment_zalopay = env["payment.provider"].search([("code", "=", "zalopay")], limit=1)
    # Search for the "zalopay" method in the "payment.method" model
    method_zalopay_qr = env["payment.method"].search([("code", "=", "zalopayqr")], limit=1)

    # Link the found payment method to the found payment provider
    if method_zalopay_qr.id is not False:
        payment_zalopay.write(
            {
                "payment_method_ids": [(6, 0, [method_zalopay_qr.id])],
            }
        )
