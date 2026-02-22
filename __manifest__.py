# -*- coding: utf-8 -*-
{
    "name": "Sale Margin Engine",
    "version": "18.0",
    "category": "Sales",
    "summary": "Computes Sale order margin based on landed cost and overheads",
    "author": 'Mohamed Zarroug',
    "depends": ["base","website","sale_management","stock","analytic"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/product_category_view.xml",
        "views/account_analytic_account_view.xml",
        "views/sale_order_view.xml"
    ],
    "assets": {
        'web.assets_backend': [
            "sale_margin_engine/static/src/js/*.js",
            "sale_margin_engine/static/src/xml/*.xml",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "auto_install": False,
    "application": True
}