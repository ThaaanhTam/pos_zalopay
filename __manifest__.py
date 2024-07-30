# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "POS ZaloPay",
    "version": "1.0",
    "category": "Point of Sale",
    "sequence": 0,
    "summary": "................",
    "description": " ",  # Non-empty string to avoid loading the README file.
    "author": "ThanhTam",
    "depends": ["payment_zalopay", "point_of_sale", "account_payment"],
    "data": [ # Do no change the order
        "data/payment_method_data.xml",
        "views/pos_zalopay_settings.xml",
        "data/pos_payment_method_data.xml",
    ],
    "assets": {
    "point_of_sale.assets": [
        'pos_zalopay/static/src/js/payment_zalopay.js',
    ],
    },
    "installable": True,
    "auto_install": False,
    "application": True,
    "license": "LGPL-3",
}
