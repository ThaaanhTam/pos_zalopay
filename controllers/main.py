from odoo import http
from odoo.http import request

class ZaloPayController(http.Controller):

    @http.route('/pos/zalopay/get_payment_qr', type='json', auth='public', methods=['POST'], csrf=False)
    def get_payment_qr(self, orderId, amount):
        provider = request.env['payment.provider'].sudo().search([('code', '=', 'zalopay')], limit=1)
        if not provider:
            return {'error': 'No ZaloPay provider found'}
        
        # Tạo data request cho ZaloPay
        data = {
            'app_id': provider.zalopay_app_id,
            'app_trans_id': orderId,
            'app_user': 'User001',  # Có thể thay đổi theo yêu cầu
            'amount': amount,
            'embed_data': '',
            'item': '[{"itemid":"knb","itemname":"Kim nguyen bao","itemquantity":1,"itemprice":1000}]',
            'description': 'Thanh toán đơn hàng #{}'.format(orderId),
            'mac': ''
        }
        
        # Tính toán chữ ký (checksum)
        raw_data = '|'.join([str(data[k]) for k in sorted(data.keys())])
        mac = hmac.new(provider.zalopay_secret_key.encode(), raw_data.encode(), hashlib.sha256).hexdigest()
        data['mac'] = mac
        
        # Gửi yêu cầu đến ZaloPay
        response = requests.post(provider.zalopay_endpoint, json=data)
        result = response.json()
        
        if result.get('return_code') == 1:
            return {
                'payment_url': result['order_url']
            }
        else:
            return {
                'error': result.get('return_message', 'Failed to create QR code')
            }
