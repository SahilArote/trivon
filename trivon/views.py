from django.shortcuts import render
from store.models import Product

def home(request):
    products = Product.objects.all().filter(is_available=True)
    for product in products:
        if product.stock > 0:
            product.stock_status = "In Stock"
        else:
            product.stock_status = "Out of Stock"

    context = {
        'stock_status': product.stock_status,
        'products': products,
    }

    return render(request, 'home.html', context)