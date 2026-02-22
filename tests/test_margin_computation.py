from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'margin_engine')
class TestMarginComputation(TransactionCase):
    """
    Unit tests for sale_margin_engine margin computation logic.
    Tests cover: cost snapshot, overhead (fixed & percentage), margin fields.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # --- Analytic account with overhead value ---
        cls.analytic_plan = cls.env['account.analytic.plan'].search([], limit=1)
        if not cls.analytic_plan:
            cls.analytic_plan = cls.env['account.analytic.plan'].create({
                'name': 'Default Plan',
            })

        cls.analytic_account = cls.env['account.analytic.account'].create({
            'name': 'Test Overhead Account',
            'overhead': 50.0,  # 50 AED fixed / 50% depending on test
            'plan_id': cls.analytic_plan.id,
        })

        # --- Product category linked to analytic account ---
        cls.category = cls.env['product.category'].create({
            'name': 'Test Category',
            'analytic_account_id': cls.analytic_account.id,
        })

        # --- Product ---
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'consu',
            'standard_price': 100.0,
            'list_price': 200.0,
            'categ_id': cls.category.id,
        })

        # --- Customer ---
        cls.partner = cls.env['res.partner'].create({'name': 'Test Customer'})

    def _set_overhead_type(self, overhead_type):
        self.env['ir.config_parameter'].sudo().set_param(
            'sale_margin_engine.overhead_type', overhead_type
        )

    def _create_order(self, price_unit, qty):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': qty,
                'price_unit': price_unit,
            })],
        })
        # Trigger all computes
        order.order_line._compute_cost_snapshot()
        order.order_line._compute_overhead_snapshot()
        order.order_line._compute_margin_fields()
        return order

    # ------------------------------------------------------------------ #
    #  1. Cost Snapshot
    # ------------------------------------------------------------------ #

    def test_cost_snapshot_equals_standard_price(self):
        """cost_snapshot should capture product.standard_price at order time."""
        self._set_overhead_type('')
        order = self._create_order(price_unit=200.0, qty=1)
        line = order.order_line[0]
        self.assertAlmostEqual(line.cost_snapshot, 100.0,
                               msg="cost_snapshot should equal standard_price")

    def test_cost_snapshot_frozen_after_confirmation(self):
        """cost_snapshot must NOT update after the order is confirmed."""
        self._set_overhead_type('')
        order = self._create_order(price_unit=200.0, qty=1)
        order.action_confirm()
        line = order.order_line[0]
        original_snapshot = line.cost_snapshot

        # Change standard price AFTER confirmation
        self.product.standard_price = 999.0
        line._compute_cost_snapshot()

        self.assertAlmostEqual(line.cost_snapshot, original_snapshot,
                               msg="cost_snapshot must be frozen after confirmation")

    # ------------------------------------------------------------------ #
    #  2. Overhead — Fixed
    # ------------------------------------------------------------------ #

    def test_overhead_fixed_per_unit(self):
        """Fixed overhead: overhead_snapshot = overhead_value (per unit, not × qty)."""
        self._set_overhead_type('fixed')
        self.analytic_account.overhead = 50.0
        order = self._create_order(price_unit=200.0, qty=3)
        line = order.order_line[0]
        # Fixed overhead is stored per unit in overhead_snapshot
        self.assertAlmostEqual(line.overhead_snapshot, 50.0,
                               msg="Fixed overhead per unit should be 50")

    def test_overhead_fixed_total_overhead(self):
        """total_overhead_snapshot = overhead_snapshot * qty."""
        self._set_overhead_type('fixed')
        self.analytic_account.overhead = 50.0
        order = self._create_order(price_unit=200.0, qty=3)
        line = order.order_line[0]
        self.assertAlmostEqual(line.total_overhead_snapshot, 150.0,
                               msg="Total fixed overhead should be 50 × 3 = 150")

    # ------------------------------------------------------------------ #
    #  3. Overhead — Percentage
    # ------------------------------------------------------------------ #

    def test_overhead_percentage(self):
        """Percentage overhead: overhead_snapshot = cost × (pct/100) × qty."""
        self._set_overhead_type('percentage')
        self.analytic_account.overhead = 10.0  # 10%
        order = self._create_order(price_unit=200.0, qty=2)
        line = order.order_line[0]
        # 100 (cost) × 10% × 2 (qty) = 20
        expected = 100.0 * (10.0 / 100.0) * 2
        self.assertAlmostEqual(line.overhead_snapshot, expected,
                               msg=f"Percentage overhead should be {expected}")

    def test_overhead_zero_when_no_analytic(self):
        """overhead_snapshot should be 0 if category has no analytic account."""
        self._set_overhead_type('fixed')
        category_no_analytic = self.env['product.category'].create({
            'name': 'No Analytic',
        })
        product_no_analytic = self.env['product.product'].create({
            'name': 'Plain Product',
            'standard_price': 100.0,
            'list_price': 200.0,
            'categ_id': category_no_analytic.id,
        })
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': product_no_analytic.id,
                'product_uom_qty': 1,
                'price_unit': 200.0,
            })],
        })
        line = order.order_line[0]
        line._compute_cost_snapshot()
        line._compute_overhead_snapshot()
        self.assertAlmostEqual(line.overhead_snapshot, 0.0,
                               msg="Overhead should be 0 without analytic account")

    def test_overhead_zero_when_type_not_set(self):
        """overhead_snapshot should be 0 if overhead_type config param is empty."""
        self._set_overhead_type('')
        order = self._create_order(price_unit=200.0, qty=2)
        line = order.order_line[0]
        self.assertAlmostEqual(line.overhead_snapshot, 0.0,
                               msg="Overhead should be 0 when type not configured")

    # ------------------------------------------------------------------ #
    #  4. Margin Fields
    # ------------------------------------------------------------------ #

    def test_margin_calculation_fixed_overhead(self):
        """
        margin = subtotal - (cost_snapshot × qty + total_overhead_snapshot)
        With fixed overhead:
          subtotal = 200 × 2 = 400
          total_cost = (100 × 2) + (50 × 2) = 300
          margin = 400 - 300 = 100
        """
        self._set_overhead_type('fixed')
        self.analytic_account.overhead = 50.0
        order = self._create_order(price_unit=200.0, qty=2)
        line = order.order_line[0]
        self.assertAlmostEqual(line.margin, 100.0, places=2,
                               msg="Margin should be 100")

    def test_margin_percentage_calculation(self):
        """margin_percentage = margin / subtotal."""
        self._set_overhead_type('fixed')
        self.analytic_account.overhead = 50.0
        order = self._create_order(price_unit=200.0, qty=2)
        line = order.order_line[0]
        # margin=100, subtotal=400 → 25%
        self.assertAlmostEqual(line.margin_percentage, 0.25, places=4,
                               msg="Margin % should be 0.25 (25%)")

    def test_total_cost_calculation(self):
        """total_cost = total_cost_snapshot + total_overhead_snapshot."""
        self._set_overhead_type('fixed')
        self.analytic_account.overhead = 50.0
        order = self._create_order(price_unit=200.0, qty=2)
        line = order.order_line[0]
        # (100×2) + (50×2) = 300
        self.assertAlmostEqual(line.total_cost, 300.0, places=2,
                               msg="Total cost should be 300")

    def test_negative_margin_when_price_below_cost(self):
        """Margin should be negative when price is below cost + overhead."""
        self._set_overhead_type('fixed')
        self.analytic_account.overhead = 50.0
        order = self._create_order(price_unit=120.0, qty=1)
        line = order.order_line[0]
        # subtotal=120, total_cost=100+50=150 → margin=-30
        self.assertLess(line.margin, 0,
                        msg="Margin should be negative when price < cost + overhead")
        self.assertAlmostEqual(line.margin, -30.0, places=2)

    # ------------------------------------------------------------------ #
    #  5. Order-level Totals
    # ------------------------------------------------------------------ #

    def test_order_total_margin(self):
        """SaleOrder.total_margin = sum of line margins."""
        self._set_overhead_type('fixed')
        self.analytic_account.overhead = 50.0
        order = self._create_order(price_unit=200.0, qty=2)
        order.order_line._compute_cost_snapshot()
        order.order_line._compute_overhead_snapshot()
        order.order_line._compute_margin_fields()
        order._compute_totals()
        self.assertAlmostEqual(order.total_margin, 100.0, places=2,
                               msg="Order total_margin should equal sum of line margins")

    def test_order_margin_percentage(self):
        """SaleOrder.margin_percentage = total_margin / amount_untaxed."""
        self._set_overhead_type('fixed')
        self.analytic_account.overhead = 50.0
        order = self._create_order(price_unit=200.0, qty=2)
        order.order_line._compute_cost_snapshot()
        order.order_line._compute_overhead_snapshot()
        order.order_line._compute_margin_fields()
        order._compute_totals()
        expected = order.total_margin / order.amount_untaxed
        self.assertAlmostEqual(order.margin_percentage, expected, places=4,
                               msg="Order margin_percentage should be total_margin / amount_untaxed")