from accounts.models import Wishlist


def wishlist_counter(request):

    wishlist_count = 0

    if request.user.is_authenticated:
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
        
    return dict(wishlist_count=wishlist_count)     




