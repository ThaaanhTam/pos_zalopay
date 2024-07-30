# pos_zalopay/controllers/main.py
import logging
import hmac
import hashlib
import json
import time
import requests
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class PosZaloPayController(http.Controller):

    @http.route('/pos/zalopay/get_payment_qr', type='json', auth='public', methods=['POST'])
    def get_payment_qr(self, orderId, amount):
        zalopay_api_url = 'https://sb-openapi.zalopay.vn/v2/create'
        app_id = request.env['payment.provider'].search([('code', '=', 'zalopay')]).appid
        app_key = request.env['payment.provider'].search([('code', '=', 'zalopay')]).key1
        app_user = request.env['payment.provider'].search([('code', '=', 'zalopay')]).app_user
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
            _logger.error("Error in ZaloPay request: %s", e)
            return {'error': str(e)}
