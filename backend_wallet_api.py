import uvicorn
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from passlib.context import CryptContext
from jose import JWTError, jwt

# --- 1. CONFIGURATION AND CONSTANTS ---

# Initial balance for new users
INITIAL_BALANCE = 100.00

# JWT Configuration
SECRET_KEY = "super-secret-key-do-not-use-in-production-12345"  # Replace this!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- 2. IN-MEMORY DATABASE (Simplified) ---
# NOTE: In a real application, replace these with a proper SQLAlchemy/Postgres ORM setup.

users_db: List[Dict[str, Any]] = []
items_db: List[Dict[str, Any]] = []
transactions_db: List[Dict[str, Any]] = []

# --- 3. SEED DATA ---

def get_next_id(db: List[Dict[str, Any]]) -> int:
    """Helper to get the next unique ID for an in-memory list."""
    if not db:
        return 1
    return max(item['id'] for item in db) + 1

def seed_data():
    """Populates the items database with initial items."""
    print("Seeding initial items...")
    global items_db
    items_db = [
        {"id": 1, "name": "The Great Gatsby (Book)", "price": 50.00},
        {"id": 2, "name": "Coffee Mug", "price": 25.50},
        {"id": 3, "name": "Notebook (Premium)", "price": 10.00},
        {"id": 4, "name": "Mystery Box (Low Risk)", "price": 49.99},
        {"id": 5, "name": "Pen Set (Ballpoint)", "price": 15.00},
    ]
    print(f"Seeded {len(items_db)} items.")

seed_data()

# --- 4. PYDANTIC SCHEMAS ---

# Models for Request and Response Data
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserInDB(UserBase):
    id: int
    hashed_password: str
    balance: float

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class BalanceResponse(BaseModel):
    user_id: int
    username: str
    balance: float

class SpendRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount to spend, must be greater than zero.")
    description: str = Field("General Spend", description="Description for the transaction.")

class Item(BaseModel):
    id: int
    name: str
    price: float

class Transaction(BaseModel):
    id: int
    user_id: int
    timestamp: datetime
    type: str = Field(..., description="e.g., 'REGISTER', 'SPEND', 'BUY'")
    amount: float
    description: str
    item_id: Optional[int] = None
    
# --- 5. SECURITY UTILITIES (Password & JWT) ---

# Password Utilities
def verify_password(plain_password, hashed_password):
    """Checks if the plain password matches the hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Hashes the plain password."""
    return pwd_context.hash(password)

# JWT Utilities
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- 6. USER/WALLET/DATABASE SERVICE FUNCTIONS ---

def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Retrieves a user dictionary by username."""
    return next((user for user in users_db if user["username"] == username), None)

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a user dictionary by ID."""
    return next((user for user in users_db if user["id"] == user_id), None)

