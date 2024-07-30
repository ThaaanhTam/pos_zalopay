import logging
import json
import hmac
import hashlib
import requests
import time

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class PosZaloPayController(http.Controller):

    @http.route('/pos/zalpay/get_payment_qr', type='json', auth='public', methods=['POST'])
    def get_payment_qr(self, orderId, amount):
        _logger.info('Starting ZaloPay payment QR creation for Order ID: %s, Amount: %s', orderId, amount)

        # Lấy thông tin cấu hình từ mô hình payment.provider của ZaloPay
        provider = request.env['payment.provider'].sudo().search([('code', '=', 'zalopay')], limit=1)
        if not provider:
            _logger.error('ZaloPay provider not configured')
            return {'error': 'ZaloPay provider not configured'}

        app_id = provider.appid
        app_key = provider.key1
        app_user = provider.app_user

        if not app_id or not app_key or not app_user:
            _logger.error('Missing ZaloPay configuration parameters: app_id=%s, app_key=%s, app_user=%s', app_id, app_key, app_user)
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

        _logger.info('ZaloPay Payload: %s', json.dumps(payload))

        # Gửi yêu cầu tới API của ZaloPay
        try:
            response = requests.post(zalopay_api_url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
            response_data = response.json()

            _logger.info('ZaloPay Response: %s', response_data)

            if response_data.get('return_code') == 1:
                order_url = response_data.get('order_url')
                _logger.info('Generated QR Code URL: %s', order_url)
                return {'order_url': order_url}
            else:
                error_message = response_data.get('sub_return_message', 'Unknown error')
                _logger.error('ZaloPay error: %s', error_message)
                return {'error': error_message}
        except Exception as e:
            _logger.error('Error while creating ZaloPay order: %s', str(e))
            return {'error': str(e)}
