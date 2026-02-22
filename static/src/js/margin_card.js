/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { Component,useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const fieldRegistry = registry.category("fields");

class MarginDashboardPopup extends Component {
    static template = "sale_margin_engine.MarginDashboardPopup";
    static props = ["close", "lines", "overheadType","currency"];
    static components = { Dialog };

    setup() {
        this.expanded = useState({});
    }

    toggleRow(index) {
        this.expanded[index] = !this.expanded[index];
    }

    getLandedCosts(line) {
        return (line.landed_costs || []).map(lc => ({
            label: lc.label,
            amount: lc.estimated_total,
            per_unit: lc.per_unit,
            split_method: lc.split_method,
        }));
    }

    formatCurrency(value) {
        return new Intl.NumberFormat(undefined, {
            style: "currency",
            currency: this.props.currency || "USD",
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(value || 0);
    }

    formatPercent(value) {
        return ((value || 0) * 100).toFixed(2) + " %";
    }

    marginColor(pct) {
        if (pct < 0.1) return "text-danger";
        if (pct < 0.2) return "text-warning";
        return "text-success";
    }
    
    get totals() {
        const lines = this.props.lines;
        const totalRevenue = lines.reduce((s, l) => s + l.unit_price * l.qty, 0);
        const totalMargin = lines.reduce((s, l) => s + l.margin, 0);
        const marginPct = totalRevenue ? totalMargin / totalRevenue : 0;
        return { totalMargin, marginPct };
    }

}

class MarginDashboardWidget extends Component {
    static template = "sale_margin_engine.MarginDashboardWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.dialog = useService("dialog");
        this.orm = useService("orm");
    }

    async openDashboard() {
        const order = this.props.record;
        const lines = (order.data?.order_line?.records || []).map(rec => ({
            product_name: rec.data.product_id?.[1] || "—",
            // product_category: rec.data.product_id?.[1] || "—",
            qty: rec.data.product_uom_qty || 0,
            unit_price: rec.data.price_unit || 0,
            unit_cost: rec.data.cost_snapshot || 0,
            overhead: rec.data.overhead_snapshot || 0,
            margin: rec.data.margin || 0,
            margin_percentage: rec.data.margin_percentage || 0,
            landed_costs: rec.data.landed_cost_breakdown?.landed || [],
            product_category: rec.data.landed_cost_breakdown?.category_name || '—',
            analytic_account: rec.data.landed_cost_breakdown?.analytic_account || '—',
        }));

        const overheadType = order.data?.overhead_type || "None";
        const currencyId = order.data?.currency_id?.[0];
        let currency = "USD";
        if (currencyId) {
            const result = await this.orm.read("res.currency", [currencyId], ["name"]);
            currency = result?.[0]?.name || "USD";
        }
        this.dialog.add(MarginDashboardPopup, {
            close: () => {},
            lines,
            overheadType,
            currency,
        });
    }
}

fieldRegistry.add("margin_dashboard_widget", {
    component: MarginDashboardWidget,
    supportedTypes: ["char"],
});