def create_user_record(user: UserCreate) -> Dict[str, Any]:
    """Creates a new user, hashes password, sets initial balance, and stores in DB."""
    if get_user(user.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    hashed_password = get_password_hash(user.password)
    user_id = get_next_id(users_db)
    
    new_user = {
        "id": user_id,
        "username": user.username,
        "hashed_password": hashed_password,
        "balance": INITIAL_BALANCE,
    }
    users_db.append(new_user)
    
    # Record initial balance transaction
    record_transaction(
        user_id=user_id,
        amount=INITIAL_BALANCE,
        type="REGISTER",
        description="Initial Wallet Setup",
        item_id=None
    )
    
    return new_user

def record_transaction(user_id: int, amount: float, type: str, description: str, item_id: Optional[int]):
    """Records a new transaction."""
    transaction_id = get_next_id(transactions_db)
    new_transaction = {
        "id": transaction_id,
        "user_id": user_id,
        "timestamp": datetime.now(),
        "type": type,
        "amount": amount,
        "description": description,
        "item_id": item_id
    }
    transactions_db.append(new_transaction)
    return new_transaction

def update_user_balance(user_id: int, amount: float, operation: str):
    """Updates the user's balance based on an operation ('ADD' or 'SUBTRACT')."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if operation == 'SUBTRACT':
        if user['balance'] < amount:
            raise HTTPException(status_code=400, detail="Insufficient funds in wallet.")
        user['balance'] -= amount
    elif operation == 'ADD':
        user['balance'] += amount
    
    # Round balance to 2 decimal places after operation
    user['balance'] = round(user['balance'], 2)

    return user['balance']

# --- 7. DEPENDENCIES ---

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Decodes JWT and retrieves the authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
        
    user = get_user(token_data.username)
    if user is None:
        raise credentials_exception
    
    # Return the full user dictionary
    return user

# --- 8. FASTAPI APPLICATION SETUP ---

app = FastAPI(
    title="Virtual Wallet FastAPI Backend",
    description="A simple API for user authentication, a virtual wallet (starting balance ₹100), and an item purchasing system.",
    version="1.0.0"
)

# --- 9. ENDPOINTS (ROUTERS) ---

# --- AUTH ROUTER ---
@app.post("/auth/register", response_model=UserBase, status_code=status.HTTP_201_CREATED, tags=["Auth"])
def register_user(user: UserCreate):
    """Registers a new user and grants them the initial ₹100 balance."""
    try:
        new_user = create_user_record(user)
        return new_user
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed.")

@app.post("/auth/login", response_model=Token, tags=["Auth"])
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Logs in a user and returns an access token."""
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- WALLET ROUTER ---
@app.get("/wallet/balance", response_model=BalanceResponse, tags=["Wallet"])
def get_balance(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retrieves the current balance of the authenticated user's wallet."""
    return BalanceResponse(
        user_id=current_user["id"],
        username=current_user["username"],
        balance=current_user["balance"]
    )

@app.post("/wallet/spend", response_model=BalanceResponse, tags=["Wallet"])
def spend_money(
    spend_data: SpendRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Deducts an arbitrary amount from the user's wallet."""
    user_id = current_user["id"]
    
    try:
        new_balance = update_user_balance(user_id, spend_data.amount, 'SUBTRACT')
    except HTTPException as e:
        raise e
        
    # Record the transaction
    record_transaction(
        user_id=user_id,
        amount=spend_data.amount,
        type="SPEND",
        description=spend_data.description,
        item_id=None
    )
    
    return BalanceResponse(
        user_id=user_id,
        username=current_user["username"],
        balance=new_balance
    )

# --- ITEMS ROUTER ---
@app.get("/items/list", response_model=List[Item], tags=["Items"])
def list_items():
    """Lists all available items for purchase."""
    # Convert item dicts to Pydantic models for clean response
    return [Item(**i) for i in items_db]

@app.post("/items/buy/{item_id}", response_model=BalanceResponse, tags=["Items"])
def buy_item(
    item_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Allows an authenticated user to purchase an item by ID."""
    user_id = current_user["id"]
    
    # 1. Find the item
    item = next((i for i in items_db if i["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item with ID {item_id} not found.")
        
    item_price = item["price"]
    
    # 2. Check balance and update
    try:
        # Subtract the item price from the user's balance
        new_balance = update_user_balance(user_id, item_price, 'SUBTRACT')
    except HTTPException as e:
        # Re-raise Insufficient funds error
        raise e
    
    # 3. Record transaction
    record_transaction(
        user_id=user_id,
        amount=item_price,
        type="BUY",
        description=f"Purchased: {item['name']}",
        item_id=item_id
    )

    return BalanceResponse(
        user_id=user_id,
        username=current_user["username"],
        balance=new_balance
    )

# --- ADMIN/DEBUG ROUTER (Optional but helpful for development) ---
@app.get("/transactions", response_model=List[Transaction], tags=["Admin/Debug"], description="List all transactions (for all users, requires no auth in this simple version)")
def get_all_transactions():
    """Retrieves all transactions recorded in the system."""
    # Note: In a real app, this would require ADMIN authentication
    return [Transaction(**t) for t in transactions_db]

@app.get("/users", response_model=List[UserInDB], tags=["Admin/Debug"], description="List all users (for all users, requires no auth in this simple version)")
def get_all_users():
    """Retrieves all user records."""
    # Note: In a real app, this would require ADMIN authentication
    # We create a temporary list of Pydantic objects before returning
    users_list = []
    for user in users_db:
        # Exclude hashed_password from the response for security in a real endpoint, but include here for debugging simplicity
        users_list.append(UserInDB(**user))
    return users_list

# --- 10. RUNNER ---
if __name__ == "__main__":
    # Ensure uvicorn is installed (pip install uvicorn)
    # The --reload flag is for development convenience
    print(f"Starting FastAPI server on http://127.0.0.1:8000")
    print(f"Initial balance for new users: ₹{INITIAL_BALANCE}")
    uvicorn.run("backend_wallet_api:app", host="0.0.0.0", port=8000, reload=True)
