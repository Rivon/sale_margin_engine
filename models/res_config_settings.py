from odoo import models,fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    overhead_type = fields.Selection([('fixed', 'Fixed Cost'),('percentage', 'Percentage of Landed Cost')])


    def get_values(self):
        res = super().get_values()
        res['overhead_type'] = self.env['ir.config_parameter'].sudo().get_param('sale_margin_engine.overhead_type')
        return res

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param('sale_margin_engine.overhead_type', self.overhead_type)
