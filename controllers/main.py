import logging
import json
import hmac
import hashlib
import requests
import time

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class PosZaloPayController(http.Controller):

    @http.route('/pos/zalpay/get_payment_qr', type='json', auth='public', methods=['POST'])
    def get_payment_qr(self, orderId, amount):
        # Lấy thông tin cấu hình từ mô hình payment.provider của ZaloPay
        provider = request.env['payment.provider'].sudo().search([('code', '=', 'zalopay')], limit=1)
        if not provider:
            return {'error': 'ZaloPay provider not configured'}

        app_id = provider.appid
        app_key = provider.key1
        app_user = provider.app_user

        if not app_id or not app_key or not app_user:
            return {'error': 'Missing ZaloPay configuration parameters'}

        zalopay_api_url = 'https://sb-openapi.zalopay.vn/v2/create'

        app_trans_id = f'{int(time.time())}_{orderId}'
        embed_data = '{}'
        items = '[]'

        # Tạo chữ ký
        data = f'{app_id}|{app_trans_id}|{app_user}|{amount}|{app_key}'
        mac = hmac.new(app_key.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()

        # Tạo payload
        payload = {
            'app_id': app_id,
            'app_trans_id': app_trans_id,
            'app_user': app_user,
            'amount': amount,
            'description': f'Thanh toán đơn hàng {orderId}',
            'embed_data': embed_data,
            'item': items,
            'mac': mac
        }

        # Gửi yêu cầu tới API của ZaloPay
        try:
            response = requests.post(zalopay_api_url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
            response_data = response.json()

            if response_data['return_code'] == 1:
                order_url = response_data['order_url']
                return {'order_url': order_url}
            else:
                return {'error': response_data.get('sub_return_message', 'Unknown error')}
        except Exception as e:
            _logger.error("Error while creating ZaloPay order: %s", e)
            return {'error': str(e)}
