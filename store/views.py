
from django.shortcuts import render , get_object_or_404, redirect

from accounts.models import Wishlist
from .models import Product, ReviewRating, Variation, Brand
from category.models import Category
from carts.models import CartItem
from django.contrib import messages 
from .forms import ReviewForm
from carts.views import _cart_id
from django.db.models import Q
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from orders.models import OrderProduct    
from django.db.models import F, ExpressionWrapper, FloatField
import difflib

# Create your views here.
def store(request, category_slug=None):

    products = Product.objects.filter(is_available=True)
    category = None

    # ========== CATEGORY FILTER ==========
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    # ========== BRAND FILTER ==========
    # FIX 1: Handle both brand slug and brand name/id
    brand_param = request.GET.get('brand')
    if brand_param:
        try:
            # Try to filter by brand slug first
            products = products.filter(brand__slug=brand_param)
        except:
            # Fallback: Try to filter by brand name if slug doesn't work
            products = products.filter(brand__brand_name__icontains=brand_param)

    # ========== PRICE FILTER ==========
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    if min_price:
        try:
            min_price_int = int(min_price)
            products = products.filter(price__gte=min_price_int)
        except (ValueError, TypeError):
            # Silently skip invalid price input
            pass

    if max_price:
        try:
            max_price_int = int(max_price)
            products = products.filter(price__lte=max_price_int)
        except (ValueError, TypeError):
            # Silently skip invalid price input
            pass

    # ========== DISCOUNT % FILTER (CALCULATED DYNAMICALLY) ==========
    # FIX 2: Better handling of discount calculation with safety checks
    max_discount = request.GET.get('max_discount') 
    min_discount = request.GET.get('min_discount') 

    if max_discount or min_discount:
        try:
            # IMPORTANT: Only include products that have a valid MRP (not null and greater than 0)
            # AND where MRP is actually higher than price (discount exists)
            products = products.filter(mrp__isnull=False).exclude(mrp__lte=0)
            
            # Only filter by price difference if MRP is truly higher
            products = products.filter(mrp__gt=F('price'))
            
            # Annotate with calculated discount percentage using safe division
            # Formula: ((MRP - Price) / MRP) * 100
            products = products.annotate(
                calculated_discount=ExpressionWrapper(
                    ((F('mrp') - F('price')) * 100.0) / F('mrp'),
                    output_field=FloatField()
                )
            )

            # Apply discount range filters
            if max_discount:
                try:
                    max_discount_int = int(max_discount)
                    # Products with discount <= max_discount AND discount > 0
                    products = products.filter(
                        calculated_discount__lte=max_discount_int,
                        calculated_discount__gt=0
                    )
                except (ValueError, TypeError):
                    pass

            if min_discount:
                try:
                    min_discount_int = int(min_discount)
                    # Products with discount >= min_discount
                    products = products.filter(calculated_discount__gte=min_discount_int)
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            # Log but don't crash - continue with unfiltered results
            print(f"Discount filter error: {e}")
            pass

    # 🔎 SIZE FILTER (only if category selected)
    selected_sizes = request.GET.getlist('size')

    if category and selected_sizes:
        products = products.filter(
            variation__variation_category='size',
            variation__variation_value__in=selected_sizes,
            variation__is_active=True
        ).distinct()

    # Pagination
    paginator = Paginator(products.order_by('id'), 6)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)

    # ✅ Show sizes ONLY when category is selected
    if category:
        available_sizes = Variation.objects.filter(
            product__category=category,
            variation_category='size',
            is_active=True
        ).values_list('variation_value', flat=True).distinct()
    else:
        available_sizes = None
    
    brands = Brand.objects.all()

    context = {
        'products': paged_products,
        'product_count': products.count(),
        'available_sizes': available_sizes,
        'selected_sizes': selected_sizes,
        'brands': brands,
    }

    return render(request, 'store/store.html', context)



