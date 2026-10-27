import re

from django import forms

from .models import Order, phone_validator


def normalize_phone(value):
    """Turn +8801712345678 / 8801712345678 / 017-1234-5678 into 01712345678."""
    digits = re.sub(r'[\s\-]', '', value or '')
    if digits.startswith('+88'):
        digits = digits[3:]
    elif digits.startswith('880') and len(digits) == 13:
        digits = digits[2:]
    return digits


class PhoneField(forms.CharField):
    def to_python(self, value):
        return normalize_phone(super().to_python(value))

    default_validators = [phone_validator]


class CheckoutForm(forms.Form):
    name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your full name'}),
    )
    phone = PhoneField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 01712345678',
                                      'inputmode': 'tel'}),
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Full delivery address', 'rows': 3}),
    )
    delivery_area = forms.ChoiceField(
        choices=Order.AREA_CHOICES, initial='inside',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )
    payment_method = forms.ChoiceField(
        choices=Order.PAYMENT_CHOICES, initial='cod',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                     'placeholder': 'Optional note for the delivery'}),
    )


class TrackOrderForm(forms.Form):
    order_number = forms.CharField(
        max_length=12,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. TM1A2B3C4D'}),
    )
    phone = PhoneField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone used for the order'}),
    )

    def clean_order_number(self):
        return self.cleaned_data['order_number'].strip().upper()
