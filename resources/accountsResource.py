from flask_restful import Resource
from flask import request, Response
from pymongo import MongoClient
from datetime import datetime, UTC 
from bson.objectid import ObjectId # Import ObjectId for updating
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO

# ============================================
# MongoDB Configuration
# ============================================

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DATABASE_NAME = "banking"
client = None
db = None

# ============================================
# MongoDB Setup and Helpers
# ============================================

def _get_statement_data(account_id):
    db = get_mongo_db()
    account = db.accounts.find_one({"id": account_id})
    if not account:
        return {"message": f"Account with id {account_id} not found"}, 404

    transactions_cursor = db.transactions.find(
        {"account_id": account_id}, 
        {"_id": 0, "account_id": 0}
    ).sort("timestamp", 1)

    transactions = []
    
    # Fetch all transactions to calculate the running balance
    temp_transactions = list(transactions_cursor)
    
    # Calculate total net transactions to find the opening balance
    total_net_transaction_amount = sum(
        t['amount'] if t['type'] == 'deposit' else -t['amount'] 
        for t in temp_transactions
    )
    
    opening_balance = round(account["balance"] - total_net_transaction_amount, 2)
    current_running_balance = opening_balance
    ISO_FORMAT_WITH_TZ = '%Y-%m-%dT%H:%M:%S.%f%z'
    # Iterate forward to calculate and store the running balance for the statement
    for t in temp_transactions:
        if isinstance(t["timestamp"], str):
            t["timestamp"] = datetime.strptime(t["timestamp"], '%Y-%m-%dT%H:%M:%S.%f%z')
        t["timestamp"] = t["timestamp"].isoformat()
        if t['type'] == 'deposit':
            current_running_balance += t['amount']
        else:
            current_running_balance -= t['amount']
        t['running_balance'] = round(current_running_balance, 2)
        transactions.append(t)

    return {
        "account": format_account(account),
        "transactions": transactions,
        "opening_balance": opening_balance
    }, 200

def get_mongo_db():
    global client, db
    if db is None:
        try:
            client = MongoClient(MONGO_URI) 
            db = client[DATABASE_NAME]
            print(f"Connected to MongoDB database: {DATABASE_NAME}")

            # 1. Ensure indexes
            db.accounts.create_index("id", unique=True)
            db.transactions.create_index("account_id")
            
            
            if db.accounts.count_documents({}) == 0:
                print("Initializing database with dummy accounts...")
                db.sequences.insert_one({"_id": "account_id", "sequence_value": 0}) 
                initial_accounts = [
                    # Added 'no_of_months' and 'address' for initial dummy accounts
                    {"name": "Dheekshith B G", "balance": 1000.50, "status": "Active", "no_of_months": 12, "address": "123 Main St, Anytown"}, 
                    {"name": "Ninad Agarwal", "balance": 500.00, "status": "Active", "no_of_months": 6, "address": "456 Oak Ave, Othercity"},
                    {"name": "Mouneesh", "balance": 200.00, "status": "Active", "no_of_months": 24, "address": "789 Pine Ln, Somewhere"},
                    {"name": "Mahith", "balance": 500.00, "status": "Active", "no_of_months": 25, "address": "789 Pine Ln, Somewhere"}
                ]
                
                # Fetch the current sequence value and initialize if not exists
                sequence_doc = db.sequences.find_one_and_update(
                    {'_id': "account_id"}, 
                    {'$inc': {'sequence_value': len(initial_accounts)}},
                    upsert=True, 
                    return_document=True
                )
                start_id = sequence_doc['sequence_value'] - len(initial_accounts)
                
                # Assign IDs and insert
                for i, account in enumerate(initial_accounts):
                    account['id'] = start_id + i + 1
                    db.accounts.insert_one(account)
                    
                print(f"Inserted {len(initial_accounts)} initial accounts.")
            
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            client = None
            db = None
    return db


