import unittest
import json
import time
from app import app 

class TestBankingAPI(unittest.TestCase):

    # Set up the test client before each test
    def setUp(self):
        """Initializes the test client and sets testing mode."""
        self.app = app.test_client()
        self.app.testing = True

    # --- Utility Function for Setup ---

    def create_test_account_with_transaction(self, name, balance, no_of_months=12, address="Test Address"):
        """
        Creates an account and one deposit transaction for verification.
        Updated to include no_of_months and address.
        """
        # 1. Create a new account
        # The API now automatically sets status: "Active"
        response = self.app.post('/accounts', json={
            'name': name, 
            'balance': balance,
            'no_of_months': no_of_months, # New field
            'address': address            # New field
        })
        self.assertEqual(response.status_code, 201, f"Setup Failed: Account POST returned {response.status_code}")
        account_data = json.loads(response.data)
        account_id = account_data['id']

        # 2. Add a transaction (deposit)
        deposit_response = self.app.post('/accounts/deposit', json={'id': account_id, 'amount': 100.00})
        self.assertEqual(deposit_response.status_code, 200, f"Setup Failed: Deposit POST returned {deposit_response.status_code}")
        
        return account_id

    # =================================================================
    # 1. READ (GET) TESTS
    # =================================================================

    def test_get_all_accounts(self):
        """Tests GET /accounts returns a list of accounts (min 3 from initial seeding)."""
        response = self.app.get('/accounts')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 3) # Assumes initial seeding works

    def test_get_single_account_success(self):
        """Tests GET /accounts/<id> for a valid existing account."""
        # Create a temp account
        temp_id = self.create_test_account_with_transaction("Test Retrieval", 100.00)
        
        response = self.app.get(f'/accounts/{temp_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertEqual(data['id'], temp_id)
        self.assertEqual(data['name'], "Test Retrieval")
        # Balance should be initial (100.00) + deposit (100.00)
        self.assertAlmostEqual(data['balance'], 200.00) 
        
        # Check new fields
        self.assertEqual(data['no_of_months'], 12)
        self.assertEqual(data['address'], "Test Address")

        # Cleanup
        # Need to set balance to zero before delete
        self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': 200.00})
        self.app.delete(f'/accounts/{temp_id}')

    def test_get_single_account_not_found(self):
        """Tests GET /accounts/<id> for a non-existent account."""
        response = self.app.get('/accounts/9999999')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('not found', data['message'])

    # =================================================================
    # 2. CREATE (POST) TESTS
    # =================================================================

    def test_create_account_success_with_new_fields(self):
        """Tests POST /accounts with all required and new optional fields."""
        payload = {
            'name': "New Account", 
            'balance': 500.75,
            'no_of_months': 36,
            'address': "101 Beta Street"
        }
        response = self.app.post('/accounts', json=payload)
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        
        self.assertIn('id', data)
        self.assertEqual(data['name'], "New Account")
        self.assertAlmostEqual(data['balance'], 500.75)
        self.assertEqual(data['status'], 'Active')
        self.assertEqual(data['no_of_months'], 36) # Check new field
        self.assertEqual(data['address'], "101 Beta Street") # Check new field

        # Cleanup
        # Need to set balance to zero before delete
        self.app.post('/accounts/withdraw', json={'id': data['id'], 'amount': 500.75})
        self.app.delete(f'/accounts/{data["id"]}')

    def test_create_account_missing_required_fields(self):
        """Tests POST /accounts failure with missing name or balance."""
        response = self.app.post('/accounts', json={'name': 'Missing Balance'})
        self.assertEqual(response.status_code, 400)
        
    def test_create_account_invalid_no_of_months(self):
        """Tests POST /accounts failure with invalid no_of_months (e.g., negative)."""
        payload = {
            'name': "Bad Account", 
            'balance': 10.00,
            'no_of_months': -5, # Negative is invalid
            'address': "101 Beta Street"
        }
        response = self.app.post('/accounts', json=payload)
        self.assertEqual(response.status_code, 400)
        error_data = json.loads(response.data)
        self.assertIn('non-negative integer', error_data['message'])

    # =================================================================
    # 3. UPDATE (PUT) TESTS
    # =================================================================

    def test_update_account_name_success(self):
        """Tests PUT /accounts/<id> updates the account name."""
        temp_id = self.create_test_account_with_transaction("Old Name", 10.00)
        
        new_name = "Updated Account Name"
        response = self.app.put(f'/accounts/{temp_id}', json={'name': new_name})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['name'], new_name)
        
        # Cleanup
        self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': 110.00})
        self.app.delete(f'/accounts/{temp_id}')

    def test_update_account_new_fields_success(self):
        """Tests PUT /accounts/<id> updates the new fields: no_of_months and address."""
        temp_id = self.create_test_account_with_transaction("Updatable Account", 10.00)
        
        new_months = 48
        new_address = "999 Gamma Road, Sector 4"
        
        response = self.app.put(f'/accounts/{temp_id}', json={
            'no_of_months': new_months,
            'address': new_address
        })
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['no_of_months'], new_months)
        self.assertEqual(data['address'], new_address)
        
        # Verify (ensures the update was persistent)
        verify_response = self.app.get(f'/accounts/{temp_id}')
        verify_data = json.loads(verify_response.data)
        self.assertEqual(verify_data['no_of_months'], new_months)
        self.assertEqual(verify_data['address'], new_address)

        # Cleanup
        self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': 110.00})
        self.app.delete(f'/accounts/{temp_id}')

    def test_update_account_invalid_no_of_months(self):
        """Tests PUT /accounts/<id> prevents updating no_of_months to a negative value."""
        temp_id = self.create_test_account_with_transaction("Updatable Account", 10.00)
        
        response = self.app.put(f'/accounts/{temp_id}', json={'no_of_months': -10})
        self.assertEqual(response.status_code, 400)
        error_data = json.loads(response.data)
        self.assertIn('non-negative integer', error_data['message'])

        # Cleanup
        self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': 110.00})
        self.app.delete(f'/accounts/{temp_id}')

    def test_update_account_not_found(self):
        """Tests PUT /accounts/<id> for a non-existent account."""
        response = self.app.put('/accounts/9999999', json={'name': 'Should Fail'})
        self.assertEqual(response.status_code, 404)

    # =================================================================
    # 4. DELETE (DELETE) TESTS
    # =================================================================

    def test_delete_account_success(self):
        """Tests DELETE /accounts/<id> for an account with zero balance."""
        # 1. Create account
        response = self.app.post('/accounts', json={'name': "Zero Balance Delete", 'balance': 0.00})
        account_data = json.loads(response.data)
        temp_id = account_data['id']

        # 2. Delete
        delete_response = self.app.delete(f'/accounts/{temp_id}')
        self.assertEqual(delete_response.status_code, 200)

        # 3. Verify deletion
        verify_response = self.app.get(f'/accounts/{temp_id}')
        self.assertEqual(verify_response.status_code, 404)

    def test_delete_account_non_zero_balance(self):
        """Tests DELETE /accounts/<id> fails if balance is non-zero."""
        temp_id = self.create_test_account_with_transaction("Non-Zero Delete", 100.00)
        # Note: The utility function adds an initial 100 + a 100 deposit, so balance is 200.00

        delete_response = self.app.delete(f'/accounts/{temp_id}')
        self.assertEqual(delete_response.status_code, 400)
        error_data = json.loads(delete_response.data)
        self.assertIn('must have a zero balance before deletion', error_data['message'])

        # Cleanup (Must still delete since deletion failed)
        self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': 200.00})
        self.app.delete(f'/accounts/{temp_id}')

    # =================================================================
    # 5. TRANSACTION (DEPOSIT/WITHDRAW/HISTORY) TESTS
    # =================================================================

    def test_deposit_success(self):
        """Tests POST /accounts/deposit updates balance and logs transaction."""
        temp_id = self.create_test_account_with_transaction("Test Deposit", 50.00) # Initial 50 + 100 deposit = 150
        
        deposit_amount = 250.00
        response = self.app.post('/accounts/deposit', json={'id': temp_id, 'amount': deposit_amount})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertAlmostEqual(data['balance'], 400.00) # 150 + 250

        # Verify transaction history
        history_response = self.app.get(f'/accounts/{temp_id}/transactions')
        history_data = json.loads(history_response.data)
        # Should have 2 transactions (1 from setup + 1 from this test)
        self.assertEqual(len(history_data), 2) 
        self.assertEqual(history_data[0]['amount'], deposit_amount) 
        self.assertEqual(history_data[0]['type'], "Deposit") 

        # Cleanup
        self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': 400.00})
        self.app.delete(f'/accounts/{temp_id}')

    def test_withdraw_success(self):
        """Tests POST /accounts/withdraw updates balance."""
        temp_id = self.create_test_account_with_transaction("Test Withdraw", 500.00) # Initial 500 + 100 deposit = 600
        
        withdraw_amount = 150.00
        response = self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': withdraw_amount})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertAlmostEqual(data['balance'], 450.00) # 600 - 150

        # Cleanup
        self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': 450.00})
        self.app.delete(f'/accounts/{temp_id}')

    def test_withdraw_insufficient_balance(self):
        """Tests POST /accounts/withdraw fails on insufficient balance."""
        temp_id = self.create_test_account_with_transaction("Test Insufficient", 10.00) # Balance is 110.00
        
        withdraw_amount = 200.00 # Too much
        response = self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': withdraw_amount})
        self.assertEqual(response.status_code, 400)
        error_data = json.loads(response.data)
        self.assertIn('Insufficient balance', error_data['message'])

        # Cleanup
        self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': 110.00})
        self.app.delete(f'/accounts/{temp_id}')

    # =================================================================
    # 6. STATUS (BLOCK/CLOSE) TESTS
    # =================================================================

    def test_close_account_fail_non_zero_balance(self):
        """Tests PUT /accounts/close/<id> fails if balance is non-zero."""
        temp_id = self.create_test_account_with_transaction("Account to Close", 50.00) 

        response = self.app.put(f'/accounts/close/{temp_id}')
        self.assertEqual(response.status_code, 400)

        error_data = json.loads(response.data)
        self.assertIn('must have a zero balance before closing', error_data['message'])

        # Cleanup (must still delete since closure failed)
        self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': 150.00})
        self.app.delete(f'/accounts/{temp_id}')
        
    def test_close_account_success_zero_balance(self):
        """Tests PUT /accounts/close/<id> succeeds if balance is zero."""
        # Create account with initial balance 0
        response = self.app.post('/accounts', json={'name': "Zero Balance Account", 'balance': 0.00})
        account_data = json.loads(response.data)
        temp_id = account_data['id']

        # Try to close
        close_response = self.app.put(f'/accounts/close/{temp_id}')
        self.assertEqual(close_response.status_code, 200)

        closed_data = json.loads(close_response.data)
        self.assertEqual(closed_data['status'], 'Closed')
        
        # Verify closed account cannot transact
        deposit_response = self.app.post('/accounts/deposit', json={'id': temp_id, 'amount': 1.00})
        self.assertEqual(deposit_response.status_code, 400)
        self.assertIn('Cannot deposit to account status: Closed', json.loads(deposit_response.data)['message'])
        
        # Cleanup
        # Since balance is 0, we can delete it now.
        self.app.delete(f'/accounts/{temp_id}')
        
    # =================================================================
    # 7. INTEREST CALCULATION (NEW) TESTS
    # =================================================================

    def test_calculate_monthly_interest_success(self):
        """Tests GET /accounts/interest/<id> returns correct interest calculation."""
        # Setup: Initial Balance: 900.00 + 100.00 deposit = 1000.00 final balance
        # no_of_months: 6
        # Annual Rate: 5% (0.05). Monthly Rate: 0.05 / 12
        # Interest = 1000 * (0.05/12 * 6) = 1000 * 0.025 = 25.00
        
        temp_id = self.create_test_account_with_transaction("Interest Account", 900.00, no_of_months=6) 
        
        response = self.app.get(f'/accounts/interest/{temp_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertEqual(data['account_id'], temp_id)
        self.assertAlmostEqual(data['current_balance'], 1000.00) 
        self.assertEqual(data['no_of_months'], 6)
        
        # Check calculated amount (should be 25.00)
        self.assertAlmostEqual(data['calculated_interest_amount'], 25.00) 
        
        # Cleanup
        self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': 1000.00})
        self.app.delete(f'/accounts/{temp_id}')

    def test_calculate_monthly_interest_account_not_found(self):
        """Tests GET /accounts/interest/<id> fails for non-existent account."""
        response = self.app.get('/accounts/interest/9999999')
        self.assertEqual(response.status_code, 404)
        error_data = json.loads(response.data)
        self.assertIn('not found', error_data['message'])

    def test_calculate_monthly_interest_no_months_configured(self):
        """Tests GET /accounts/interest/<id> fails if no_of_months is 0."""
        # Create an account with 0 months configured
        temp_id = self.create_test_account_with_transaction("Zero Months", 100.00, no_of_months=0) # Balance is 200.00
        
        response = self.app.get(f'/accounts/interest/{temp_id}')
        self.assertEqual(response.status_code, 400)
        error_data = json.loads(response.data)
        self.assertIn('not configured for monthly interest calculation', error_data['message'])

        # Cleanup
        self.app.post('/accounts/withdraw', json={'id': temp_id, 'amount': 200.00})
        self.app.delete(f'/accounts/{temp_id}')