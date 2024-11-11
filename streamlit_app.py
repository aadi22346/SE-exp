import streamlit as st
from datetime import datetime, timedelta
from pymongo import MongoClient
from urllib.parse import quote_plus
import ast

# Ensure secrets are set
db_username = st.secrets["DB_USERNAME"]
db_password = st.secrets["DB_PASSWORD"]

# URL-encode the credentials
username = quote_plus(db_username)
password = quote_plus(db_password)

# Database connection
client = MongoClient(f"mongodb+srv://{username}:{password}@cluster0.qovpu.mongodb.net/")
db = client['library_management']

class User:
    def __init__(self, user_id):
        self.user_id = user_id
        self._db = db
        print(f"Initialized User with user_id: {self.user_id}")

    def get_user_details(self):
        print(f"Fetching details for user_id: {self.user_id}")
        user = self._db.users.find_one({"user_id": self.user_id})
        if user:
            print(f"User found: {user}")
            return {
                "user_id": user.get("user_id"),
                "name": user.get("name"),
                "email": user.get("email"),
                "status": user.get("status")
            }
        else:
            print("User not found")
            return None

    def get_status(self):
        user = self._db.users.find_one({"user_id": self.user_id})
        return user.get("status") if user else None

    def has_overdue_books(self):
        current_date = datetime.now()
        overdue = self._db.borrow_transactions.find_one({
            'user_id': self.user_id,
            'due_date': {'$lt': current_date},
            'returned': False
        })
        return bool(overdue)

class Book:
    def __init__(self, title):
        self.title = title
        self._db = db
        print(f"Initialized Book with title: {self.title}")

    def check_availability(self):
        print(f"Checking availability for book_title: {self.title}")
        book = self._db.books.find_one({"book_title": self.title})
        if book:
            print(f"Book found: {book}")
            return book["available_copies"] > 0
        else:
            print("Book not found")
            return False

    def update_inventory(self, change):
        print(f"Updating inventory for book_title: {self.title} with change: {change}")
        result = self._db.books.update_one({"book_title": self.title}, {"$inc": {"available_copies": change}})
        print(f"Update result: {result.modified_count}")
        return result.modified_count > 0

class BorrowTransaction:
    def __init__(self):
        self._db = db

    def create_transaction(self, user_id, book_title, borrow_date, due_date):
        print(f"Creating transaction for user_id: {user_id}, book_title: {book_title}")
        transaction = {
            'user_id': user_id,
            'book_title': book_title,
            'borrow_date': borrow_date,
            'due_date': due_date,
            'returned': False
        }
        result = self._db.borrow_transactions.insert_one(transaction)
        print(f"Transaction result: {result.inserted_id}")
        return bool(result.inserted_id)

class LibrarySystem:
    def __init__(self):
        self._db = db
        print("Initialized LibrarySystem")

    def borrow_books(self, user_id, book_title):
        print(f"Borrowing book: {book_title} for user: {user_id}")
        user_details = self._db.users.find_one({"user_id": user_id})
        if not user_details or user_details["status"] != "active":
            print("Invalid user or user has overdue books")
            return "Invalid user or user has overdue books", False

        book = Book(book_title)
        if not book.check_availability():
            self.notify_book_unavailable(book_title)
            return "Book is unavailable", False

        # Create transaction
        borrow_date = datetime.now()
        due_date = borrow_date + timedelta(days=14)
        
        transaction = BorrowTransaction()
        if not transaction.create_transaction(user_id, book_title, borrow_date, due_date):
            print("Failed to create transaction")
            return "Failed to create transaction", False
        
        # Update inventory
        if not book.update_inventory(-1):
            print("Failed to update inventory")
            return "Failed to update inventory", False
        
        # Schedule notification
        self.schedule_due_date_notification(user_details["name"], user_details["email"], book_title, due_date)
        
        print(f"Book borrowed successfully! Due date: {due_date.strftime('%Y-%m-%d')}")
        return f"Book borrowed successfully! Due date: {due_date.strftime('%Y-%m-%d')}", True

    def notify_book_unavailable(self, book_title):
        print(f"Book '{book_title}' is currently unavailable.")
        st.warning(f"Book '{book_title}' is currently unavailable.")

    def notify_overdue_books(self):
        current_date = datetime.now()
        overdue_transactions = []
        
        transactions = self._db.borrow_transactions.find({
            'due_date': {'$lt': current_date},
            'returned': False
        })
        for transaction in transactions:
            overdue_transactions.append(transaction)
        print(f"Overdue transactions: {overdue_transactions}")
        return overdue_transactions

    def schedule_due_date_notification(self, user_name, user_email, book_title, due_date):
        # Logic to schedule notification (e.g., using a task queue)
        print(f"Notification scheduled for {user_name} ({user_email}) for book '{book_title}' due on {due_date.strftime('%Y-%m-%d')}")
        st.info(f"Notification scheduled for {user_name} ({user_email}) for book '{book_title}' due on {due_date.strftime('%Y-%m-%d')}")

# Streamlit app
st.title("Library System")

# Search bar for books
st.subheader("Search for a Book")
partial_title = st.text_input("Start typing the book title...")

# Fetch search results based on partial title
if partial_title:
    books = db.books.find({"book_title": {"$regex": partial_title, "$options": "i"}})
    search_results = [book["book_title"] for book in books]
    st.write(f"Search results: {search_results}")  # Debugging statement
    selected_book_title = st.selectbox("Select a book from the list:", search_results)
else:
    selected_book_title = None

# Display book details if a title is selected
if selected_book_title:
    st.write(f"Selected book title: {selected_book_title}")  # Debugging statement
    book = db.books.find_one({"book_title": selected_book_title})
    if book:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(book['cover_image_uri'], width=200)
        with col2:
            st.write(f"**Title:** {book['book_title']}")
            st.write(f"**Author:** {book['author']}")

            # Convert genres string to list
            genres = ast.literal_eval(book['genres']) if isinstance(book['genres'], str) else book['genres']
            if genres:
                st.write("**Genres:**")
                for genre in genres:
                    st.write(f"- {genre}")

            st.write(f"**Available Copies:** {book['available_copies']}")
            st.write(f"**Details:** {book['book_details']}")

            # Borrow section with improved flow
            st.subheader("Borrow this Book")
            
            # User ID input
            user_id = st.text_input("Enter your user ID:", key="user_id_input", value=st.session_state.get("user_id", ""))
            
            # Store user_id in session state
            if user_id:
                st.session_state.user_id = user_id

            if st.button("Borrow Book"):
                if user_id:
                    library = LibrarySystem()
                    message, success = library.borrow_books(user_id, selected_book_title)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
    else:
        st.error("Could not fetch book details.")

# Notify book unavailability
if st.button("Notify Unavailable Books"):
    unavailable_books = db.books.find({'available_copies': 0})
    book_titles = [book['book_title'] for book in unavailable_books]
    if book_titles:
        st.write("Unavailable Books:")
        for title in book_titles:
            st.write(f"- {title}")
    else:
        st.write("All books are available.")

# Notify overdue books
if st.button("Notify Overdue Books"):
    library = LibrarySystem()
    overdue_books = library.notify_overdue_books()
    if overdue_books:
        st.write("Overdue Books:")
        for overdue in overdue_books:
            st.write(f"User: {overdue['user_name']}, Book Title: {overdue['book_title']}")
    else:
        st.write("No overdue books.")