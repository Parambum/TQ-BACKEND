FastAPI Virtual Wallet & E-Commerce API
This project implements a simple FastAPI backend with user authentication (JWT), a virtual wallet, and a basic item purchasing system. It uses an in-memory structure for the database for simplicity and easy startup.

1. Prerequisites
You need Python 3.8+ installed.

2. Setup and Installation
Clone the repository (or save the Python file):

Save the code above as backend_wallet_api.py.

Install Dependencies:
This project requires FastAPI, Uvicorn, Pydantic, Passlib, and Python-Jose.

pip install fastapi "uvicorn[standard]" pydantic "python-jose[cryptography]" passlib bcrypt

Run the Server:
Execute the Python file directly:

python backend_wallet_api.py

The server will start at http://127.0.0.1:8000.

3. API Documentation (Swagger UI)
Once the server is running, you can view the interactive documentation (Swagger UI) at:

➡️ http://127.0.0.1:8000/docs

4. API Usage Examples (cURL or Postman)
All currency is denoted in ₹ (Rupees).

Step 1: Register a New User
New users automatically receive an initial balance of ₹100.00.

curl -X POST "[http://127.0.0.1:8000/auth/register](http://127.0.0.1:8000/auth/register)" \
-H "Content-Type: application/json" \
-d '{"username": "testuser", "password": "securepassword123"}'

Expected Response:

{
  "username": "testuser"
}

Step 2: Login and Get JWT Token
Use the registered credentials to get an access_token. This token is required for all wallet and item operations.

# Note: FastAPI uses x-www-form-urlencoded for OAuth2PasswordRequestForm
curl -X POST "[http://127.0.0.1:8000/auth/login](http://127.0.0.1:8000/auth/login)" \
-H "Content-Type: application/x-www-form-urlencoded" \
-d "username=testuser&password=securepassword123"

Expected Response (Save the access_token!):

{
  "access_token": "eyJhbGciOiJIUzI1NiI...",
  "token_type": "bearer"
}

Step 3: Check Wallet Balance (Requires Token)
Use the token obtained in Step 2 in the Authorization header.

# Replace <YOUR_JWT_TOKEN> with the token from Step 2
export AUTH_TOKEN="<YOUR_JWT_TOKEN>"

curl -X GET "[http://127.0.0.1:8000/wallet/balance](http://127.0.0.1:8000/wallet/balance)" \
-H "Authorization: Bearer $AUTH_TOKEN"

Expected Response:

{
  "user_id": 1,
  "username": "testuser",
  "balance": 100.0
}

Step 4: List Available Items
Check the list of available items and their prices.

curl -X GET "[http://127.0.0.1:8000/items/list](http://127.0.0.1:8000/items/list)"

Expected Response (Partial):

[
  { "id": 1, "name": "The Great Gatsby (Book)", "price": 50.0 },
  { "id": 2, "name": "Coffee Mug", "price": 25.5 },
  // ... more items
]

Step 5: Buy an Item (Requires Token)
Let's buy Item ID 1 ("The Great Gatsby") for ₹50.00.

# Use the AUTH_TOKEN from Step 2
curl -X POST "[http://127.0.0.1:8000/items/buy/1](http://127.0.0.1:8000/items/buy/1)" \
-H "Authorization: Bearer $AUTH_TOKEN"

Expected Response (Balance reduced: 100.00 - 50.00 = 50.00):

{
  "user_id": 1,
  "username": "testuser",
  "balance": 50.0
}

Step 6: Arbitrary Spending (Requires Token)
Deduct another ₹20.50 from the wallet.

# Use the AUTH_TOKEN from Step 2
curl -X POST "[http://127.0.0.1:8000/wallet/spend](http://127.0.0.1:8000/wallet/spend)" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $AUTH_TOKEN" \
-d '{"amount": 20.50, "description": "Taxi ride home"}'

Expected Response (Balance reduced: 50.00 - 20.50 = 29.50):

{
  "user_id": 1,
  "username": "testuser",
  "balance": 29.5
}

Debug/Admin Endpoints (No Auth Required)
You can check the transaction history and the list of users for debugging:

List Users: GET http://127.0.0.1:8000/users

List Transactions: GET http://127.0.0.1:8000/transactions