def product_detail(request, category_slug, product_slug):
    try:
        single_product = Product.objects.get(category__slug=category_slug, slug=product_slug)
        in_cart = CartItem.objects.filter(cart__cart_id=_cart_id(request), product=single_product).exists()
        
    except Exception as e:
        raise e
    
    related_products = Product.objects.filter(category=single_product.category).exclude(id=single_product.id)[:5]
    if request.user.is_authenticated:
        try:
            orderproduct = OrderProduct.objects.filter(user=request.user, product_id=single_product.id).exists()

        except OrderProduct.DoesNotExist:
            orderproduct = None
    else:
        orderproduct = None


    reviews = ReviewRating.objects.filter(product_id=single_product, status=True)

    in_wishlist = False
    if request.user.is_authenticated:
        in_wishlist = Wishlist.objects.filter(user=request.user, product=single_product).exists()

    context = {
        'single_product': single_product,
        'in_cart': in_cart,
        'orderproduct': orderproduct,
        'in_wishlist': in_wishlist,
        'reviews': reviews,
        'related_products': related_products,
    } 

    return render(request, 'store/product_detail.html', context)

def search(request):
    products = Product.objects.none()
    product_count = 0

    if 'keyword' in request.GET:
        keyword = request.GET.get('keyword')
        if keyword:
            keyword = keyword.strip() # Extra spaces hata do
            
            # --- SPELLING MISTAKE FIXER LOGIC ---
            # 1. Database se saare Brands aur Categories ke naam nikal lo
            all_brand_names = list(Brand.objects.values_list('brand_name', flat=True))
            all_category_names = list(Category.objects.values_list('category_name', flat=True))
            
            # 2. Python difflib se check karo ki keyword kis brand/category se sabse zyada milta julta hai (60% match)
            closest_brands = difflib.get_close_matches(keyword, all_brand_names, n=1, cutoff=0.6)
            closest_categories = difflib.get_close_matches(keyword, all_category_names, n=1, cutoff=0.6)
            
            # Agar spelling mistake thi, toh keyword ko actual naam se replace kar do (e.g., 'pume' -> 'puma')
            search_brand = closest_brands[0] if closest_brands else keyword
            search_category = closest_categories[0] if closest_categories else keyword

            # --- SEARCH QUERY ---
            # Ab hum exact keyword aur corrected keyword dono se search karenge
            query = Q(description__icontains=keyword) | \
                    Q(product_name__icontains=keyword) | \
                    Q(brand__brand_name__icontains=search_brand) | \
                    Q(category__category_name__icontains=search_category)

            # Agar user ne multiple words likhe hain (jaise "Nike Jeans"), toh words ko split karke bhi dhundo
            words = keyword.split()
            if len(words) > 1:
                for word in words:
                    query |= Q(product_name__icontains=word) | \
                             Q(brand__brand_name__icontains=word) | \
                             Q(category__category_name__icontains=word)

            # distinct() lagana zaroori hai taaki duplicate products na aayein
            products = Product.objects.filter(query).order_by('-created_date').distinct()
            product_count = products.count()

    context = {
        'products': products,
        'product_count': product_count,
        # 'keyword': keyword  # Optional: User ko dikhane ke liye ki unhone kya search kiya tha
    }

    return render(request, 'store/store.html', context)



def submit_review(request, product_id):
    url = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        try:
            reviews = ReviewRating.objects.get(user__id=request.user.id, product__id=product_id)
            form = ReviewForm(request.POST, instance=reviews)
            form.save()
            messages.success(request, 'Thank you! Your review has been updated.')
            return redirect(url)
        
        except ReviewRating.DoesNotExist:
            form = ReviewForm(request.POST)
            if form.is_valid():
                data = ReviewRating()
                data.subject = form.cleaned_data['subject']
                data.rating = form.cleaned_data['rating']
                data.review = form.cleaned_data['review']
                data.ip = request.META.get('REMOTE_ADDR')
                data.product_id = product_id
                data.user_id = request.user.id
                data.save()
                messages.success(request, 'Thank you! Your review has been submitted.')
                return redirect(url)




