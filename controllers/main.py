import hmac
import hashlib
import logging
import requests as pyreq
from odoo.http import request
import json
import random
from io import BytesIO
from datetime import datetime
import base64
import qrcode
from odoo import http

_logger = logging.getLogger(__name__)

class ZaloPayController(http.Controller):

    _create_qr_url = "/api/zalopay/get_payment_qr"
    _callback_url = "/pos/zalopay/callback"

    @http.route(
            _create_qr_url,
            type='json',
            auth='public',
            methods=['POST'],
            csrf=False)
    def get_payment_qr(self, amount):
        """Create a ZaloPay payment order and return the response."""
        _logger.info("Creating ZaloPay payment order.")
        trans_id = random.randrange(1000000)

        try:
            # Get ZaloPay data
            zalopay = (
                http.request.env["payment.provider"]
                .sudo()
                .search([("code", "=", "zalopay")], limit=1)
            )

            if not zalopay:
                raise ValueError("Không phải nhà cung cấp")

            _logger.info("Đúng nhà cung cấp %s", zalopay)
            
            # Get appid from ZaloPay provider and convert to integer
            app_id = int(zalopay.appid)
            key1 = zalopay.key1

            # Create the data for the API request
            data = {
                "app_id": app_id,
                "app_trans_id": "{:%y%m%d}_{}".format(datetime.today(), trans_id),
                "app_user": zalopay.app_user,  # You might want to get this from `zalopay` too
                "app_time": int(datetime.now().timestamp() * 1000),
                "embed_data": json.dumps({}),
                "item": json.dumps([{}]),
                "amount": amount,  # Example amount in VND
                "description": "Payment for order",
                "bank_code": "zalopayapp",
                "callback_url": request.httprequest.url_root + '/pos/zalopay/callback',

            }

            _logger.info("Data for API request: %s", data)

            # Create a string from the data to create the checksum
            data_string = "|".join([
                str(data["app_id"]),
                data["app_trans_id"],
                data["app_user"],
                str(data["amount"]),
                str(data["app_time"]),
                data["embed_data"],
                data["item"]
            ])
            _logger.info("Data string for checksum: %s", data_string)

            data["mac"] = hmac.new(key1.encode(), data_string.encode(), hashlib.sha256).hexdigest()

            # Add the checksum to the data
            qr_create_url = "https://sb-openapi.zalopay.vn/v2/create"
            _logger.info("QR create URL: %s", qr_create_url)

            data_json = json.dumps(data)
            _logger.info("Data JSON for POST request: %s", data_json)

            # Send a POST request to the ZaloPay create QR URL
            response = pyreq.post(
                qr_create_url,
                data=data_json,
                headers={"Content-Type": "application/json"},
            )

            _logger.info("Response status code: %d", response.status_code)
            _logger.info("Response body: %s", response.text)

            response_data = response.json()
            if response.status_code == 200:
                if response_data.get("return_code") == 1:  # Assuming 1 means success, adjust if needed
                    order_url = response_data.get("order_url")
                    if order_url:
                        _logger.info("Order URL: %s", order_url)
                        qr = qrcode.QRCode(version=1, box_size=10, border=5)

                        qr.add_data(order_url)
                        qr.make(fit=True)

                        img = qr.make_image(fill='black', back_color='white')
                        buffer = BytesIO()
                        img.save(buffer, format="PNG")

                        # Get the content of the BytesIO object as bytes
                        img_bytes = buffer.getvalue()

                        # Convert the bytes to a base64 string
                        img_base64 = (
                            "data:image/png;base64," + base64.b64encode(img_bytes).decode()
                        )
                        _logger.info("Tạo thành cônggggggg")
                        return img_base64

            _logger.error("Không tìm thấy order_url trong phản hồi của ZaloPay")
            return {'error': 'Không tìm thấy order_url trong phản hồi của ZaloPay'}

        except Exception as e:
            _logger.error("Error creating ZaloPay payment order: %s", e)
            return {'error': str(e)}
        



    @http.route(
    _callback_url,
    type="json",
    auth="public",
    methods=["POST"],
    csrf=False,
    )
    def zalopay_callback(self):
        """Xử lý callback từ ZaloPay."""
        result = {}
        logging.info("xử lý callback")
        try:
            raw_data = request.httprequest.get_data()
            cbdata = json.loads(raw_data)
            _logger.info("Dữ liệu callback nhận được: ")
            _logger.info("Dữ liệu callback nhận được: %s", cbdata)
            _logger.info(cbdata)

            zalopay_provider = request.env['payment.provider'].sudo().search([('code', '=', 'zalopay')], limit=1)
            key2 = zalopay_provider.key2

            mac = hmac.new(key2.encode(), cbdata['data'].encode(), hashlib.sha256).hexdigest()

            # Kiểm tra callback hợp lệ (đến từ ZaloPay server)
            if mac != cbdata['mac']:
                # Callback không hợp lệ
                _logger.info("Không nhận được dữ liệu JSON từ ZaloPay")
                result['return_code'] = -1
                result['return_message'] = 'mac not equal'
            else:
                # Thanh toán thành công
                # Cập nhật trạng thái cho đơn hàng
                dataJson = json.loads(cbdata['data'])
                app_trans_id = dataJson['app_trans_id']
                _logger.info("Cập nhật trạng thái đơn hàng = success cho app_trans_id = %s", app_trans_id)
              
              
                all_transactions = request.env['payment.transaction'].sudo().search([])
                for tx in all_transactions:
                    _logger.info("Giao dịch hiện có: %s với app_trans_id: %s", tx.id, tx.app_trans_id)
                 # Tìm giao dịch tương ứng với app_trans_id
                tx = request.env['payment.transaction'].sudo().search([('app_trans_id', '=', app_trans_id)], limit=1)
                if tx:
                    tx._set_done()
                    tx._reconcile_after_done()
                    _logger.info("Đã cập nhật trạng thái đơn hàng thành công cho app_trans_id = %s", app_trans_id)
                    result['return_code'] = 1
                    result['return_message'] = 'success'
                else:
                    _logger.warning("Không tìm thấy giao dịch với app_trans_id = %s", app_trans_id)
                    result['return_code'] = -1
                    result['return_message'] = 'Transaction not found'
        except Exception as e:
            _logger.error("Xử lý callback ZaloPay thất bại: %s", e)
            result['return_code'] = 0  # ZaloPay server sẽ callback lại (tối đa 3 lần)
            result['return_message'] = str(e)
        _logger.info("Kết thúc xử lý callback ZaloPay với kết quả: %s", result)
        # Thông báo kết quả cho ZaloPay server
        return result
    

    
