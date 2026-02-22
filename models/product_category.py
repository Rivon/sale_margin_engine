from odoo import models,fields, api

class ProductCategory(models.Model):
    _inherit = 'product.category'

    analytic_account_id = fields.Many2one('account.analytic.account', index=True)
