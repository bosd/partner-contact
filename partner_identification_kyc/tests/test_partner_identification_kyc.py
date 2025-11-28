import odoo
from odoo.tests import common


@odoo.tests.tagged("post_install", "-at_install")
class TestPartnerIdentificationKYC(common.TransactionCase):
    def setUp(self):
        super().setUp()

        # Get the KYC category
        self.kyc_category = self.env.ref(
            "partner_identification_kyc.kyc_identification_category"
        )

        # Create a test partner
        self.test_partner = self.env["res.partner"].create(
            {
                "name": "Test Partner for KYC",
                "email": "test.kyc@example.com",
            }
        )

        # Create a test issuer
        self.test_issuer = self.env["res.partner"].create(
            {
                "name": "Test KYC Issuer",
                "is_company": True,
            }
        )

    def test_kyc_category_creation(self):
        """Test that the KYC category was created with correct settings."""
        self.assertEqual(self.kyc_category.name, "KYC")
        self.assertEqual(self.kyc_category.code, "KYC")
        self.assertTrue(self.kyc_category.create_activity_on_new)
        self.assertEqual(self.kyc_category.default_validity_number, 1)
        self.assertEqual(self.kyc_category.default_validity_unit, "years")
        self.assertEqual(self.kyc_category.renewal_lead_number, 2)
        self.assertEqual(self.kyc_category.renewal_lead_unit, "months")

        # Check that activity types are set correctly
        activity_type = self.env.ref(
            "partner_identification_kyc.activity_type_kyc_check"
        )
        self.assertEqual(self.kyc_category.initial_activity_type_id, activity_type)
        self.assertEqual(self.kyc_category.renew_activity_type_id, activity_type)

    def test_action_request_kyc_creates_record(self):
        """Test that the action_request_kyc creates a new KYC identification record."""
        initial_count = self.env["res.partner.id_number"].search_count(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )

        # Call the action
        self.test_partner.action_request_kyc()

        # Check that a new record was created
        final_count = self.env["res.partner.id_number"].search_count(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )

        self.assertEqual(final_count, initial_count + 1)

        # Get the newly created record
        new_record = self.env["res.partner.id_number"].search(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
            ],
            order="create_date desc",
            limit=1,
        )

        self.assertEqual(new_record.status, "draft")
        self.assertTrue(new_record.name.startswith("KYC-"))

    def test_action_request_kyc_duplicate_prevention(self):
        """Test that action_request_kyc prevents duplicates when a 'draft' record
        already exists."""
        # Create the first KYC record
        self.test_partner.action_request_kyc()

        # Verify the first record exists
        records = self.env["res.partner.id_number"].search(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
                ("status", "=", "draft"),
            ]
        )
        self.assertEqual(len(records), 1)

        # Try to create another record - should raise an error
        with self.assertRaises(odoo.exceptions.UserError):
            self.test_partner.action_request_kyc()

    def test_ensure_kyc_record_creates_when_none_exists(self):
        """Test that ensure_kyc_record creates a record when none exists."""
        initial_count = self.env["res.partner.id_number"].search_count(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )

        # Call the API function
        self.test_partner.ensure_kyc_record()

        # Check that a new record was created
        final_count = self.env["res.partner.id_number"].search_count(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )

        self.assertEqual(final_count, initial_count + 1)

        # Verify the status is 'draft'
        new_record = self.env["res.partner.id_number"].search(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
            ],
            order="create_date desc",
            limit=1,
        )

        self.assertEqual(new_record.status, "draft")

    def test_ensure_kyc_record_no_duplicate_when_active_exists(self):
        """Test that ensure_kyc_record does not create a record when an active one
        already exists."""
        # Create the first record with 'draft' status (active)
        self.test_partner.ensure_kyc_record()

        # Get the initial record
        initial_records = self.env["res.partner.id_number"].search(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )

        self.assertEqual(len(initial_records), 1)

        # Call the API function again
        self.test_partner.ensure_kyc_record()

        # Verify that no duplicate was created (still has only 1 active record)
        final_records = self.env["res.partner.id_number"].search(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )

        self.assertEqual(len(final_records), 1)

    def test_ensure_kyc_record_creates_when_expired_exists(self):
        """Test that ensure_kyc_record creates a record when only expired records
        exist."""
        # Create an expired record
        identification_model = self.env["res.partner.id_number"]
        identification_model.create(
            {
                "partner_id": self.test_partner.id,
                "category_id": self.kyc_category.id,
                "name": "KYC-EXPIRED-TEST",
                "status": "close",
            }
        )

        initial_count = self.env["res.partner.id_number"].search_count(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )
        self.assertEqual(initial_count, 1)

        # Call the API function - should create a new record since existing one is
        # expired
        self.test_partner.ensure_kyc_record()

        # Verify that a new record was created (now has 2 records total)
        final_count = self.env["res.partner.id_number"].search_count(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )

        self.assertEqual(final_count, 2)

    def test_ensure_kyc_record_multiple_scenarios(self):
        """Test ensure_kyc_record with different status scenarios."""
        test_partner_multi = self.env["res.partner"].create(
            {
                "name": "Test Partner Multi",
                "email": "test.multi@example.com",
            }
        )

        identification_model = self.env["res.partner.id_number"]

        # Scenario 1: Add a 'close' record, then ensure_kyc_record should create new one
        identification_model.create(
            {
                "partner_id": test_partner_multi.id,
                "category_id": self.kyc_category.id,
                "name": "KYC-CLOSE-TEST",
                "status": "close",
            }
        )

        initial_count = self.env["res.partner.id_number"].search_count(
            [
                ("partner_id", "=", test_partner_multi.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )
        self.assertEqual(initial_count, 1)

        test_partner_multi.ensure_kyc_record()  # Should create new record
        count_after_ensure = self.env["res.partner.id_number"].search_count(
            [
                ("partner_id", "=", test_partner_multi.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )
        self.assertEqual(count_after_ensure, 2)

        # Scenario 2: Add an 'open' record, then ensure_kyc_record should NOT create
        # new one
        test_partner_multi2 = self.env["res.partner"].create(
            {
                "name": "Test Partner Multi 2",
                "email": "test.multi2@example.com",
            }
        )

        identification_model.create(
            {
                "partner_id": test_partner_multi2.id,
                "category_id": self.kyc_category.id,
                "name": "KYC-OPEN-TEST",
                "status": "open",
            }
        )

        initial_count2 = self.env["res.partner.id_number"].search_count(
            [
                ("partner_id", "=", test_partner_multi2.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )
        self.assertEqual(initial_count2, 1)

        test_partner_multi2.ensure_kyc_record()  # Should NOT create new record
        count_after_ensure2 = self.env["res.partner.id_number"].search_count(
            [
                ("partner_id", "=", test_partner_multi2.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )
        self.assertEqual(count_after_ensure2, 1)

    def test_button_visibility_conditions(self):
        """Test the visibility conditions for the Request KYC button."""
        # Initially, no KYC records exist, so button should be visible
        # (This is tested indirectly by testing the functions that implement the logic)

        # Create a 'draft' status record
        self.test_partner.action_request_kyc()

        # Now the button should be hidden (tested by trying to call the function
        # and expect error)
        with self.assertRaises(odoo.exceptions.UserError):
            self.test_partner.action_request_kyc()

        # Create a running status record with a different partner for testing
        partner2 = self.env["res.partner"].create(
            {
                "name": "Test Partner 2 for KYC",
                "email": "test2.kyc@example.com",
            }
        )

        identification_model = self.env["res.partner.id_number"]
        identification_model.create(
            {
                "partner_id": partner2.id,
                "category_id": self.kyc_category.id,
                "name": "KYC-RUNNING-TEST",
                "status": "open",
            }
        )

        # With a running status, the button should be hidden
        with self.assertRaises(odoo.exceptions.UserError):
            partner2.action_request_kyc()

    def test_button_visibility_computed_field(self):
        """Test the computed field show_kyc_button for different scenarios."""
        # Initially, no KYC records - button should be visible (show_kyc_button = True)
        self.assertTrue(self.test_partner.show_kyc_button)

        # Create a draft status record - button should be hidden
        self.test_partner.action_request_kyc()
        # Reload the partner to get the updated computed field
        self.test_partner.invalidate_recordset()
        partner_reloaded = self.test_partner.browse(self.test_partner.id)
        self.assertFalse(partner_reloaded.show_kyc_button)

        # Create a new partner with pending status - button should be hidden
        partner_pending = self.env["res.partner"].create(
            {
                "name": "Test Partner Pending",
                "email": "test.pending@example.com",
            }
        )
        identification_model = self.env["res.partner.id_number"]
        identification_model.create(
            {
                "partner_id": partner_pending.id,
                "category_id": self.kyc_category.id,
                "name": "KYC-PENDING-TEST",
                "status": "pending",
            }
        )
        partner_pending.invalidate_recordset()
        partner_pending_reloaded = partner_pending.browse(partner_pending.id)
        self.assertFalse(partner_pending_reloaded.show_kyc_button)

        # Create a new partner with close status - button should be visible
        partner_close = self.env["res.partner"].create(
            {
                "name": "Test Partner Close",
                "email": "test.close@example.com",
            }
        )
        identification_model.create(
            {
                "partner_id": partner_close.id,
                "category_id": self.kyc_category.id,
                "name": "KYC-CLOSE-TEST",
                "status": "close",
            }
        )
        partner_close.invalidate_recordset()
        partner_close_reloaded = partner_close.browse(partner_close.id)
        self.assertTrue(partner_close_reloaded.show_kyc_button)

    def test_action_request_kyc_ensure_single_record(self):
        """Test that action_request_kyc works correctly with single record."""
        # Test that the method properly calls ensure_one()
        partners = self.test_partner | self.env["res.partner"].create(
            {
                "name": "Another Test Partner",
                "email": "another.test@example.com",
            }
        )

        # Calling the action on multiple records should raise an error
        with self.assertRaises(ValueError):
            partners.action_request_kyc()

    def test_ensure_kyc_record_idempotency(self):
        """Test that ensure_kyc_record is idempotent when record exists."""
        # Call ensure_kyc_record multiple times - should not create duplicates
        initial_count = self.env["res.partner.id_number"].search_count(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )

        # First call - creates the record
        self.test_partner.ensure_kyc_record()

        # Second call - should not create a duplicate
        self.test_partner.ensure_kyc_record()

        final_count = self.env["res.partner.id_number"].search_count(
            [
                ("partner_id", "=", self.test_partner.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        )

        # Should have created only one record
        self.assertEqual(final_count, initial_count + 1)

    def test_multiple_status_scenarios_for_button_visibility(self):
        """Test all possible status combinations for button visibility."""
        # Create a new partner to test various scenarios
        test_partner_3 = self.env["res.partner"].create(
            {
                "name": "Test Partner 3",
                "email": "test3@example.com",
            }
        )

        # Initially, with no records, button should be visible
        self.assertTrue(test_partner_3.show_kyc_button)

        # Test each status combination

        # Test with 'open' (Running) status only - button should be hidden
        identification_model = self.env["res.partner.id_number"]
        identification_model.create(
            {
                "partner_id": test_partner_3.id,
                "category_id": self.kyc_category.id,
                "name": "KYC-OPEN-TEST",
                "status": "open",
            }
        )
        test_partner_3.invalidate_recordset()
        reloaded_partner = test_partner_3.browse(test_partner_3.id)
        self.assertFalse(reloaded_partner.show_kyc_button)

        # Clean up for next test
        identification_model.search(
            [
                ("partner_id", "=", test_partner_3.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        ).unlink()

        # Test with 'pending' (To Renew) status only - button should be hidden
        identification_model.create(
            {
                "partner_id": test_partner_3.id,
                "category_id": self.kyc_category.id,
                "name": "KYC-PENDING-TEST",
                "status": "pending",
            }
        )
        test_partner_3.invalidate_recordset()
        reloaded_partner = test_partner_3.browse(test_partner_3.id)
        self.assertFalse(reloaded_partner.show_kyc_button)

        # Clean up for next test
        identification_model.search(
            [
                ("partner_id", "=", test_partner_3.id),
                ("category_id", "=", self.kyc_category.id),
            ]
        ).unlink()

        # Test with 'close' (Expired) status only - button should be visible
        identification_model.create(
            {
                "partner_id": test_partner_3.id,
                "category_id": self.kyc_category.id,
                "name": "KYC-CLOSE-TEST",
                "status": "close",
            }
        )
        test_partner_3.invalidate_recordset()
        reloaded_partner = test_partner_3.browse(test_partner_3.id)
        self.assertTrue(reloaded_partner.show_kyc_button)
