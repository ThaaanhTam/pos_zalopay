import hmac
import hashlib
import logging
import qrcode
import pytz
import base64
import requests as pyreq
import json
import random

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

class ZaloPayController(payment_portal.PaymentPortal):

    _create_qr_url = "/api/zalopay/get_payment_qr"
    _pos_ipn_url = "/pos/zalopay/callback"



    @http.route(
            _create_qr_url,
            type='json',
            auth='public', 
            methods=['POST'], 
            csrf=False)
    def get_payment_qr(self, amount):
        """Tạo đơn hàng thanh toán ZaloPay và trả về phản hồi."""
        _logger.info("Đang tạo đơn hàng thanh toán ZaloPay.")
        trans_id = random.randrange(1000000)
       
        try:
            # Lấy thông tin ZaloPay
            zalopay = (
                http.request.env["payment.provider"]
                .sudo()
                .search([("code", "=", "zalopay")], limit=1)
            )
            
            if not zalopay:
                raise ValueError("Không tìm thấy nhà cung cấp ZaloPay")
            
            _logger.info("Đã tìm thấy nhà cung cấp ZaloPay: %s", zalopay)
            app_id = int(zalopay.appid)
            key1 = zalopay.key1

            # Lấy thông tin đơn hàng
            # order = http.request.env['sale.order'].sudo().browse(int(order_id))
            # if not order:
            #     raise ValueError("Không tìm thấy đơn hàng")

            # Tạo dữ liệu cho yêu cầu API
            data = {
                "app_id": app_id,
                "app_trans_id": "{:%y%m%d}_{}".format(datetime.today(), trans_id),
                "app_user": zalopay.app_user,
                "app_time": int(datetime.now().timestamp() * 1000),
                "embed_data": json.dumps({}),
                "item": json.dumps([{
                    "id": str(id),
                    "name": "aaaa",
                    "price": int(1200),
                    "quantity": 1
                }]),
                "amount": str(amount),
                "description": f"Thanh toán cho đơn hàng ",
                "bank_code": "zalopayapp",
                "callback_url": request.httprequest.host_url + '/payment/zalopay/callback',
                
            }

            _logger.info("Dữ liệu cho yêu cầu API: %s", data)

            # Tạo chuỗi để tạo checksum
            data_string = "|".join([
                str(data["app_id"]),  
                data["app_trans_id"],
                data["app_user"],
                str(data["amount"]),
                str(data["app_time"]),
                data["embed_data"],
                data["item"]
            ])
            _logger.info("Chuỗi dữ liệu cho checksum: %s", data_string)
            
            # Tạo checksum
            data["mac"] = hmac.new(key1.encode(), data_string.encode(), hashlib.sha256).hexdigest()

            qr_create_url = "https://sb-openapi.zalopay.vn/v2/create"
            _logger.info("URL tạo QR: %s", qr_create_url)

            data_json = json.dumps(data)
            _logger.info("Dữ liệu JSON cho yêu cầu POST: %s", data_json)

            # Gửi yêu cầu POST đến URL tạo QR của ZaloPay
            response = pyreq.post(
                qr_create_url,
                data=data_json,
                headers={"Content-Type": "application/json"},
            )

            _logger.info("Mã trạng thái phản hồi: %d", response.status_code)
            _logger.info("Nội dung phản hồi: %s", response.text)

            response_data = response.json()
            if response.status_code == 200:
                if response_data.get("return_code") == 1:  
                    order_url = response_data.get("order_url")
                    if order_url:
                        _logger.info("URL đơn hàng: %s", order_url)
                        qr = qrcode.QRCode(version=1, box_size=10, border=5)

                        qr.add_data(order_url)
                        qr.make(fit=True)

                        img = qr.make_image(fill='black', back_color='white')
                        buffer = BytesIO()
                        img.save(buffer, format="PNG")

                        img_bytes = buffer.getvalue()

                        img_base64 = (
                            "data:image/png;base64," + base64.b64encode(img_bytes).decode()
                        )
                        _logger.info("Tạo QR thành công")
                        return img_base64
                    else:
                        _logger.error("Không tìm thấy order_url trong phản hồi của ZaloPay")
                        return {'error': 'Không tìm thấy order_url trong phản hồi của ZaloPay'}
                else:
                    _logger.error("Lỗi từ ZaloPay: %s", response_data.get("return_message"))
                    return {'error': response_data.get("return_message")}
            else:
                _logger.error("Yêu cầu tạo QR thất bại với mã trạng thái: %d", response.status_code)
                return {'error': 'Yêu cầu tạo QR thất bại'}

        except Exception as e:
            _logger.error("Lỗi khi tạo đơn hàng thanh toán ZaloPay: %s", e)
            return {'error': str(e)}