def get_next_sequence(name):
    """Generates the next sequential ID for accounts."""
    db = get_mongo_db()
    # Atomically increment the sequence value
    sequence_document = db.sequences.find_one_and_update(
        {'_id': name},
        {'$inc': {'sequence_value': 1}},
        return_document=True,
        upsert=True
    )
    return sequence_document['sequence_value']

def format_account(account):
    """Formats a MongoDB account document for API response, ensuring new fields are present."""
    # Remove MongoDB's internal ID
    account.pop('_id', None) 
    # Ensure all required fields exist, defaulting if missing
    account['no_of_months'] = account.get('no_of_months', 0)
    account['address'] = account.get('address', 'N/A')
    
    return account

# ============================================
# Resources
# ============================================

# 1. CREATE
class CreateAccountResource(Resource):
    """POST /accounts"""
    def post(self):
        db = get_mongo_db()
        data = request.json
        
        # Validation
        if 'name' not in data or 'balance' not in data:
            return {'message': 'Missing required fields: name and balance'}, 400
        
        try:
            balance = float(data['balance'])
            if balance < 0:
                return {'message': 'Balance cannot be negative'}, 400
        except ValueError:
            return {'message': 'Invalid balance format'}, 400

        # Assign default values for new fields if not provided, and validate
        no_of_months = data.get('no_of_months', 0)
        address = data.get('address', 'Address not specified')
        
        if not isinstance(no_of_months, int) or no_of_months < 0:
             return {'message': 'no_of_months must be a non-negative integer'}, 400

        # Get next sequential ID
        account_id = get_next_sequence("account_id")
        
        # New account document
        initial_data = {
            "id": account_id,
            "name": data['name'],
            "balance": balance,
            "status": "Active", # Default status
            "no_of_months": no_of_months, # New field
            "address": address, # New field
            "created_at": datetime.now(UTC).isoformat()
        }
        
        db.accounts.insert_one(initial_data)
        
        # Respond with the created account data
        return format_account(initial_data), 201

# 2. READ (All)
class GetAccountsResource(Resource):
    """GET /accounts"""
    def get(self):
        db = get_mongo_db()
        accounts = list(db.accounts.find())
        return [format_account(account) for account in accounts], 200

# 3. READ (Single)
class GetSingleAccountResource(Resource):
    """GET /accounts/<id>"""
    def get(self, id):
        db = get_mongo_db()
        account = db.accounts.find_one({"id": id})
        if account:
            return format_account(account), 200
        return {'message': f'Account with id {id} not found'}, 404

# 4. UPDATE
class UpdateAccountResource(Resource):
    """PUT /accounts/<id>"""
    def put(self, id):
        db = get_mongo_db()
        data = request.json
        
        update_fields = {}
        
        # Allow updating name
        if 'name' in data:
            if not data['name']:
                return {'message': 'Name cannot be empty'}, 400
            update_fields['name'] = data['name']
        
        # Allow updating no_of_months (new field)
        if 'no_of_months' in data:
            no_of_months = data['no_of_months']
            if not isinstance(no_of_months, int) or no_of_months < 0:
                return {'message': 'no_of_months must be a non-negative integer'}, 400
            update_fields['no_of_months'] = no_of_months
            
        # Allow updating address (new field)
        if 'address' in data:
            if not data['address']:
                return {'message': 'Address cannot be empty'}, 400
            update_fields['address'] = data['address']
            
        if not update_fields:
            return {'message': 'No valid fields provided for update (valid fields: name, no_of_months, address)'}, 400

        # Atomically update the account
        result = db.accounts.find_one_and_update(
            {"id": id},
            {"$set": update_fields},
            return_document=True
        )
        
        if result:
            return format_account(result), 200
        
        return {'message': f'Account with id {id} not found'}, 404

