import logging
import json
import hmac
import hashlib
import urllib.parse
from datetime import datetime
from time import time
import random

from werkzeug import urls
from odoo import _, api, fields, models
from odoo.addons.payment_zalopay import const
from odoo.http import request

_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    order_url = fields.Char(string="Order URL")

    def _handle_zalopay_response(self, data):
        """
        Xử lý phản hồi từ ZaloPay.
        """
        _logger.info("Dữ liệu phản hồi từ ZaloPay: %s", data)

        # Lấy order_url từ dữ liệu phản hồi
        order_url = data.get('order_url')

        # Ghi log order_url để kiểm tra
        if order_url:
            _logger.info("Order URL từ phản hồi ZaloPay: %s", order_url)
        else:
            _logger.info("Không có Order URL trong phản hồi ZaloPay")

        # Tìm hoặc tạo giao dịch thanh toán
        tx = self.search([('reference', '=', data.get('reference'))])
        if tx:
            _logger.info("Giao dịch thanh toán tìm thấy với reference: %s", data.get('reference'))
            tx.write({'order_url': order_url})
        else:
            _logger.info("Không tìm thấy giao dịch thanh toán với reference: %s", data.get('reference'))

        return tx

    def _process_payment_response(self, data):
        """
        Xử lý phản hồi thanh toán.
        """
        _logger.info("Bắt đầu xử lý phản hồi thanh toán: %s", data)
        
        # Xử lý phản hồi từ ZaloPay
        self._handle_zalopay_response(data)
        
        # Các bước xử lý khác nếu cần

