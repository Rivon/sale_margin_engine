from odoo import models,fields

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    overhead = fields.Float()
    overhead_type = fields.Char(compute="_compute_overhead_type")

    def _compute_overhead_type(self):
        for rec in self: 
            rec.overhead_type = self.env['ir.config_parameter'].sudo().get_param('sale_margin_engine.overhead_type') or ""

    def write(self, vals):
        res = super().write(vals)
        if 'overhead' in vals:
            payload = {
                'type': 'overhead_updated',
                'analytic_account_ids': self.ids,
                'overhead_type': self.env['ir.config_parameter'].sudo().get_param('sale_margin_engine.overhead_type', 'None'),
                'message': 'Analytic overhead changed - refresh margins if affected',
            }
            self.env['bus.bus']._sendone(
                'sale_margin_overhead_changed',
                'notification',
                payload
            )
        return res