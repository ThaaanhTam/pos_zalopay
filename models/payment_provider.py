import logging

import hmac
import hashlib
import urllib.parse

from odoo import _, api, fields, models
from odoo.addons.payment_zalopay import const

_logger = logging.getLogger(__name__)


class PaymentPOSVNPay(models.Model):
    _inherit = "payment.provider"

    zalopay_qr_tmn_code = fields.Char(
        string="ZALOPay Website Code for QR ", required_if_provider="zalopay"
    )