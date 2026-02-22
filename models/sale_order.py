from odoo import models,fields,api


class SaleOrder(models.Model):
    _inherit = 'sale.order'


    total_cost = fields.Float(compute='_compute_totals', store=True)
    total_margin = fields.Float(compute='_compute_totals', store=True)
    margin_percentage = fields.Float(compute='_compute_totals', store=True)
    overhead_type = fields.Char(compute="_compute_overhead_type")
    margin_dashboard = fields.Char(compute='_compute_margin_dashboard')

    def _compute_margin_dashboard(self):
        for rec in self:
            rec.margin_dashboard = ''

    def _compute_overhead_type(self):
        for rec in self:
            type = self.env['ir.config_parameter'].sudo().get_param('sale_margin_engine.overhead_type') or "" 
            rec.overhead_type = type

    @api.depends('order_line.total_cost', 'order_line.margin')
    def _compute_totals(self):
        for order in self:
            order.total_cost = sum(order.order_line.mapped('total_cost'))
            order.total_margin = sum(order.order_line.mapped('margin'))
            order.margin_percentage = (order.total_margin / order.amount_untaxed if order.amount_untaxed else 0)

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    cost_snapshot = fields.Float(compute='_compute_cost_snapshot', store=True)
    total_cost_snapshot = fields.Float(compute='_compute_cost_snapshot', store=True)
    overhead_snapshot = fields.Float(compute='_compute_overhead_snapshot', store=True)
    total_overhead_snapshot = fields.Float(compute='_compute_overhead_snapshot', store=True)
    total_unit_cost = fields.Float(compute='_compute_margin_fields', store=True)
    total_cost = fields.Float(compute='_compute_margin_fields', store=True)
    margin = fields.Float(compute='_compute_margin_fields', store=True)
    margin_percentage = fields.Float(compute='_compute_margin_fields', store=True)
    landed_cost_breakdown = fields.Json(compute='_compute_landed_cost_breakdown')

    def _compute_landed_cost_breakdown(self):
        for line in self:
            line.landed_cost_breakdown = line._get_landed_cost_breakdown()

    @api.depends('product_id')
    def _compute_cost_snapshot(self):
        for line in self:
            if line.order_id.state in ['sale', 'done']:
                continue  # freeze after confirmation
            line.cost_snapshot = line.product_id.standard_price
            line.total_cost_snapshot = line.cost_snapshot * line.product_uom_qty

    @api.depends('cost_snapshot','product_uom_qty','product_id.categ_id.analytic_account_id.overhead')
    def _compute_overhead_snapshot(self):
        # Read config once
        overhead_type = self.env['ir.config_parameter'].sudo().get_param('sale_margin_engine.overhead_type')
        for line in self:
            line.overhead_snapshot = 0.0

            # Freeze after confirmation
            if line.order_id.state in ['sale', 'done']:
                continue
            if not overhead_type:
                continue
            
            category = line.product_id.categ_id
            analytic = category.analytic_account_id
            
            if not analytic:
                continue
            
            overhead_value = analytic.overhead or 0.0
            # Apply logic
            if overhead_type == 'percentage':
                line.overhead_snapshot = (line.cost_snapshot * (overhead_value / 100.0)) * line.product_uom_qty
            elif overhead_type == 'fixed':
                line.overhead_snapshot = overhead_value # Overhead per unit
            line.total_overhead_snapshot = line.overhead_snapshot * line.product_uom_qty

    @api.depends('price_unit','discount','product_uom_qty','cost_snapshot','overhead_snapshot')
    def _compute_margin_fields(self):
        for line in self:
            if line.order_id.state in ['sale', 'done']:
                continue
            line.total_unit_cost = line.cost_snapshot + line.overhead_snapshot
            subtotal = line.price_subtotal
            total_cost = line.total_cost_snapshot + line.total_overhead_snapshot
            line.total_cost = total_cost
            line.margin = subtotal - total_cost
            line.margin_percentage = ((line.margin / subtotal) if subtotal else 0)


    def _get_landed_cost_breakdown(self):
        """
        Returns landed cost breakdown for this product
        based on the most recent validated landed cost applied to a purchase receipt.
        """
        self.ensure_one()
        product = self.product_id
        category = product.categ_id
        analytic = category.analytic_account_id

        # Find all validated landed costs that include this product
        adj_lines = self.env['stock.valuation.adjustment.lines'].search([
            ('product_id', '=', product.id),
            ('cost_id.state', '=', 'done'),
        ], order='cost_id desc')  # most recent
        if not adj_lines:
            return {
                'landed': [],
                'category_name': category.name or '—',
                'analytic_account': analytic.name if analytic else '—',
            }
        most_recent_lc = adj_lines[0].cost_id
        breakdown = []
        for adj in adj_lines.filtered(lambda a: a.cost_id == most_recent_lc):
            per_unit = (adj.additional_landed_cost / adj.quantity) if adj.quantity else 0
            breakdown.append({
                'label': adj.cost_line_id.name or 'Landed Cost',
                'split_method': adj.cost_line_id.split_method,
                'additional_landed_cost': adj.additional_landed_cost,
                'quantity': adj.quantity,
                'per_unit': per_unit,
                'estimated_total': per_unit * self.product_uom_qty,
            })
        return {
            'landed': breakdown,
            'category_name': category.name or '—',
            'analytic_account': analytic.name if analytic else '—',
        }