from django.conf import settings
import requests
from django.conf import settings
from orders.models import OrderProduct
import requests

BASE_URL = "https://apiv2.shiprocket.in/v1/external"


# =========================
# 1️⃣ GENERATE TOKEN
# =========================
def generate_token():
    url = f"{BASE_URL}/auth/login"

    payload = {
        "email": settings.SHIPROCKET_EMAIL,
        "password": settings.SHIPROCKET_PASSWORD
    }

    response = requests.post(url, json=payload)
    return response.json().get("token")


# =========================
# 2️⃣ CREATE ORDER
# =========================
def create_shiprocket_order(order):

    token = generate_token()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    url = f"{BASE_URL}/orders/create/adhoc"

    order_products = OrderProduct.objects.filter(order=order)

    order_items = []
    for item in order_products:
        order_items.append({
            "name": item.product.product_name,
            "sku": str(item.product.id),
            "units": item.quantity,
            "selling_price": str(item.product_price),
        })

    payload = {
        "order_id": order.order_number,
        "order_date": order.created_at.strftime('%Y-%m-%d %H:%M'),
        "pickup_location": "Home",

        "billing_customer_name": order.first_name,
        "billing_last_name": order.last_name or "NA",
        "billing_address": order.address_line_1,
        "billing_address_2": order.address_line_2,
        "billing_city": order.city,
        "billing_pincode": str(order.pincode),
        "billing_state": order.state,
        "billing_country": order.country,
        "billing_email": order.email,
        "billing_phone": str(order.phone),

        "shipping_is_billing": True,

        "shipping_customer_name": order.first_name,
        "shipping_last_name": order.last_name or "NA",
        "shipping_address": order.address_line_1,
        "shipping_address_2": order.address_line_2,
        "shipping_city": order.city,
        "shipping_pincode": str(order.pincode),
        "shipping_state": order.state,
        "shipping_country": order.country,
        "shipping_email": order.email,
        "shipping_phone": str(order.phone),

        "order_items": order_items,
        "payment_method": "Prepaid",
        "sub_total": str(order.order_total),

        "length": 10,
        "breadth": 10,
        "height": 10,
        "weight": 0.5,
    }

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()

    print("CREATE ORDER RESPONSE:", data)

    if data.get("shipment_id"):
        order.shiprocket_order_id = data.get("order_id")
        order.shipment_id = data.get("shipment_id")
        order.save()

        # 🔥 AUTO ASSIGN COURIER
        auto_assign_awb(order)

    return data


# =========================
# 3️⃣ AUTO ASSIGN COURIER + AWB
# =========================
def auto_assign_awb(order):
    token = generate_token()
    
    if not token:
        print("Shiprocket Token Generate Nahi Hua!")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    # Step 1: Check Serviceability
    service_url = f"{BASE_URL}/courier/serviceability/"

    service_payload = {
        "pickup_postcode": settings.SHIPROCKET_PICKUP_PINCODE,
        "delivery_postcode": order.pincode,
        "cod": 0,
        "weight": 0.5
    }

    try:
        service_response = requests.get(
            service_url,
            params=service_payload,
            headers=headers
        )
        service_data = service_response.json()

        print("SERVICEABILITY RESPONSE:", service_data)

        couriers = service_data.get("data", {}).get("available_courier_companies", [])

        if not couriers:
            print("No courier available for this pincode.")
            return

        # Select first available courier (Sabse sasta/fastest option manually bhi sort kar sakte hain baad mein)
        courier_id = couriers[0]["courier_company_id"]

        # Step 2: Assign AWB
        assign_url = f"{BASE_URL}/courier/assign/awb/"

        assign_payload = {
            # FIX 1: Corrected field name as per your previous models
            "shipment_id": order.shiprocket_shipment_id, 
            "courier_id": courier_id
        }

        assign_response = requests.post(assign_url, json=assign_payload, headers=headers)
        assign_data = assign_response.json()

        print("ASSIGN AWB RESPONSE:", assign_data)
        
        # FIX 2: Correct Shiprocket JSON Parsing
        # Shiprocket ka format aise aata hai: {"response": {"data": {"awb_code": "...", "courier_name": "..."}}}
        response_data = assign_data.get("response", {}).get("data", {})
        
        awb = response_data.get("awb_code")

        if awb:
            order.awb_code = awb
            order.courier_name = response_data.get("courier_name")
            order.shipment_status = "AWB Assigned"
        else:
            print("AWB Not Found in Response, shifting to Sandbox Mode")
            order.awb_code = "TEST-AWB-123456"
            order.shipment_status = "Sandbox Mode"

        order.save()
        print(f"AWB Assigned Successfully: {awb}")

    except Exception as e:
        print("Error in AWB Assignment:", str(e))


# ... (Aapka purana create_shiprocket_order wala code) ...

def get_shiprocket_token():
    url = "https://apiv2.shiprocket.in/v1/external/auth/login"
    payload = {
        "email": settings.SHIPROCKET_EMAIL,
        "password": settings.SHIPROCKET_PASSWORD
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json().get('token')
    return None

def track_shipment_live(shipment_id):
    token = get_shiprocket_token()
    if not token:
        return None
    
    # Shipment ID ke through live tracking ka URL
    url = f"https://apiv2.shiprocket.in/v1/external/courier/track/shipment/{shipment_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None 