# 5. DELETE
class DeleteAccountResource(Resource):
    """DELETE /accounts/<id>"""
    def delete(self, id):
        db = get_mongo_db()
        
        account = db.accounts.find_one({"id": id})
        if not account:
            return {'message': f'Account with id {id} not found'}, 404

        # Business Requirement: Balance must be zero to delete
        if account.get("balance", 0) != 0:
            return {"message": "Account must have a zero balance before deletion.", 
                    "current_balance": account["balance"]}, 400
        
        # Delete account and associated transactions
        db.accounts.delete_one({"id": id})
        db.transactions.delete_many({"account_id": id})
        
        return {'message': f'Account with id {id} and all related transactions deleted'}, 200

# ============================================
# Transaction Resources (Deposit/Withdraw/History)
# ============================================

# Utility function for transaction logging
def log_transaction(db, account_id, type, amount):
    """Logs a transaction in the transactions collection."""
    transaction_data = {
        "account_id": account_id,
        "type": type,
        "amount": amount,
        "timestamp": datetime.now(UTC).isoformat()
    }
    db.transactions.insert_one(transaction_data)

# Deposit
class DepositMoneyResource(Resource):
    """POST /accounts/deposit"""
    def post(self):
        db = get_mongo_db()
        data = request.json
        
        if 'id' not in data or 'amount' not in data:
            return {'message': 'Missing required fields: id and amount'}, 400
        
        try:
            account_id = int(data['id'])
            amount = float(data['amount'])
            if amount <= 0:
                return {'message': 'Deposit amount must be positive'}, 400
        except ValueError:
            return {'message': 'Invalid id or amount format'}, 400
            
        # Atomically update the balance and check account status
        result = db.accounts.find_one_and_update(
            {"id": account_id, "status": "Active"}, # Only update Active accounts
            {"$inc": {"balance": amount}},
            return_document=True
        )
        
        if result:
            log_transaction(db, account_id, "Deposit", amount)
            return format_account(result), 200
        
        # Check why update failed (not found or not active)
        account_check = db.accounts.find_one({"id": account_id})
        if not account_check:
            return {'message': f'Account with id {account_id} not found'}, 404
        
        # Account exists but is not Active
        return {'message': f"Cannot deposit to account status: {account_check['status']}"}, 400

# Withdraw
class WithdrawMoneyResource(Resource):
    """POST /accounts/withdraw"""
    def post(self):
        db = get_mongo_db()
        data = request.json
        
        if 'id' not in data or 'amount' not in data:
            return {'message': 'Missing required fields: id and amount'}, 400
            
        try:
            account_id = int(data['id'])
            amount = float(data['amount'])
            if amount <= 0:
                return {'message': 'Withdrawal amount must be positive'}, 400
        except ValueError:
            return {'message': 'Invalid id or amount format'}, 400
            
        # 1. Find the account and check status/balance
        account = db.accounts.find_one({"id": account_id})
        if not account:
            return {'message': f'Account with id {account_id} not found'}, 404
        
        if account.get("status") != "Active":
            return {'message': f"Cannot withdraw from account status: {account['status']}"}, 400
            
        if account.get("balance", 0) < amount:
            return {'message': 'Insufficient balance'}, 400
            
        # 2. Atomically update the balance
        result = db.accounts.find_one_and_update(
            {"id": account_id},
            {"$inc": {"balance": -amount}}, # Subtract amount
            return_document=True
        )
        
        if result:
            log_transaction(db, account_id, "Withdrawal", amount)
            return format_account(result), 200
        
        # Should ideally not be reached if checks above passed, but good for safety
        return {'message': 'Withdrawal failed due to an unknown error'}, 500

# Transaction History
class TransactionHistoryResource(Resource):
    """GET /accounts/<id>/transactions"""
    def get(self, id):
        db = get_mongo_db()
        
        try:
            account_id = int(id)
        except ValueError:
            return {'message': 'Invalid account ID format'}, 400
            
        # Check if account exists
        if not db.accounts.find_one({"id": account_id}):
            return {'message': f'Account with id {account_id} not found'}, 404
            
        transactions = list(db.transactions.find({"account_id": account_id}, {'_id': 0}))
        
        # Sort by timestamp (most recent first)
        transactions.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return transactions, 200

