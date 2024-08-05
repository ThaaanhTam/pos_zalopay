import logging

import hmac
import hashlib
import urllib.parse

from odoo import _, api, fields, models
from odoo.addons.payment_zalopay import const

_logger = logging.getLogger(__name__)


class PaymentPOSZALOPay(models.Model):
    _inherit = "payment.provider"

    zalopay_qr_tmn_code = fields.Char(
        string="ZALOPay Website Code for QR ", required_if_provider="zalopay"
    )
    

    def _get_default_payment_method_codes(self):
        """Override of `payment` to return the default payment method codes."""
        default_codes = super()._get_default_payment_method_codes()
        if self.code != "zalopay":
            return default_codes
        return const.DEFAULT_PAYMENT_METHODS_CODES