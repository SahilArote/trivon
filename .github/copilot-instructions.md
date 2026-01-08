# Trivon E-Commerce Platform - AI Coding Guide

## Project Overview
Trivon is a Django 6.0 e-commerce platform using SQLite. Architecture: **four core Django apps** handling distinct domains: `accounts` (authentication), `category` (product categorization), `store` (product catalog), and `carts` (shopping carts). Custom user model (`Account`) replaces Django's default. Session-based carts (no user authentication required).

## Architecture & Key Patterns

### App Boundaries
- **accounts**: Custom user model, email-based auth with verification/password reset tokens (Django's token generators)
- **category**: Product categories with slug URLs; injected into templates via context processor for navigation menus
- **store**: Products with variations (color/size); pagination at 6 items per page (1 item in category filter)
- **carts**: Session-based cart (`_cart_id()` derives from `request.session.session_key`); CartItem tracks variations via M2M

### Data Flow
1. **Product browsing**: Store app filters by category slug, paginated
2. **Add to cart**: POST to `add_cart(product_id)` parses form variations, creates/updates CartItem
3. **Cart context**: `carts.context_processors.counter()` injects `cart_count` into all templates (except admin)
4. **Menu context**: `category.context_processors.menu_links()` provides all categories as `links`

### Critical Integration Points
- **Slug-based URLs**: Product detail requires `category_slug` AND `product_slug` (both ForeignKey/unique)
- **Custom Auth**: `Account` model uses `USERNAME_FIELD = 'email'` (not default username); `MyAccountManager` handles creation
- **Media handling**: Categories/products upload to `photos/categories/` and `photos/products/` respectively
- **Email verification**: Uses Django's `uidb64` token + `token_generator.make_token(user)`

## Key Files & Conventions

| File | Purpose | Pattern |
|------|---------|---------|
| [trivon/settings.py](trivon/settings.py) | Config: custom user, context processors, email SMTP (Gmail) | MEDIA_ROOT = `/media/`, STATIC_ROOT = `/static/` |
| [store/models.py](store/models.py) | Product, Variation (colors/sizes); VariationManager filters by category | `get_url()` returns reverse with category+product slugs |
| [carts/views.py](carts/views.py) | `_cart_id()` from session; add_cart dedupes variations via list matching | Variation list compared to detect duplicate cart items |
| [accounts/forms.py](accounts/forms.py) | Registration/login use custom Account model | Email verification via token link sent to registered email |
| [templates/](templates/) | Base layout with includes; store/ and accounts/ subdirs mirror apps | Context vars: `links` (categories), `cart_count`, `single_product`, `in_cart` |

## Developer Workflows

### Setup
1. **Virtual environment**: `env/` exists; activate with `env\Scripts\activate.bat` (Windows)
2. **Run server**: `python manage.py runserver` (DEBUG=True in settings)
3. **Database**: SQLite `db.sqlite3`; migrations in each app's `migrations/` folder

### Common Tasks
- **Add new product variation type**: Update `variation_category_choice` in [store/models.py](store/models.py), create migration
- **Adjust pagination**: Change `Paginator(products, 6)` in [store/views.py](store/views.py#L20) for different page sizes
- **Modify cart logic**: Variation deduping in [carts/views.py](carts/views.py#L32-L45) uses list comparison; changes affect add_cart flow
- **Update email settings**: Modify EMAIL_HOST_* in [trivon/settings.py](trivon/settings.py#L154-L157) (currently Gmail SMTP)

## Code Style & Standards
- **Models**: Include `get_url()` for slug-based reverse URLs; use `__str__` for admin display
- **Views**: Return context dict with descriptive keys; use `try/except` for ObjectDoesNotExist (minimal use of get_object_or_404)
- **Templates**: Access context vars directly (e.g., `{{ cart_count }}`, `{{ links }}`); includes stored in [templates/includes/](templates/includes/)
- **Naming**: Cart IDs are strings (session keys); product slugs are unique; variation_value and variation_category are CharField choices

## Common Pitfalls
1. **Cart variation matching**: Variation lists must match exactly (order matters in list comparison); test with multiple variations
2. **Slug consistency**: Product detail URL requires matching category AND product slugs in DB; category slug in URL but not product
3. **Session carts**: Clearing `request.session.session_key` breaks cart; cart ownership tied to session ID
4. **Image uploads**: Categories upload to `media/photos/categories/`, products to `photos/products/` (relative to MEDIA_ROOT)
5. **Custom user auth**: Use `Account` model not Django's User; migrate REQUIRED_FIELDS for managers

## Git & Deployment Notes
- Recent push: Django 6.0, Pillow 12.0, sqlparse 0.5.5 installed
- SQLite suitable for development; production requires migration to PostgreSQL/MySQL
- Email credentials in settings.py (extract to environment variables for production)