# Block/Close Resources
class BlockAccountResource(Resource):
    """PUT /accounts/block/<id>"""
    def put(self, id):
        db = get_mongo_db()
        
        # Atomically update only if status is Active
        result = db.accounts.find_one_and_update(
            {"id": id, "status": "Active"},
            {"$set": {"status": "Blocked"}},
            return_document=True
        )
        
        if result:
            return format_account(result), 200
        
        # Check if it's not found or already blocked/closed
        account_check = db.accounts.find_one({"id": id})
        if not account_check:
            return {"message": f"Account with id {id} not found"}, 404
            
        # If it reached here, it means the status query filter failed, so it was already Blocked or Closed.
        return {"message": f"Account with id {id} is already {account_check['status']}"}, 200 

# NEW: Resource to close account permanently
class CloseAccountResource(Resource):
    """PUT /accounts/close/<id>"""
    def put(self, id):
        db = get_mongo_db()
        
        account = db.accounts.find_one({"id": id})
        if not account:
            return {"message": f"Account with id {id} not found"}, 404
        
        # Business Requirement: Balance must be zero to close
        # Use .get with a default value of 0.0 to prevent KeyError if balance is somehow missing
        if account.get("balance", 0.0) != 0.0:
            return {"message": "Account must have a zero balance before closing.", 
                    "current_balance": account["balance"]}, 400
        
        # Atomically set the status to Closed
        result = db.accounts.find_one_and_update(
            {"id": id, "status": {"$ne": "Closed"}}, # Only close if not already closed
            {"$set": {"status": "Closed"}},
            return_document=True
        )

        if result:
            return format_account(result), 200
        
        # If update failed, it means the account was already Closed
        return {"message": f"Account with id {id} is already Closed"}, 200 

# NEW: Resource to calculate monthly interest
class MonthlyInterestResource(Resource):
    # Simple Annual Interest Rate (5% per year)
    ANNUAL_RATE = 0.05
    
    def get(self, id):
        db = get_mongo_db()
        
        try:
            account_id = int(id)
        except ValueError:
            return {'message': 'Invalid account ID format'}, 400

        account = db.accounts.find_one({"id": account_id})
        
        if not account:
            return {'message': f'Account with id {account_id} not found'}, 404
        
        # Check Account Status (Business Rule from tests)
        # Interest calculation should fail if the account is 'Closed' or 'Blocked' 
        # (Though we allow 'Blocked' for calculation here, it's safer to only allow 'Active').
        # If the requirement is strictly 'Active' for calculation:
        if account.get("status") != "Active":
            return {'message': f"Cannot calculate interest for closed or inactive account status: {account['status']}"}, 400
        
        balance = account.get("balance", 0.0)
        no_of_months = account.get("no_of_months", 0)
        
        # Check no_of_months (Test: test_calculate_monthly_interest_no_months_configured)
        if no_of_months <= 0:
            return {'message': 'Account is not configured for monthly interest calculation (no_of_months is zero or negative).',
                    'current_balance': round(balance, 2),
                    'no_of_months': no_of_months}, 400

        # Calculation (Simple Interest formula for the time period)
        # Monthly Rate = Annual Rate / 12
        monthly_rate = self.ANNUAL_RATE / 12.0
        
        # Total Interest = Principal * (Monthly Rate * Number of Months)
        total_interest = balance * (monthly_rate * no_of_months)
        
        # Format for consistency (2 decimal places)
        total_interest = round(total_interest, 2)
        
        return {
            'account_id': account_id,
            'current_balance': round(balance, 2),
            'no_of_months': no_of_months,
            'annual_interest_rate': f"{self.ANNUAL_RATE * 100}%",
            'monthly_interest_rate': round(monthly_rate * 100, 4), # Percentage
            'calculated_interest_amount': total_interest
        }, 200

