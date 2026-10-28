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
- Category, brand and price-range filters, sorting, and pagination
- Product discount (percentage-based, shown with a strikethrough old price)
- Product specifications (RAM, storage, display, battery, camera, color), image gallery, related products
- Stock-aware cart (cannot add more than available) and atomic checkout
- Cash on Delivery with delivery charge by area (Inside / Outside Khulna)
- One order with many items, unique order number, and an **order tracking** page (order number + phone)
- Custom 404 page
- **Coupons** (percent or fixed, min order, usage limits, expiry), **Buy Now**, **Wishlist**, verified-buyer **reviews**, recently viewed, WhatsApp order button, home-page offer banners
- **Order management**: customers can cancel Pending orders (stock is restored), order status timeline, admin bulk status actions, call-confirmed flag, CSV export, printable invoice, blocked phone numbers
- **Sales dashboard** at `/dashboard/` (staff only): today/month sales, 7-day chart, pending orders, low stock, top products
- **Shop settings** in the admin: delivery charges, free-delivery threshold, minimum order, low-stock level, WhatsApp number
- **Warranty, condition and IMEI/serial** on products and invoices; editable **text pages** (About, Contact, Return, Warranty, Privacy, Terms) and contact details from the admin
- **Rate limiting** on login, sign-up, order tracking and coupon guessing; daily `backup_data` command
- SEO: meta/Open Graph tags, `sitemap.xml`, `robots.txt`
- **Accounts**: sign up / log in with phone number + password, "My Orders" history, checkout prefilled from your account and last order (an account is required to place an order; browsing and the cart work without one)

## Project Structure

```
techmobi_shop/
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

- **Product** — name, brand, price, description, image, quantity, category, discount, featured flag, specs.
- **ProductImage** — extra gallery images for a product.
- **Customer** — name, phone (unique per phone at checkout), address.
- **Order** — order number, customer, delivery area/charge, payment method, subtotal, total, status.
- **OrderItem** — order, product, product name/unit price snapshot, quantity, line total.

## Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/sobuzytp/techmobi_shop.git
cd techmobi_shop
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
is created or reused (by phone number) and a single `Order` with one `OrderItem` per cart line is saved, then the cart is cleared and the customer
is redirected to the **Order Placed Successfully!** page.

## Configuration

Environment variables (all optional for local development):

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Secret key. **Set this in production.** |
| `DJANGO_DEBUG` | `1` (default) or `0`. Use `0` in production. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts, required when `DJANGO_DEBUG=0`. |
| `DJANGO_SERVE_MEDIA` | `1` lets Django serve `/media/` when `DJANGO_DEBUG=0` (if your web server does not). |
| `DJANGO_BEHIND_PROXY` | `1` if the host terminates HTTPS and sends `X-Forwarded-Proto`. |
| `DJANGO_CLIENT_IP_HEADER` | Where to read the visitor IP for rate limits behind a proxy/CDN (`HTTP_X_FORWARDED_FOR`, `HTTP_CF_CONNECTING_IP`). The staff dashboard shows the IP the server sees. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Optional, e.g. `https://tech-mobi.notte.top`. |

Delivery charges, free-delivery threshold and minimum order are edited in the admin under **Shop settings** (`DELIVERY_CHARGES` in `techmobi/settings.py` only supplies the first defaults).

With `DJANGO_DEBUG=0`, session and CSRF cookies are marked Secure (HTTPS only).

## Backups

```bash
python manage.py backup_data            # db + media -> ../techmobi-backups/techmobi-backup-<date>.zip
python manage.py backup_data --keep 30  # keep the newest 30 (default 14)
```

Run it every day from cron (cPanel -> Cron Jobs), e.g. at 03:00:

```
0 3 * * * /home/USER/virtualenv/APP/3.11/bin/python /home/USER/APP/manage.py backup_data
```

Download a copy now and then and keep it somewhere other than the server. To restore, unzip, put `db.sqlite3`
back in the project folder and the `media/` folder next to it.

## Tests

```bash
python manage.py test
```

## Notes

- `db.sqlite3` and `media/` are excluded from version control via `.gitignore` — run the
  migration (and optionally the seed) commands after cloning to set up your own local database.
- This project is built for educational purposes as part of a Django practice assignment.

## REST API and aijobab sync

Public, read-only JSON API (no customer data, no writes):

| URL | What |
|---|---|
| `/api/v1/` | list of endpoints |
| `/api/v1/products/` | products; `?q=`, `?category=`, `?brand=`, `?in_stock=1`, `?page=`, `?page_size=` (max 100) |
| `/api/v1/products/<id>/` | one product |
| `/api/v1/categories/`, `/api/v1/shop/`, `/api/v1/pages/` | categories, shop contact/delivery info, policy pages |
| `/api/v1/feed.csv` | all products as CSV (e.g. for an Excel price-list import) |

Sending the catalogue to aijobab (set these in cPanel > Setup Python App, never commit them):

    AIJOBAB_SYNC_URL=https://...      # endpoint from your aijobab dashboard/docs
    AIJOBAB_API_KEY=...               # your key
    AIJOBAB_AUTH_HEADER=Authorization # or X-API-Key, if aijobab asks for that

    python manage.py sync_catalog --dry-run   # show what would be sent
    python manage.py sync_catalog             # send it (add to cron to keep it fresh)

The payload is `{"source", "shop", "products": [...]}`; adjust `build_payload` in
`shop/management/commands/sync_catalog.py` if aijobab expects a different shape.
