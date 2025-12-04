from flask import Flask, jsonify, redirect
from flask_restful import Api, MethodNotAllowed, NotFound
from flask_cors import CORS
import os
from resources.accountsResource import (
    CreateAccountResource, 
    GetAccountsResource, 
    GetSingleAccountResource, 
    UpdateAccountResource, 
    DeleteAccountResource,
    DepositMoneyResource,
    WithdrawMoneyResource,
    TransactionHistoryResource,
    AccountStatementJsonResource,
    AccountStatementPdfResource,
    MonthlyInterestResource,
    CloseAccountResource,
    BlockAccountResource
)

# ============================================
# Configuration (Defined here, not from common.py)
# ============================================
DOMAIN = os.environ.get("FLASK_DOMAIN", "127.0.0.1")
PORT = int(os.environ.get("FLASK_PORT", 5000))
PREFIX = "" # All API endpoints will start with this prefix

# ============================================
# Main Application Setup
# ============================================
application = Flask(__name__)
app = application
app.config['PROPAGATE_EXCEPTIONS'] = True
CORS(app)
api = Api(app, prefix=PREFIX, catch_all_404s=True)


# ============================================
# Error Handler
# ============================================

@app.errorhandler(NotFound)
def handle_not_found_error(e):
    response = jsonify({"message": "Resource not found on this URL"})
    response.status_code = 404
    return response


@app.errorhandler(MethodNotAllowed)
def handle_method_not_allowed_error(e):
    response = jsonify({"message": "The method is not allowed for the requested URL"})
    response.status_code = 405
    return response


@app.route('/')
def redirect_to_prefix():
    if PREFIX != '':
        return redirect(PREFIX)


# ============================================
# Add Resources (Banking Account Management API)
# ============================================
# Account CRUD Endpoints
api.add_resource(CreateAccountResource, '/accounts') # POST /accounts
api.add_resource(GetAccountsResource, '/accounts') # GET /accounts
api.add_resource(GetSingleAccountResource, '/accounts/<int:id>') # GET /accounts/<id>
api.add_resource(UpdateAccountResource, '/accounts/<int:id>') # PUT /accounts/<id>
api.add_resource(DeleteAccountResource, '/accounts/<int:id>') # DELETE /accounts/<id>

# Transaction Endpoints
api.add_resource(DepositMoneyResource, '/accounts/deposit') # POST /accounts/deposit
api.add_resource(WithdrawMoneyResource, '/accounts/withdraw') # POST /accounts/withdraw
api.add_resource(TransactionHistoryResource, '/accounts/transactions/<int:id>/') # GET /accounts/<id>/transactions
api.add_resource(AccountStatementJsonResource, '/accounts/statement/<int:id>') # GET /accounts/<id>/transactions
api.add_resource(AccountStatementPdfResource, '/accounts/statement/pdf/<int:id>') # GET /accounts/<id>/transactions
api.add_resource(MonthlyInterestResource, '/accounts/interest/<int:id>')
api.add_resource(BlockAccountResource, '/accounts/block/<int:id>')
api.add_resource(CloseAccountResource, '/accounts/close/<int:id>')






if __name__ == '__main__':
    print(f"Starting Flask Banking API at http://{DOMAIN}:{PORT}{PREFIX}")
    app.run(debug=True, host=DOMAIN, port=PORT)