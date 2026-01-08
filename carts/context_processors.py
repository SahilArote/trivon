from carts.models import Cart , CartItem
from .views import _cart_id 




def counter(request):
    cart_count = 0
    if 'admin' in request.path:
        return {}
    else:
        try:
            cart = Cart.objects.filter(cart_id=_cart_id(request))
            # For authenticated users: get cart items by user
            if request.user.is_authenticated:
                cart_items = CartItem.objects.filter(user=request.user, is_active=True)
            else:
                cart_items = CartItem.objects.all().filter(cart=cart[:1])
            for cart_item in cart_items:
                cart_count += cart_item.quantity

        except Cart.DoesNotExist:
            cart_count = 0

    return dict(cart_count=cart_count)        

       

