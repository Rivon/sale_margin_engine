/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, onWillUnmount } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup();
        if (this.props.resModel !== 'sale.order') return;
        this.busService = useService("bus_service");
        this.notification = useService("notification");
        this.channel = "sale_margin_overhead_changed";

        onWillStart(() => {
            console.log(">>> Adding bus channel:", this.channel);
            this.busService.addChannel(this.channel);
            // Ensure polling starts (usually auto, but safe)
            this.busService.start();
        });

        this.busService.addEventListener("notification", (ev) => {
            const notifications = ev.detail || [];
            for (const notif of notifications) {
                if (notif.channel !== this.channel) continue;
                const payload = notif.payload;
                if (payload?.type === "overhead_updated") {
                    console.log(">>> Overhead update received", payload);

                    this.model.root.load({ resId: this.model.root.resId }).then(() => {
                        this.model.notify();
                        this.notification.add(
                            "Overhead updated – margins refreshed",
                            { type: "info" }
                        );
                    });
                }
            }
        });

        onWillUnmount(() => {
            console.log(">>> Removing bus channel:", this.channel);
            this.busService.deleteChannel(this.channel);
        });
    }
});