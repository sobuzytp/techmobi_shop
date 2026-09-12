from django import forms
from .models import Customer


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'address']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Enter your full name'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. 01712345678'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control', 'placeholder': 'Full delivery address', 'rows': 3
            }),
        }
