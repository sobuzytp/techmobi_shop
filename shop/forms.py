import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

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


class SignupForm(forms.Form):
    """Account = full name + phone number (used as the username) + password."""
    name = forms.CharField(
        max_length=150, label='Full name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'name'}),
    )
    phone = PhoneField(
        max_length=20, label='Phone number',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 01712345678',
                                      'inputmode': 'tel', 'autocomplete': 'tel'}),
    )
    password1 = forms.CharField(
        label='Password', strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirm password', strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if get_user_model().objects.filter(username=phone).exists():
            raise forms.ValidationError("An account with this phone number already exists. Please log in.")
        return phone

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2:
            if p1 != p2:
                self.add_error('password2', "The two passwords do not match.")
            else:
                user = get_user_model()(username=cleaned.get('phone', ''), first_name=cleaned.get('name', ''))
                try:
                    validate_password(p1, user)
                except forms.ValidationError as exc:
                    self.add_error('password1', exc)
        return cleaned

    def save(self):
        data = self.cleaned_data
        return get_user_model().objects.create_user(
            username=data['phone'], password=data['password1'], first_name=data['name'],
        )


class PhoneLoginForm(AuthenticationForm):
    """Log in with phone number + password (accepts +880… / 880… / 017-… too)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Phone number'
        self.fields['username'].widget.attrs.update(
            {'class': 'form-control', 'placeholder': 'e.g. 01712345678', 'inputmode': 'tel'})
        self.fields['password'].widget.attrs.update({'class': 'form-control'})
        self.error_messages['invalid_login'] = "Wrong phone number or password."

    def clean_username(self):
        return normalize_phone(self.cleaned_data['username'])
