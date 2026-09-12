# TechMobi — Single Vendor Mobile Shop (Django)

TechMobi is a simple single-vendor e-commerce website for a **mobile phone shop**, built with
Django, HTML, CSS, JavaScript, Bootstrap 5, and SQLite.

Customers can browse products, view product details, add items to a shopping cart, adjust
quantities, and check out — with the order saved to the database.

## Features

- **Home page** — shop banner, product categories, and featured products.
- **Product listing** — all products loaded from the database, with search and category filter.
- **Product details** — image, price, description, available stock, and Add to Cart.
- **Shopping cart** (session-based) — add, increase/decrease quantity, remove items, live total.
- **Checkout** — customer name, phone, and address form; saves the order to the database and
  reduces stock; shows an **"Order Placed Successfully!"** confirmation page.
- **Django Admin** — full product, category, customer, and order management.
- **Responsive Bootstrap 5 UI** — navbar, cards, buttons, forms, grid, and alerts.
- **JavaScript** — Bootstrap form validation on checkout, live cart total preview, auto-dismissing
  alerts.

### Bonus features implemented
- Product search (navbar + product list page)
- Category filter
- Product discount (percentage-based, shown with a strikethrough old price)

## Project Structure

```
techmobi_project/
├── manage.py
├── requirements.txt
├── README.md
├── techmobi/            # Project settings, root URLs
│   ├── settings.py
│   ├── urls.py
│   └── ...
├── shop/                 # Main app
│   ├── models.py         # Category, Product, Customer, Order
│   ├── views.py           # Home, product list/detail, cart, checkout, order success
│   ├── urls.py
│   ├── forms.py           # CheckoutForm (Customer)
│   ├── admin.py
│   ├── management/commands/seed_products.py   # optional sample data seeder
│   └── templates/shop/
│       ├── base.html
│       ├── home.html
│       ├── product_list.html
│       ├── product_detail.html
│       ├── cart.html
│       ├── checkout.html
│       └── order_success.html
├── static/
│   ├── css/style.css
│   └── js/main.js
└── media/                 # uploaded product images (created at runtime)
```

## Database Models

- **Product** — name, price, description, image, quantity, category, discount, featured flag.
- **Customer** — name, phone, address.
- **Order** — customer (FK), product (FK), quantity, total price, order date, status.

## Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/single-vendor-ecommerce.git
cd single-vendor-ecommerce
```

### 2. Create a virtual environment and install dependencies
```bash
python -m venv .venv
source .venv/bin/activate      # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Apply migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Create an admin user
```bash
python manage.py createsuperuser
```

### 5. (Optional) Seed sample products
```bash
python manage.py seed_products
```

### 6. Run the development server
```bash
python manage.py runserver
```

Visit:
- Storefront: http://127.0.0.1:8000/
- Admin panel: http://127.0.0.1:8000/admin/

## Adding Products

Log into the Django Admin panel (`/admin/`) with your superuser account and add:
1. **Categories** (e.g. Smartphones, Tablets, Accessories)
2. **Products** — set the name, price, description, image, quantity, category, and optionally
   mark it as *Featured* or give it a *discount percent*.

## Customer Flow

```
View Products → View Details → Add to Cart → Manage Cart → Checkout → Place Order
```

The cart is stored in the user's session (no login required). On checkout, a `Customer` record
is created and an `Order` is saved for each cart line, then the cart is cleared and the customer
is redirected to the **Order Placed Successfully!** page.

## Notes

- `db.sqlite3` and `media/` are excluded from version control via `.gitignore` — run the
  migration (and optionally the seed) commands after cloning to set up your own local database.
- This project is built for educational purposes as part of a Django practice assignment.