class AccountStatementJsonResource(Resource):
    def get(self, id):
        data, status = _get_statement_data(id)
        if status != 200:
            return data, status

        account_data = data["account"]
        transactions = data["transactions"]
        opening_balance = data["opening_balance"]
        
        statement = {
            "account_id": account_data["id"],
            "account_holder": account_data["name"],
            "opening_balance": opening_balance,
            "closing_balance": account_data["balance"],
            "statement_date": datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%S%z'),
            "transactions": transactions
        }
        return statement, 200
    
class AccountStatementPdfResource(Resource):
    def get(self, id):
        data, status = _get_statement_data(id)
        if status != 200:
            return data, status
        
        account = data["account"]
        transactions = data["transactions"]
        
        # --- Start ReportLab PDF Generation ---
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        
        # Define coordinates and step for drawing
        X_START = 50
        Y_START = 750
        Y_STEP = 14
        
        # Title and Summary
        c.setFont("Helvetica-Bold", 16)
        c.drawString(X_START, Y_START, "Group 1 Bank")

        c.setFont("Helvetica-Bold", 16)
        c.drawString(X_START, Y_START - Y_STEP * 2, "Account Statement")
        
        c.setFont("Helvetica", 10)
        c.drawString(X_START, Y_START - Y_STEP * 3, f"Account Holder: {account['name']} (ID: {account['id']})")
        c.drawString(X_START, Y_START - Y_STEP * 4, f"Statement Date: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        c.drawString(X_START, Y_START - Y_STEP * 5, f"Opening Balance: ${data['opening_balance']:.2f}")
        c.drawString(X_START, Y_START - Y_STEP * 6, f"Closing Balance: ${account['balance']:.2f}")

        # Transactions Header
        Y_HEADER = Y_START - Y_STEP * 8
        c.setFont("Helvetica-Bold", 10)
        c.drawString(X_START, Y_HEADER, "Date/Time")
        c.drawString(X_START + 150, Y_HEADER, "Type")
        c.drawString(X_START + 250, Y_HEADER, "Amount ($)")
        c.drawString(X_START + 400, Y_HEADER, "Running Balance ($)")
        
        # Draw Separator Line
        c.line(X_START, Y_HEADER - 2, X_START + 500, Y_HEADER - 2)

        # Transactions Data
        y_position = Y_HEADER - Y_STEP * 2
        c.setFont("Helvetica", 9)
        
        for t in transactions:
            # Check for page break
            if y_position < 50:
                c.showPage()
                y_position = 750
                # Redraw header on new page
                c.setFont("Helvetica-Bold", 10)
                c.drawString(X_START, y_position, "Date/Time")
                c.drawString(X_START + 150, y_position, "Type")
                c.drawString(X_START + 250, y_position, "Amount ($)")
                c.drawString(X_START + 400, y_position, "Running Balance ($)")
                c.line(X_START, y_position - 2, X_START + 500, y_position - 2)
                y_position -= Y_STEP * 2
                c.setFont("Helvetica", 9)

            amount_sign = "" if t['type'] == 'deposit' else "-"
            
            c.drawString(X_START, y_position, t['timestamp'])
            c.drawString(X_START + 150, y_position, t['type'].capitalize())
            c.drawString(X_START + 250, y_position, f"{amount_sign}{t['amount']:.2f}")
            c.drawString(X_START + 400, y_position, f"{t['running_balance']:.2f}")
            
            y_position -= Y_STEP

        c.save()

        buffer.seek(0)
        pdf_content = buffer.getvalue()
        
        # --- End ReportLab PDF Generation ---

        return Response(
            pdf_content,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment;filename=statement_{account["id"]}_{datetime.now(UTC).strftime("%Y%m%d")}.pdf',
                'Content-Transfer-Encoding': 'binary'
            }
        )