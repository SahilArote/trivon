from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from carts.models import CartItem
from .forms import OrderForm
from .models import Order, Payment, OrderProduct
from store.models import Product 
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
import datetime 
import json
from .services.shiprocket import create_shiprocket_order , auto_assign_awb

# Razorpay aur Settings import karna zaroori hai
import razorpay
from django.conf import settings

# Create your views here.

def payments(request):
    body = json.loads(request.body)

    order = Order.objects.get(
        user=request.user,
        is_ordered=False,
        order_number=body['orderID']
    )

    # ----------------------------------------
    # RAZORPAY SIGNATURE VERIFICATION (Security)
    # ----------------------------------------
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    
    try:
        # Check kar rahe hain ki payment sach mein Razorpay se aayi hai ya nahi
        client.utility.verify_payment_signature({
            'razorpay_order_id': body['razorpay_order_id'],
            'razorpay_payment_id': body['transID'],
            'razorpay_signature': body['razorpay_signature']
        })
    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({'error': 'Invalid Payment Signature'}, status=400)


    # Store payment details
    payment = Payment(
        user=request.user,
        payment_id=body['transID'],
        payment_method='Razorpay',  # Hardcode kar diya Razorpay
        amount_paid=order.order_total,
        status='COMPLETED',
    )
    payment.save()

    order.payment = payment
    order.is_ordered = True
    order.save()

    # Move cart items to OrderProduct
    cart_items = CartItem.objects.filter(user=request.user)

    for item in cart_items:
        orderproduct = OrderProduct.objects.create(
            order=order,
            payment=payment,
            user=request.user,
            product=item.product,
            quantity=item.quantity,
            product_price=item.product.price,
            ordered=True,
        )

        orderproduct.variations.set(item.variation.all())

        # Reduce stock
        product = item.product
        product.stock -= item.quantity
        product.save()

    # Clear cart
    CartItem.objects.filter(user=request.user).delete()

    # 🚚 SHIPROCKET INTEGRATION START
    if payment.status == "COMPLETED":   
        print("Payment Status:", payment.status)

        # 1. Pehle Shiprocket par order create karo
        response = create_shiprocket_order(order)
        print("Shiprocket Response:", response)

        if response.get("shipment_id"):
            # Agar order ban gaya, toh ID save kar lo
            order.shiprocket_shipment_id = response.get("shipment_id")
            order.shiprocket_order_id = response.get("order_id")
            order.save()

            # 2. 🚀 NAYA KAAM: Turant us order ko ek Courier (AWB) assign kar do
            print("Assigning AWB now...")
            auto_assign_awb(order)

        else:
            print("Shiprocket Order Creation Error:", response)
    # 🚚 SHIPROCKET INTEGRATION END

    # Send confirmation email
    mail_subject = 'Thank you for your Order'
    message = render_to_string('orders/order_recieved_email.html', {
        'user': request.user,
        'order': order,
    })

    try:
        send_email = EmailMessage(mail_subject, message, to=[request.user.email])
        send_email.send()
    except Exception as e:
        print("Email sending failed, but order was placed:", e)

    return JsonResponse({
        'order_number': order.order_number,
        'transID': payment.payment_id,
    })


def place_order(request, totel=0, quantity=0):
    current_user = request.user

    # if the cart item are 0 then send him to shop
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect('store')

    grand_totel = 0
    tax = 0
    total_mrp = 0  # NAYA: MRP store karne ke liye
    discount = 0   # NAYA: Discount calculate karne ke liye
    
    for cart_item in cart_items:
        totel += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
        
        # NAYA: MRP calculation
        item_mrp = cart_item.product.mrp if cart_item.product.mrp else cart_item.product.price
        total_mrp += (item_mrp * cart_item.quantity)
        
    tax = (2 * totel) / 100
    grand_totel = totel + tax
    
    # NAYA: Discount Calculation
    discount = total_mrp - totel


    if request.method =='POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # store all the info in db         
            data = Order()
            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = int(form.cleaned_data['phone'])
            data.email = form.cleaned_data['email']
            data.address_line_1 = form.cleaned_data['address_line_1']
            data.address_line_2 = form.cleaned_data['address_line_2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']
            data.pincode = form.cleaned_data['pincode']
            data.order_total= grand_totel
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')
            data.save()
            
            # order number
            yr = int(datetime.date.today().strftime('%Y'))
            dt = int(datetime.date.today().strftime('%d'))
            mt = int(datetime.date.today().strftime('%m'))
            d = datetime.date(yr,mt,dt)
            current_date = d.strftime("%Y%m%d") 
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()

            order = Order.objects.get(user=current_user, is_ordered=False, order_number=order_number)

            # ----------------------------------------
            # RAZORPAY ORDER CREATION
            # ----------------------------------------
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            razorpay_amount = int(grand_totel * 100) # Rupees ko Paise mein convert kiya
            
            razorpay_data = {
                "amount": razorpay_amount,
                "currency": "INR",
                "receipt": order.order_number,
            }
            payment_response = client.order.create(data=razorpay_data)
            razorpay_order_id = payment_response['id']

            context ={
                'order': order,
                'cart_items': cart_items,
                'totel': totel,
                'tax': tax,
                'total_mrp': total_mrp,  # NAYA
                'discount': discount,
                'grand_totel': grand_totel,
                # Frontend par Razorpay button lagane ke liye details bhej rahe hain
                'razorpay_order_id': razorpay_order_id,
                'razorpay_amount': razorpay_amount,
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            }
            return render(request, 'orders/payments.html', context)
        else:
            context = {
                'form': form,
                'totel': totel,
                'quantity': quantity,
                'cart_items': cart_items,
                'tax': tax,
                'grand_totel': grand_totel,
            }
            return render(request, 'store/checkout.html', context)


def order_complete(request):
    order_number = request.GET.get('order_number')
    transID = request.GET.get('payment_id') 

    order = None
    ordered_products = None
    payment = None
    subtotal = 0

    try:
        if order_number:
            order = Order.objects.get(order_number=order_number)
            ordered_products = OrderProduct.objects.filter(order_id=order.id)
            for item in ordered_products:
                subtotal += (item.product_price * item.quantity)

        if transID:
            try:
                payment = Payment.objects.get(payment_id=transID)
            except Payment.DoesNotExist:
                payment = None
    except Order.DoesNotExist:
        order = None
        return redirect('home')

    context = {
        'order': order,
        'ordered_products': ordered_products,
        'order_number': order_number,
        'transaction_id': transID,
        'payment': payment,
        'subtotal': subtotal,
    }

    return render(request, 'orders/order_complete.html', context)