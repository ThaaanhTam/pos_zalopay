import logging
import json
import hmac
import hashlib
import urllib.parse
from datetime import datetime
from time import time
import random
from odoo import _, api, fields, models
from odoo.http import request
from werkzeug import urls

_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"
    logging.info("Bắt đầu tạo đơn hàng")
    app_trans_id = fields.Char(string="App Transaction ID")

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != "zalopay":
            return res

        base_url = self.provider_id.get_base_url()
        int_amount = int(self.amount)
        
        # Create transaction ID and current time
        trans_id = random.randrange(1000000)
        app_time = int(round(time() * 1000))  # Current time in milliseconds

        # Prepare order items
        order_items = []
        for line in self.invoice_ids.mapped('invoice_line_ids'):
            item = {
                "id": line.id,
                "name": line.name,
                "price": int(line.price_unit * 100)  # Price in cents
            }
            order_items.append(item)

        # Create order data
        order = {
            "app_id": self.provider_id.appid,
            "app_trans_id": "{:%y%m%d}_{}".format(datetime.today(), trans_id),
            "app_user": self.provider_id.app_user,
            "app_time": app_time,
            "embed_data": json.dumps({"redirecturl": urls.url_join(base_url, '/payment/zalopay/return')}),
            "item": json.dumps(order_items),
            "amount": int_amount,
            "description": f"Transaction #{trans_id}",
            "bank_code": "zalopayapp",
            "callback_url": urls.url_join(base_url, '/payment/zalopay/callback'),
        }

        # Create signature (mac)
        data = "{}|{}|{}|{}|{}|{}|{}".format(
            order["app_id"], order["app_trans_id"], order["app_user"],
            order["amount"], order["app_time"], order["embed_data"], order["item"]
        )
        order["mac"] = hmac.new(self.provider_id.key1.encode(), data.encode(), hashlib.sha256).hexdigest()

        # Send request to ZaloPay
        try:
            response = urllib.request.urlopen(url="https://sb-openapi.zalopay.vn/v2/create", data=urllib.parse.urlencode(order).encode())
            result = json.loads(response.read())
            _logger.info("Order created successfully: %s", result)
            
            # Update app_trans_id field
            self.write({'app_trans_id': order['app_trans_id']})
            
        except Exception as e:
            _logger.error("ZaloPay create order failed: %s", e)
            raise ValidationError(_("Order creation failed: %s") % e)

        # Return rendering values
        rendering_values = {
            "api_url": result.get("order_url"),
        }

        return rendering_values

    @api.model
    def create(self, vals):
        transaction = super(PaymentTransaction, self).create(vals)
        if transaction.provider_code == "zalopay":
            # Generate order details for ZaloPay
            transaction._get_specific_rendering_values({})
        return transaction
