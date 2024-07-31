# import logging
# from odoo import models, api

# _logger = logging.getLogger(__name__)

# class PosOrder(models.Model):
#     _inherit = "pos.order"

#     @api.model
#     def action_create_order_and_log(self, pos_order_id):
#         # Lấy thông tin đơn hàng từ POS
#         pos_order = self.browse(pos_order_id)
#         if not pos_order:
#             return
        
#         # Tạo đơn hàng mới (tùy chỉnh theo nhu cầu)
#         new_order = self.create({
#             'partner_id': pos_order.partner_id.id,
#             'amount_total': pos_order.amount_total,
#             'date_order': pos_order.date_order,
#             # Thêm các trường khác nếu cần
#         })

#         _logger.info(f"Đơn hàng mới được tạo: {new_order.name}")
        
#         return new_order
