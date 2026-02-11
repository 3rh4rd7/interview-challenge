from django import forms


class LookupForm(forms.Form):
    """Order lookup form.

    The customer enters their order number and either the email address or zip
    code they used when placing the order.
    """

    order_number = forms.CharField(
        max_length=50,
        label="Order number",
        widget=forms.TextInput(
            attrs={"placeholder": "e.g. RMA-1001", "autofocus": True},
        ),
    )
    identifier = forms.CharField(
        max_length=100,
        label="Email or zip code",
        help_text="Enter the email address or zip code used for the order.",
        widget=forms.TextInput(attrs={"placeholder": "Email or zip code"}),
    )
