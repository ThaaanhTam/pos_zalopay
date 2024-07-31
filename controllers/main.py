import hmac
import hashlib
import logging
import qrcode
import pytz
import base64
import requests as pyreq
import json

from io import BytesIO
from decimal import Decimal
from werkzeug.urls import url_encode
from datetime import datetime, timedelta
from werkzeug.exceptions import Forbidden

from odoo import http, _, tools
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
from odoo.addons.payment.controllers import portal as payment_portal
from odoo.http import request

_logger = logging.getLogger(__name__)

class ZaloPayController(http.Controller):
    @http.route('/api/zalopay/get_payment_qr', type='http', auth='user', methods=['GET'], csrf=False)
    def get_payment_qr(self, order_id, access_token):
        # Thay đổi URL và các thông số theo API của ZaloPay
        zalopay_url = "https://sb-openapi.zalopay.vn/v2/create"  # URL API của ZaloPay (thay đổi URL nếu cần)
        
        headers = {
            'Content-Type': 'application/json',
        }

        payload = {
            'order_id': order_id,
            'access_token': access_token,
            # Thêm các thông số khác nếu cần
        }

        try:
            response = requests.post(zalopay_url, headers=headers, json=payload)
            response.raise_for_status()  # Raise an error for bad status codes
            data = response.json()
            
            # Lấy URL mã QR từ phản hồi của ZaloPay
            qr_code_url = data.get('order_url')
            if not qr_code_url:
                raise ValueError("Không tìm thấy URL mã QR trong phản hồi của ZaloPay")

            return Response(json.dumps({'qr_code_url': qr_code_url}), status=200, mimetype='application/json')
        except requests.exceptions.RequestException as e:
            _logger.error("Lỗi khi gọi API ZaloPay: %s", e)
            return Response(json.dumps({'error': str(e)}), status=500, mimetype='application/json')