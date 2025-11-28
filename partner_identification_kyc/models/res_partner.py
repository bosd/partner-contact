from odoo import fields, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Computed field to determine if the KYC button should be visible
    show_kyc_button = fields.Boolean(
        string="Show KYC Button", compute="_compute_show_kyc_button", store=False
    )

    def _compute_show_kyc_button(self):
        """Compute whether to show the KYC request button."""
        kyc_category = self.env.ref(
            "partner_identification_kyc.kyc_identification_category",
            raise_if_not_found=False,
        )
        if not kyc_category:
            for partner in self:
                partner.show_kyc_button = False
            return

        # Find all partners in self that have an ongoing KYC record
        ongoing_kyc_records = self.env["res.partner.id_number"].search(
            [
                ("partner_id", "in", self.ids),
                ("category_id", "=", kyc_category.id),
                ("status", "in", ["draft", "open", "pending"]),
            ]
        )

        ongoing_kyc_partner_ids = {
            record.partner_id.id for record in ongoing_kyc_records
        }

        for partner in self:
            partner.show_kyc_button = partner.id not in ongoing_kyc_partner_ids

    def _create_kyc_record(self, partner):
        """Private helper method to create a new KYC identification record."""
        kyc_category = self.env.ref(
            "partner_identification_kyc.kyc_identification_category"
        )
        identification_model = self.env["res.partner.id_number"]
        sequence_code = (
            self.env["ir.sequence"].next_by_code("kyc.identification") or "001"
        )
        return identification_model.create(
            {
                "partner_id": partner.id,
                "category_id": kyc_category.id,
                "name": f"KYC-{partner.id}-{sequence_code}",
                "status": "draft",
            }
        )

    def action_request_kyc(self):
        """Create a new KYC identification record in the 'draft' status."""
        self.ensure_one()  # Ensure single record operation
        kyc_category = self.env.ref(
            "partner_identification_kyc.kyc_identification_category"
        )

        # Check if there's already any active ('open', 'pending') or 'draft' status
        # KYC record to prevent duplicates
        existing_kyc = self.id_numbers.filtered(
            lambda r: r.category_id == kyc_category
            and r.status in ["draft", "open", "pending"]
        )

        if existing_kyc:
            raise UserError(
                self.env._("A KYC request has already been submitted for this partner.")
            )

        # Create a new identification number record for the KYC category using helper
        # method
        self._create_kyc_record(self)

        # Return action to trigger a refresh of the view
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def ensure_kyc_record(self):
        """
        API function to ensure a KYC record exists for the partner if none currently
        exists.
        If no active KYC identification record exists for a partner (not in 'draft',
        'open', or 'pending' status), this function creates a record in the 'draft'
        status.
        """
        kyc_category = self.env.ref(
            "partner_identification_kyc.kyc_identification_category"
        )

        for partner in self:
            # Check if there's already an active or pending KYC record for this partner
            existing_kyc = partner.id_numbers.filtered(
                lambda r: r.category_id == kyc_category
                and r.status in ["draft", "open", "pending"]
            )

            if not existing_kyc:
                # Create a new identification number record for the KYC category using
                # helper method
                self._create_kyc_record(partner)
