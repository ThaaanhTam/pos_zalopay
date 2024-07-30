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
    _logger.info("Dữ liệu phản hồi từ ZaloPayyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy")
    # def _handle_zalopay_response(self, data):
    #     """
    #     Xử lý phản hồi từ ZaloPay.
    #     """
    #     # Ghi log dữ liệu phản hồi để kiểm tra
    #     _logger.info("Dữ liệu phản hồi từ ZaloPay: %s", data)

    #     # Lấy order_url từ dữ liệu phản hồi
    #     order_url = data.get('order_url')

    #     # Ghi log order_url để kiểm tra
    #     if order_url:
    #         _logger.info("Order URL từ phản hồi ZaloPay: %s", order_url)
    #     else:
    #         _logger.info("Không có Order URL trong phản hồi ZaloPay")

    #     # Tìm hoặc tạo giao dịch thanh toán
    #     tx = self.search([('reference', '=', data.get('reference'))])
    #     if tx:
    #         tx.write({'order_url': order_url})
        
    #     return tx
