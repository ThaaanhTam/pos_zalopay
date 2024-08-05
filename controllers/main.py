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

    def _create_transaction(
        self,
        provider_id,
        payment_method_id,
        partner_id,
        token_id,
        amount,
        currency_id,
        flow,
        tokenization_requested,
        landing_route,
        reference_prefix=None,
        is_validation=False,
        custom_create_values=None,
        **kwargs,
    ):
        """Override the original method to create a transaction for the POS VNPay payment method."""
        # Prepare create values
        if flow in ["redirect", "direct"]:  # Direct payment or payment with redirection
            provider_sudo = request.env["payment.provider"].sudo().browse(provider_id)
            token_id = None
            tokenize = bool(
                # Don't tokenize if the user tried to force it through the browser's developer tools
                provider_sudo.allow_tokenization
                # Token is only created if required by the flow or requested by the user
                and (
                    provider_sudo._is_tokenization_required(**kwargs)
                    or tokenization_requested
                )
            )
        elif flow == "token":  # Payment by token
            token_sudo = request.env["payment.token"].sudo().browse(token_id)

            # Prevent from paying with a token that doesn't belong to the current partner (either
            # the current user's partner if logged in, or the partner on behalf of whom the payment
            # is being made).
            partner_sudo = request.env["res.partner"].sudo().browse(partner_id)
            if (
                partner_sudo.commercial_partner_id
                != token_sudo.partner_id.commercial_partner_id
            ):
                raise AccessError(_("You do not have access to this payment token."))

            provider_sudo = token_sudo.provider_id
            payment_method_id = token_sudo.payment_method_id.id
            tokenize = False
        else:
            raise ValidationError(
                _(
                    "The payment should either be direct, with redirection, or made by a token."
                )
            )

        reference = request.env["payment.transaction"]._compute_reference(
            provider_sudo.code,
            prefix=reference_prefix,
            separator="-",
            **(custom_create_values or {}),
            **kwargs,
        )
        if (
            is_validation
        ):  # Providers determine the amount and currency in validation operations
            amount = provider_sudo._get_validation_amount()
            payment_method = request.env["payment.method"].browse(payment_method_id)
            currency_id = (
                provider_sudo.with_context(
                    validation_pm=payment_method  # Will be converted to a kwarg in master.
                )
                ._get_validation_currency()
                .id
            )

        # Create the transaction
        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            .create(
                {
                    "provider_id": provider_sudo.id,
                    "payment_method_id": payment_method_id,
                    "reference": reference,
                    "amount": amount,
                    "currency_id": currency_id,
                    "partner_id": partner_id,
                    "token_id": token_id,
                    "operation": (
                        f"online_{flow}" if not is_validation else "validation"
                    ),
                    "tokenize": tokenize,
                    "landing_route": landing_route,
                    **(custom_create_values or {}),
                }
            )
        )  # In sudo mode to allow writing on callback fields

        if flow == "token":
            tx_sudo._send_payment_request()  # Payments by token process transactions immediately
        else:
            tx_sudo._log_sent_message()

        # Monitor the transaction to make it available in the portal.
        PaymentPostProcessing.monitor_transaction(tx_sudo)

        return tx_sudo

    def _get_partner_sudo(self, user_sudo):
        """Get the partner of the user.
        Args:
            user_sudo: The user record in sudo mode.
        Returns:
            partner_sudo: The partner record in sudo mode.
        """
        partner_sudo = user_sudo.partner_id
        if not partner_sudo and user_sudo._is_public():
            partner_sudo = self.env.ref("base.public_user")
        return partner_sudo

    # Create a new transaction for the POS VNPay payment method
    def create_new_transaction(self, pos_order_sudo, zalopay, order_amount):
        """Create a new transaction with POS VNPay payment method
        Args:
            pos_order_sudo: pos.order record in sudo mode
            vnpay: payment.provider vnpay record
            order_amount: The amount of the order
        Raises:
            AssertionError: If the currency is invalid
        Returns:
            tx_sudo: The created transaction record in sudo mode
        """

        # Get the access token of the POS order
        access_token = pos_order_sudo.access_token

        # Get the VNPay QR payment method
        zalopay_qr_method = (
            request.env["payment.method"]
            .sudo()
            .search([("code", "=", "zalopayqr")], limit=1)
        )

        # Get the user and partner of the user
        user_sudo = request.env.user
        partner_sudo = pos_order_sudo.partner_id or self._get_partner_sudo(user_sudo)

        # Create transaction data
        prefix_kwargs = {
            "pos_order_id": pos_order_sudo.id,
        }
        transaction_data = {
            "provider_id": zalopay.id,
            "payment_method_id": zalopay_qr_method.id,
            "partner_id": partner_sudo.id,
            "partner_phone": partner_sudo.phone,
            "token_id": None,
            "amount": int(order_amount),
            "flow": "direct",
            "tokenization_requested": False,
            "landing_route": "",
            "is_validation": False,
            "access_token": access_token,
            "reference_prefix": request.env["payment.transaction"]
            .sudo()
            ._compute_reference_prefix(
                provider_code="zalopay", separator="-", **prefix_kwargs
            ),
            "custom_create_values": {
                "pos_order_id": pos_order_sudo.id,
                "tokenize": False,
            },
        }

        # Check if the currency is valid
        currency = pos_order_sudo.currency_id
        if not currency.active:
            raise AssertionError(_("The currency is invalid."))
        # Ignore the currency provided by the customer
        transaction_data["currency_id"] = currency.id

        _logger.info(transaction_data)

        # Create a new transaction
        tx_sudo = self._create_transaction(**transaction_data)

        return tx_sudo
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
        app_trans_id = "{:%y%m%d}_{}".format(datetime.today(), trans_id)


        try:
            # Get ZaloPay data
            zalopay = (
                http.request.env["payment.provider"]
                .sudo()
                .search([("code", "=", "zalopay")], limit=1)
            )

            if not zalopay:
                raise ValueError("Không phải nhà cung cấp")

            _logger.info("Đúng nhà cung aaaaaaaaaaaaaaaaaaaap %s", zalopay)
            
            # Get appid from ZaloPay provider and convert to integer
            app_id = int(zalopay.appid)
            key1 = zalopay.key1

            # Create the data for the API request
            data = {
                "app_id": app_id,
                "app_trans_id": app_trans_id,
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

                        _logger.info("Tạo thành công.")
                        
                        # Cập nhật app_trans_id vào bản ghi đã tạo mới nhất
                        latest_order = http.request.env['pos.order'].sudo().search([], order="id desc", limit=1)
                        if latest_order:
                            _logger.info("Đang cập nhật app_trans_id: %s vào pos.order ID: %s", data['app_trans_id'], latest_order.id)
                            update_result = latest_order.sudo().write({'app_trans_id': data['app_trans_id']})
                            _logger.info("Kết quả cập nhật: %s", update_result)

                            if update_result:
                                # Kiểm tra lại bản ghi đã cập nhật
                                updated_order = http.request.env['pos.order'].sudo().search([('id', '=', latest_order.id)], limit=1)
                                if updated_order and updated_order.app_trans_id == data['app_trans_id']:
                                    _logger.info("Đã xác nhận app_trans_id: %s đã được lưu trong pos.order ID: %s.", updated_order.app_trans_id, updated_order.id)
                                else:
                                    _logger.info("Không tìm thấy bản ghi với app_trans_id: %s sau khi cập nhật.", data['app_trans_id'])
                        else:
                            _logger.info("Không tìm thấy bản ghi pos.order để cập nhật.")

                    _logger.info("Đã tạo đơn hàng mới với mã giao dịch: %s", app_trans_id)
                    
                    return img_base64
        except Exception as e:
            _logger.error("Error creating ZaloPay payment order: %s", str(e))
            return {'status': 'error', 'message': str(e)}
        
    def _get_current_session_id(self):
        """Lấy session_id hiện tại. Cần tùy chỉnh tùy thuộc vào cách quản lý session của bạn."""
        # Ví dụ: Lấy session_id của phiên POS đang mở
        session = http.request.env['pos.session'].sudo().search([('state', '=', 'opened')], limit=1)
        return session.id if session else False
          
    @http.route(
        _callback_url,
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def zalopay_callback(self, **post):
        """Xử lý callback từ ZaloPay."""
        result = {}
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
                _logger.info("Không nhận được dữ liệu JSON từ ZaloPay")
                result['return_code'] = -1
                result['return_message'] = 'mac not equal'

            else:
                dataJson = json.loads(data['data'])
                app_trans_id = dataJson['app_trans_id']
                _logger.info("Cập nhật trạng thái đơn hàng = success cho app_trans_id = %s", app_trans_id)
            
                pos_order_sudo = (
                    request.env["pos.order"]
                    .sudo()
                    .search([('app_trans_id', '=', app_trans_id)], limit=1)
                )

                order_amount = pos_order_sudo._get_checked_next_online_payment_amount()


                if not pos_order_sudo:
                    pass                
            
            # Xử lý thanh toán thành công
            if  pos_order_sudo:
                tx_sudo = self.create_new_transaction(pos_order_sudo, zalopay, order_amount)
                tx_sudo._set_done()
                tx_sudo._process_pos_online_payment()             
                _logger.info("Thanh toán đã được lưu thành công.")

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



        # self._save_payment_result(pos_order_sudo, result)
        # Thông báo kết quả cho ZaloPay server
        return result

    def _save_payment_result(self, tx_sudo, result):
        """Lưu kết quả thanh toán vào cơ sở dữ liệu."""
        _logger.info("Đã lưu trạng thái thanh toánz")



        if tx_sudo:
            tx_sudo.write({
                'zalopay_result': json.dumps(result),
                'zalopay_status': 'success' if result['return_code'] == 1 else 'failed'
            })
        else:
            _logger.error("Không thể lưu kết quả thanh toán: Không tìm thấy giao dịch")


            





