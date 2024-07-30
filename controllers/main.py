import hmac
import hashlib
import logging
import qrcode
import pytz
import base64
import requests as pyreq
import json

from io import BytesIO
from decimal import *
from werkzeug.urls import url_encode
from datetime import datetime, timedelta
from werkzeug.exceptions import Forbidden

from odoo import http, _, tools
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
from odoo.addons.payment.controllers import portal as payment_portal
from odoo.http import request


_logger = logging.getLogger(__name__)


class PaymentZaloPayPortal(payment_portal.PaymentPortal):
    _create_qr_url = "/pos/zalopay/get_payment_qr"
    _pos_ipn_url = "/pos/zalopay/callback"

    def create_new_transaction(self, pos_order_sudo, zalopay, order_amount):
      
        # Get the access token of the POS order
        access_token = pos_order_sudo.access_token

        # Get the ZALOPay QR payment method
        zalopaypay_qr_method = (
            request.env["payment.method"]
            .sudo()
            .search([("code", "=", "zalopayqr")], limit=1)
        )

        # Get the user and partner of the user
        user_sudo = request.env.user
        partner_sudo = pos_order_sudo.partner_id or self._get_partner_sudo(user_sudo)

        # Create transaction data
        prefix_kwargs = {
            "pos_order_id": pos_order_sudo.id,
        }
        transaction_data = {
            "provider_id": zalopay.id,
            "payment_method_id": zalopay_qr_method.id,
            "partner_id": partner_sudo.id,
            "partner_phone": partner_sudo.phone,
            "token_id": None,
            "amount": int(order_amount),
            "flow": "direct",
            "tokenization_requested": False,
            "landing_route": "",
            "is_validation": False,
            "access_token": access_token,
            "reference_prefix": request.env["payment.transaction"]
            .sudo()
            ._compute_reference_prefix(
                provider_code="zalopay", separator="-", **prefix_kwargs
            ),
            "custom_create_values": {
                "pos_order_id": pos_order_sudo.id,
                "tokenize": False,
            },
        }

        # Check if the currency is valid
        currency = pos_order_sudo.currency_id
        if not currency.active:
            raise AssertionError(_("The currency is invalid."))
        # Ignore the currency provided by the customer
        transaction_data["currency_id"] = currency.id

        # Create a new transaction
        tx_sudo = self._create_transaction(**transaction_data)

        return tx_sudo
