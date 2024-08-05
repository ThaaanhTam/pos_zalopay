    /** @odoo-module **/

    import { _t } from "@web/core/l10n/translation";
    import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
    import { patch } from "@web/core/utils/patch";
    import { OnlinePaymentPopup } from "@pos_online_payment/app/utils/online_payment_popup/online_payment_popup";
    import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
    import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
    import { floatIsZero } from "@web/core/utils/numbers";

    // Overide to show QR code using qrCodeData created by get_payment_qr API
    patch(PaymentScreen.prototype, {

      async _isOrderValid(isForceValidate) {
      

        if (!(await super._isOrderValid(...arguments))) {
          return false;
        }

        if (!this.payment_methods_from_config.some((pm) => pm.is_online_payment)) {
          return true;
        }

        if (this.currentOrder.finalized) {
          this.afterOrderValidation(false);
          return false;
        }

        const onlinePaymentLines = this.getRemainingOnlinePaymentLines();
        if (onlinePaymentLines.length > 0) {
          this.currentOrder.date_order = luxon.DateTime.now();
          this.currentOrder.save_to_db();
          this.pos.addOrderToUpdateSet();

          try {
            await this.pos.sendDraftToServer();
          } catch (error) {
            if (error.code == 700 || error.code == 701) {
              this.error = true;
            }

            if ("code" in error) {
              await this._handlePushOrderError(error);
            }
            this.showSaveOrderOnServerErrorPopup();
            return false;
          }

          if (!this.currentOrder.server_id) {
            this.showSaveOrderOnServerErrorPopup();
            return false;
          }

          if (!this.currentOrder.server_id) {
            this.cancelOnlinePayment(this.currentOrder);
            this.popup.add(ErrorPopup, {
              title: _t("Online payment unavailable"),
              body: _t("The QR Code for paying could not be generated."),
            });
            return false;
          }

          let prevOnlinePaymentLine = null;
          let lastOrderServerOPData = null;
          for (const onlinePaymentLine of onlinePaymentLines) {
            const onlinePaymentLineAmount = onlinePaymentLine.get_amount();

            lastOrderServerOPData =
              await this.currentOrder.update_online_payments_data_with_server(
                this.pos.orm,
                onlinePaymentLineAmount
              );

            const qrCodeData = await this.env.services.rpc(
              "/api/zalopay/get_payment_qr",
              {
                amount: onlinePaymentLineAmount,
              },

            );
            
            if (!lastOrderServerOPData || !qrCodeData) {
              this.popup.add(ErrorPopup, {
                title: _t("Online payment unavailable"),
                body: _t(
                  "There is a problem with the server. The order online payment status cannot be retrieved."
                ),
              });
              return false;
            }

              if (!lastOrderServerOPData.is_paid) {
                if (lastOrderServerOPData.modified_payment_lines) {
                  this.cancelOnlinePayment(this.currentOrder);
                  this.showModifiedOnlinePaymentsPopup();
                  return false;
                }
                if (
                  (prevOnlinePaymentLine &&
                    prevOnlinePaymentLine.get_payment_status() !== "done") ||
                  !this.checkRemainingOnlinePaymentLines(
                    lastOrderServerOPData.amount_unpaid
                  )
                ) {
                  this.cancelOnlinePayment(this.currentOrder);
                  return false;
                }

                onlinePaymentLine.set_payment_status("waiting");
                this.currentOrder.select_paymentline(onlinePaymentLine);

                lastOrderServerOPData = await this.showOnlinePaymentQrCode( 
                  qrCodeData,
                  onlinePaymentLineAmount,
                  console.log("aaaaaaaaaaaaaaaaasssssss")
                );
                if (onlinePaymentLine.get_payment_status() === "waiting") {
                  onlinePaymentLine.set_payment_status(undefined);
                }
                prevOnlinePaymentLine = onlinePaymentLine;
              
            }

          }

          if (!lastOrderServerOPData || !lastOrderServerOPData.is_paid) {
            lastOrderServerOPData =
              await this.currentOrder.update_online_payments_data_with_server(
                this.pos.orm,
                0
              );
          }
          if (!lastOrderServerOPData || !lastOrderServerOPData.is_paid) {
            return false;
          }

          await this.afterPaidOrderSavedOnServer(lastOrderServerOPData.paid_order);

        
        

          return false;
        } else if (this.currentOrder.server_id) {
          const orderServerOPData =
            await this.currentOrder.update_online_payments_data_with_server(
              this.pos.orm,
              0
            );

          if (!orderServerOPData) {
            const { confirmed } = await this.popup.add(ConfirmPopup, {
              title: _t("Online payment unavailable"),
              body: _t(
                "There is a problem with the server. The order online payment status cannot be retrieved. Are you sure there is no online payment for this order ?"
              ),
              confirmText: _t("Yes"),
            });
            return confirmed;
          }
          if (orderServerOPData.is_paid) {
            await this.afterPaidOrderSavedOnServer(orderServerOPData.paid_order);

         
          

            return false;
          }
          if (orderServerOPData.modified_payment_lines) {
            this.showModifiedOnlinePaymentsPopup();
            return false;
          }

         
  
        }

        const a = await this.env.services.rpc(
          "/pos/zalopay/callback",
        );
        if (a)
          console.log("lấy được callback")

        return true;

       
      },

      
      hideOnlinePaymentPopup() {
        console.log("gọi hàm ẩn")
        const popup = document.querySelector("#online-paymnet-popup"); // Sửa lại selector nếu cần
        if (popup) {
          popup.style.display = 'none';
          console.log("QR Code popup hidden.");
        }
      }
    });
