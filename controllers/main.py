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
from werkzeug.urls import url_encode
from werkzeug.exceptions import Forbidden

from odoo import http, _, tools
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
from odoo.addons.payment.controllers import portal as payment_portal
from odoo.http import request

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

            _logger.info("Đúng nhà cung wwwwwwwwwwwwwwwwwwppp %s", zalopay)
            
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
                "callback_url": request.httprequest.url_root.replace("http://", "https://") + 'pos/zalopay/callback',

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
                        order = request.env['pos.order'].sudo().search([('app_trans_id', '=', data["app_trans_id"])], limit=1)
                        if order:
                            order.write({'app_trans_id': data["app_trans_id"]})
                        return img_base64

            _logger.error("Không tìm thấy order_url trong phản hồi của ZaloPay")
            return {'error': 'Không tìm thấy order_url trong phản hồi của ZaloPay'}

        except Exception as e:
            _logger.error("Error creating ZaloPay payment order: %s", e)
            return {'error': str(e)}
        




    # @http.route(_callback_url, type='http', auth='public', methods=['POST'], csrf=False)
    # def zalopay_callback(self, **post):
    #     """Handle the callback request from ZaloPay."""
    #     _logger.info(" ZaloPay callbackkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk")

    #     # Get the data from the request
    #     data = request.get_json_data()  
    #     _logger.info("Callback data: %s", data)

    #     try:
    #         # Get the POS order with the app_trans_id
    #         pos_order_sudo = (
    #             request.env["pos.order"]
    #             .sudo()
    #             .search([("id", "=", data.get("app_trans_id"))], limit=1)
    #         )

    #         # Check if the order exists
    #         if not pos_order_sudo:
    #             raise ValidationError(_("Không tìm thấy giao dịch phù hợp với mã tham chiếu."))

    #         # Check if the order has been paid
    #         if pos_order_sudo.state in ("paid", "done", "invoiced"):
    #             _logger.info("Đơn hàng đã được thanh toán. Đang hủy bỏ.")
    #             return json.dumps({"return_code": 2, "return_message": "Đơn hàng đã được thanh toán."})

    #         # Get the ZaloPay provider
    #         zalopay = (
    #             request.env["payment.provider"]
    #             .sudo()
    #             .search([("code", "=", "zalopay")], limit=1)
    #         )

    #         # Verify the callback data
    #         data_string = f"{data['app_id']}|{data['app_trans_id']}|{data['app_user']}|{data['amount']}|{data['app_time']}|{data['embed_data']}|{data['item']}"
    #         mac = hmac.new(zalopay.key2.encode(), data_string.encode(), hashlib.sha256).hexdigest()

    #         if mac != data['mac']:
    #             raise Forbidden(_("Nhận dữ liệu với chữ ký không hợp lệ."))

    #         # Validate the amount
    #         order_amount = pos_order_sudo._get_checked_next_online_payment_amount()
    #         receive_amount = data.get("amount")
    #         if int(receive_amount) != int(order_amount):
    #             raise AssertionError(_("Số tiền không khớp."))

    #         # Create a new transaction
    #         tx_sudo = self.create_new_transaction(pos_order_sudo, zalopay, order_amount)

    #         # Update the transaction "provider_reference" with the zp_trans_id
    #         tx_sudo.provider_reference = data.get("zp_trans_id")

    #         # Check the response code and process the payment
    #         if data.get("status") == 1:  # Assuming 1 means successful payment
    #             _logger.info("Thanh toán được xử lý thành công. Đang lưu.")

    #             # Set the transaction as done and process the payment
    #             tx_sudo._set_done()
    #             tx_sudo._process_pos_online_payment()
    #             _logger.info("Thanh toán đã được lưu thành công.")
    #             return json.dumps({"return_code": 1, "return_message": "Đặt hàng thành công."})
    #         else:
    #             _logger.warning(
    #                 "Nhận dữ liệu với mã phản hồi không hợp lệ: %s. Đặt trạng thái giao dịch thanh toán thành Lỗi.",
    #                 data.get("status"),
    #             )
    #             tx_sudo._set_error(
    #                 "ZaloPay: "
    #                 + _("Nhận dữ liệu với mã phản hồi không hợp lệ: %s", data.get("status"))
    #             )
    #             return json.dumps({"return_code": 2, "return_message": f"Nhận dữ liệu với mã lỗi là: {data.get('status')}"})

    #     except Forbidden:
    #         _logger.warning(
    #             "Lỗi cấm trong quá trình xử lý thông báo. Đang hủy bỏ.",
    #             exc_info=True,
    #         )
    #         return json.dumps({"return_code": 2, "return_message": "Sai thông tin xác thực."})

    #     except AssertionError:
    #         _logger.warning(
    #             "Lỗi khẳng định trong quá trình xử lý thông báo. Đang hủy bỏ.",
    #             exc_info=True,
    #         )
    #         return json.dumps({"return_code": 2, "return_message": "Số tiền không chính xác.", "data": {"amount": f"{int(order_amount)}"}})

    #     except ValidationError:
    #         _logger.warning(
    #             "Lỗi xác thực trong quá trình xử lý thông báo. Đang hủy bỏ.",
    #             exc_info=True,
    #         )
    #         return json.dumps({"return_code": 2, "return_message": "Không tìm thấy Mã đơn hàng trong hệ thống.", "data": {"app_trans_id": data.get("app_trans_id")}})

    #     except Exception as e:
    #         _logger.error(f"Lỗi xử lý dữ liệu callback: {e}")
    #         return json.dumps({"return_code": 2, "return_message": f"Lỗi hệ thống khi xử lý thông tin: {e}"})
            
    @http.route(
        _callback_url,
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def zalopay_callback(self, **kwargs):
        """Xử lý callback từ ZaloPay."""
        
        logging.info("xử lý callbackkkkkkkkkkkkkkkkkkkkkkkkkkkk")

        aa = request.httprequest.get_data()
        data = json.loads(aa)
        _logger.info("Nhận dữ liệu callback từ ZaloPay: %s", data)

        try:
            # Get the POS order with the app_trans_id
            

            # Get the ZaloPay provider
            zalopay = (
                request.env["payment.provider"]
                .sudo()
                .search([("code", "=", "zalopay")], limit=1)
            )

            # Verify the callback data
            # data_string = f"{data['app_id']}|{data['app_trans_id']}|{data['app_user']}|{data['amount']}|{data['app_time']}|{data['embed_data']}|{data['item']}"
            mac = hmac.new(zalopay.key2.encode(), data['data'].encode(), hashlib.sha256).hexdigest()

            if mac != data['mac']:
                raise Forbidden(_("Nhận dữ liệu với chữ ký không hợp lệ."))

            # Nếu MAC hợp lệ, trả về thành công
            _logger.info("MAC hợp lệ. Callback xử lý thành công.")


            pos_order = request.env["pos.order"].sudo().search([("name", "=", data.get("app_trans_id"))], limit=1)


            if not pos_order:
                raise ValidationError(_("Không tìm thấy đơn hàng với mã tham chiếu."))

            # Kiểm tra số tiền
            order_amount = pos_order.amount_total
            received_amount = data.get("amount")
            if int(received_amount) != int(order_amount):
                raise ValidationError(_("Số tiền không khớp."))

            # Tạo giao dịch mới
            transaction = self.create_new_transaction(pos_order, zalopay, order_amount)

            # Cập nhật thông tin giao dịch
            transaction.provider_reference = data.get("zp_trans_id")

            # Xử lý thanh toán thành công
            if data.get("status") == 1:  # Giả sử 1 là thành công
                transaction._set_done()
                transaction._process_pos_online_payment()
                _logger.info("Thanh toán đã được lưu thành công.")
                return json.dumps({"return_code": 1, "return_message": "Đặt hàng thành công."})

            else:
                _logger.warning("Mã phản hồi không hợp lệ: %s", data.get("status"))
                transaction._set_error(f"ZaloPay: Mã lỗi: {data.get('status')}")
                return json.dumps({"return_code": 2, "return_message": f"Nhận dữ liệu với mã lỗi: {data.get('status')}"})

        except Forbidden:
            _logger.warning("Lỗi xác thực trong quá trình xử lý thông báo.")
            return json.dumps({"return_code": 2, "return_message": "Sai thông tin xác thực."})

        except ValidationError as e:
            _logger.warning("Lỗi xác thực trong quá trình xử lý thông báo: %s", e)
            return json.dumps({"return_code": 2, "return_message": str(e)})

        except Exception as e:
            _logger.error("Lỗi xử lý dữ liệu callback: %s", e)
            return json.dumps({"return_code": 2, "return_message": "Lỗi hệ thống khi xử lý thông tin."})



            





