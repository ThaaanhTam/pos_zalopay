import hashlib
import logging
import base64
import json
import qrcode
from io import BytesIO

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)

class ZaloPayController(http.Controller):

    @http.route('/pos/zalopay/get_payment_qr', type='json', methods=['POST'], auth='public', csrf=False)
    def get_payment_qr(self, order_id, amount):
        try:
            # Retrieve provider information
            provider = request.env['payment.provider'].sudo().search([('code', '=', 'zalopay')], limit=1)
            if not provider:
                return {'error': 'ZaloPay provider not found'}

            # Prepare request data
            data = {
                'appId': provider.zalopay_app_id,
                'merchantCode': provider.zalopay_merchant_code,
                'amount': amount,
                'orderId': str(order_id),
                'callbackUrl': provider.zalopay_callback_url,
                'returnUrl': provider.zalopay_return_url,
                'checksum': ''
            }

            # Create checksum
            checksum_str = f"{data['appId']}|{data['merchantCode']}|{data['amount']}|{data['orderId']}|{provider.zalopay_secret_key}"
            data['checksum'] = hashlib.md5(checksum_str.encode()).hexdigest()

            # Call ZaloPay API
            response = request.env['payment.provider'].sudo()._call_zalopay_api('create_payment_url', data)
            response_data = response.json()

            # Generate QR code
            qr_code = qrcode.make(response_data['paymentUrl'])
            qr_code_file = BytesIO()
            qr_code.save(qr_code_file, format='PNG')
            qr_code_base64 = base64.b64encode(qr_code_file.getvalue()).decode('utf-8')

            return {'qr_code': qr_code_base64, 'payment_url': response_data['paymentUrl']}
        except Exception as e:
            _logger.error('Error in ZaloPay QR code generation: %s', str(e))
            return {'error': 'Failed to generate QR code'}

    @http.route('/pos/zalopay/callback', type='json', methods=['POST'], auth='public', csrf=False)
    def zalopay_callback(self, **post):
        try:
            # Retrieve provider information
            provider = request.env['payment.provider'].sudo().search([('code', '=', 'zalopay')], limit=1)
            if not provider:
                return 'error'

            # Validate checksum
            checksum_str = f"{post.get('appId')}|{post.get('orderId')}|{post.get('amount')}|{post.get('status')}|{provider.zalopay_secret_key}"
            checksum = hashlib.md5(checksum_str.encode()).hexdigest()
            if checksum != post.get('checksum'):
                return 'error'

            # Find transaction and update status
            tx = request.env['payment.transaction'].sudo().search([('reference', '=', post.get('orderId'))], limit=1)
            if tx:
                tx.write({'state': 'done'})
                return 'success'
            else:
                return 'error'
        except Exception as e:
            _logger.error('Error in ZaloPay callback handling: %s', str(e))
            return 'error'
