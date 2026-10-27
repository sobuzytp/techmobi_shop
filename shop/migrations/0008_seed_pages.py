from django.db import migrations

PAGES = [
    ('about', 'About Us', 10, """TechMobi is a mobile phone shop in Khulna, Bangladesh. We sell smartphones, tablets, smartwatches and accessories at fair prices, and we deliver across the country.

What you can expect from us:
- Products described honestly, with the condition (new, used or refurbished) and warranty shown on every product page.
- Cash on Delivery: you pay when the order reaches you.
- Real people on the phone and WhatsApp if you need help before or after you buy.

Thank you for shopping with us."""),
    ('contact', 'Contact Us', 20, """Have a question about an order, a product or a warranty claim? Call or message us and we will get back to you as soon as we can.

When you contact us about an order, please keep your order number (it starts with TM) and the phone number you used ready. It helps us find your order quickly."""),
    ('return-policy', 'Return & Refund Policy', 30, """We want you to be happy with what you buy. Please read this before you place an order.

Checking your order
- Please check the parcel in front of the delivery person if you can, and tell us at once if the item is damaged or is not what you ordered.

Returns
- If the product is not what you ordered, arrives damaged, or has a fault, contact us within 7 days of receiving it.
- The product must be in the condition you received it, with the box, accessories and invoice.
- Products that were opened and used without a fault, and items with a broken seal or physical damage caused after delivery, cannot be returned.

Refunds and replacements
- If your return is accepted, we will replace the product or refund the amount, whichever you prefer and whichever is possible for that product.
- Delivery charges are not refunded unless the mistake was ours.

Cancelling an order
- You can cancel a Pending order yourself from My Orders. Once an order has been confirmed or shipped, please contact us."""),
    ('warranty-policy', 'Warranty Policy', 40, """The warranty period of each product is shown on its product page and on your invoice. A product with no warranty listed does not have a shop warranty.

What the warranty covers
- Manufacturing faults that appear during normal use within the warranty period.

What it does not cover
- Physical damage, cracked screens, liquid damage, burns, or damage from unauthorised repair or software changes.
- Accessories such as cables and cases that show normal wear.
- Products whose IMEI or serial number does not match our record.

How to claim
- Contact us with your order number and phone number, and bring the product with its IMEI or serial number and the invoice. We will check it and repair or replace it where the fault is covered."""),
    ('privacy-policy', 'Privacy Policy', 50, """We collect only what we need to process your order: your name, phone number, delivery address and the details of what you ordered. If you create an account, we also keep your account password in a protected (hashed) form.

We use this information to confirm and deliver your order, to contact you about it, to handle returns and warranty claims, and to prevent fake orders. We do not sell your information. We share your name, phone number and address only with the delivery service that delivers your parcel.

You can ask us to correct or delete your account and personal details by contacting us. We may need to keep order records for as long as the law and our accounts require."""),
    ('terms', 'Terms & Conditions', 60, """By placing an order on this website you agree to these terms.

- Prices are in Bangladeshi Taka (Tk) and may change without notice. The price you see when you place the order is the price you pay.
- All orders are paid by Cash on Delivery. Please keep the amount ready when the delivery person arrives.
- We may call you to confirm an order. We may cancel an order we cannot confirm, or when a product is out of stock, and we will tell you if we do.
- Stock is limited. Adding a product to your cart does not reserve it until the order is placed.
- Delivery times depend on your location and the courier. Delivery charges are shown before you place the order.
- Please give a correct name, phone number and address. We are not responsible for delays caused by wrong details.
- Returns and refunds follow our Return & Refund Policy, and warranty claims follow our Warranty Policy."""),
]


def seed(apps, schema_editor):
    Page = apps.get_model('shop', 'Page')
    for slug, title, order, content in PAGES:
        Page.objects.get_or_create(slug=slug, defaults={'title': title, 'sort_order': order, 'content': content})


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0007_trust_and_safety'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
