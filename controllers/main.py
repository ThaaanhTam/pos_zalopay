import logging
import json
import urllib.parse
from odoo import http
from odoo.http import request
from werkzeug.exceptions import BadRequest

_logger = logging.getLogger(__name__)

class PaymentZaloPayController(http.Controller):
    @http.route('/payment/zalopay/return', type='http', auth='public', methods=['GET'], csrf=False)
    def zalopay_return(self, **post):
        # Xử lý phản hồi từ ZaloPay sau khi thanh toán
        _logger.info("ZaloPay return response: %s", post)
        # Kiểm tra và xác thực dữ liệu từ ZaloPay
        if 'order_id' not in post:
            return request.render('payment_zalopay.error_page', {})

        transaction = request.env['payment.transaction'].search([('app_trans_id', '=', post['order_id'])])
        if not transaction:
            return request.render('payment_zalopay.error_page', {})

        # Xử lý xác nhận thanh toán thành công
        transaction.write({'state': 'done'})
        return request.render('payment_zalopay.success_page', {})

    @http.route('/payment/zalopay/callback', type='http', auth='public', methods=['POST'], csrf=False)
    def zalopay_callback(self, **post):
        # Xử lý callback từ ZaloPay
        _logger.info("ZaloPay callback response: %s", post)
        try:
            order_id = post.get('order_id')
            if not order_id:
                raise BadRequest("Order ID is missing")

            transaction = request.env['payment.transaction'].search([('app_trans_id', '=', order_id)])
            if not transaction:
                raise BadRequest("Transaction not found")

            # Xác nhận thanh toán và cập nhật trạng thái đơn hàng
            transaction.write({'state': 'done'})
        except Exception as e:
            _logger.error("ZaloPay callback failed: %s", e)
            return request.make_response(json.dumps({'status': 'error'}), status=500)

        return request.make_response(json.dumps({'status': 'success'}), status=200)
    
    @http.route('/pos/vnpay/get_payment_qr', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payment_qr(self, **kwargs):
        # Tạo mã QR cho thanh toán
        _logger.info("Generating payment QR code")
        try:
            transaction_id = kwargs.get('transaction_id')
            if not transaction_id:
                raise BadRequest("Transaction ID is missing")

            transaction = request.env['payment.transaction'].search([('id', '=', int(transaction_id))])
            if not transaction:
                raise BadRequest("Transaction not found")

            # Tạo mã QR hoặc URL thanh toán
            qr_url = transaction._get_specific_rendering_values({})
            return request.make_response(json.dumps({'qr_url': qr_url['api_url']}), status=200)
        except Exception as e:
            _logger.error("Failed to generate payment QR code: %s", e)
            return request.make_response(json.dumps({'status': 'error'}), status=500)
