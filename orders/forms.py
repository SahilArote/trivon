from django import forms
from .models import Order


class OrderForm(forms.ModelForm):
    phone = forms.CharField(
        max_length=15,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'required': True, 'min': '0'}),
        error_messages={
            'invalid': 'Phone number must contain only numbers.',
            'required': 'Phone number is required.'
        }
    )
    
    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'phone' ,'email', 'address_line_1', 'address_line_2','country', 'state', 'city', 'order_note', 'pincode' ]
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Check if phone contains only digits
            if not phone.isdigit():
                raise forms.ValidationError('Phone number must contain only numbers. No letters or special characters allowed.')
            # Check minimum length (optional - adjust as needed)
            if len(phone) < 10:
                raise forms.ValidationError('Phone number must be at least 10 digits long.')
        return phone
