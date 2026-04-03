
from django.shortcuts import render , get_object_or_404, redirect

from accounts.models import Wishlist
from .models import Product, ReviewRating, Variation
from category.models import Category
from carts.models import CartItem
from django.contrib import messages 
from .forms import ReviewForm
from carts.views import _cart_id
from django.db.models import Q
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from orders.models import OrderProduct    
from django.db.models import F, ExpressionWrapper, FloatField

# Create your views here.
def store(request, category_slug=None):

    products = Product.objects.filter(is_available=True)
    category = None

    # Category filter
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    # 🔎 PRICE FILTER
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    try:
        if min_price:
            products = products.filter(price__gte=int(min_price))

        if max_price:
            products = products.filter(price__lte=int(max_price))
    except (ValueError, TypeError):
        pass

    max_discount = request.GET.get('max_discount') 
    min_discount = request.GET.get('min_discount') 

    try:
        if max_discount or min_discount:
            # Sirf unhi products par calculation hogi jinka MRP price se zyada hai
            products = products.filter(mrp__isnull=False, mrp__gt=F('price'))
            
            # Database ke andar real-time Discount Percentage calculate karna
            products = products.annotate(
                calculated_discount=ExpressionWrapper(
                    ((F('mrp') - F('price')) * 100.0) / F('mrp'),
                    output_field=FloatField()
                )
            )

            # Ab us calculation ke hisaab se filter karna
            if max_discount:
                products = products.filter(calculated_discount__lte=int(max_discount), calculated_discount__gt=0)
            if min_discount:
                products = products.filter(calculated_discount__gte=int(min_discount))
    except (ValueError, TypeError):
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

    context = {
        'products': paged_products,
        'product_count': products.count(),
        'available_sizes': available_sizes,
        'selected_sizes': selected_sizes,
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
            products = Product.objects.filter(
                Q(description__icontains=keyword) |
                Q(product_name__icontains=keyword)
            ).order_by('-created_date')

            product_count = products.count()

    context = {
        'products': products,
        'product_count': product_count,
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




