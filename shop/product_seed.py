"""Detailed information for products already in the shop.

Only EMPTY fields are filled, so anything you typed yourself is never overwritten.
Specs below come from the makers' official pages or well-known spec sheets; always glance at
them in the admin before relying on them, and add what is specific to your stock (colour, storage).
"""

COMMON_FAQ = (
    "Q: Can I pay online?\nA: We take Cash on Delivery only. You pay the delivery person when the product reaches you.\n\n"
    "Q: How long does delivery take?\nA: Inside Dhaka usually 1-2 days and outside Dhaka 2-5 days. You will get a confirmation call after ordering.\n\n"
    "Q: Is the product original?\nA: Yes. We sell original products with the warranty shown on the page."
)

KNOWN = [
    {
        'match': ['iphone 18 pro max'],
        'brand': 'Apple', 'processor': 'Apple A20 Pro (6-core CPU, 7-core GPU)',
        'display': '6.9-inch Super Retina XDR OLED, 120Hz ProMotion', 'os': 'iOS',
        'battery': 'Up to 45 hours video playback',
        'charging': '60W fast charging (50% in ~15 min), MagSafe/Qi2 25W wireless',
        'camera': '48MP triple rear (Main, Ultra Wide, 4x Telephoto), 18MP front',
        'network': '5G, Wi-Fi 7, Bluetooth 6', 'sim': 'Dual eSIM (no physical SIM)',
        'short_description': "Apple's biggest Pro iPhone with the A20 Pro chip and a triple 48MP camera system.",
        'highlights': "A20 Pro chip\n6.9-inch ProMotion OLED display (120Hz)\nTriple 48MP rear cameras with 4x telephoto\n18MP Center Stage front camera\nUp to 45 hours video playback\nFast charging and MagSafe/Qi2 wireless",
        'extra_specs': "Storage options: 256GB, 512GB, 1TB, 2TB\nWeight: 249 g\nDimensions: 163.4 x 78.0 x 8.75 mm\nColours: Black, Silver, Glacier, Burgundy\nConnectivity: Ultra Wideband, NFC, multi-band GPS",
        'in_the_box': "iPhone 18 Pro Max\nUSB-C charge cable (1 m)\nDocumentation\n(Power adapter and EarPods are not included)",
        'ai_notes': "Premium buyer who wants the best iPhone camera and battery life. Phone is eSIM only, so check the customer's operator supports eSIM. No charger in the box - suggest a 20W+ USB-C adapter.",
    },
    {
        'match': ['galaxy s26 ultra', 's26 ultra'],
        'brand': 'Samsung', 'processor': 'Snapdragon 8 Elite Gen 5',
        'ram': '12GB', 'storage': '256GB',
        'display': '6.9-inch Dynamic LTPO AMOLED 2X, QHD+, 120Hz', 'os': 'Android 16 (One UI 8.5)',
        'battery': '5000 mAh', 'charging': '60W wired, 25W wireless',
        'camera': '200MP main + 50MP ultra-wide + 50MP periscope + 10MP telephoto, 12MP front',
        'network': '5G, Wi-Fi 7, Bluetooth 6.0, NFC', 'sim': 'Dual SIM (nano-SIM + eSIM)',
        'short_description': "Samsung's top flagship: 200MP camera, Snapdragon 8 Elite Gen 5 and a 6.9-inch QHD+ screen.",
        'highlights': "200MP main camera with 100x digital zoom\nSnapdragon 8 Elite Gen 5 processor\n6.9-inch QHD+ AMOLED, 120Hz, up to 2600 nits\n5000 mAh battery with 60W fast charging\nIP68 water and dust resistance\nGorilla Armor 2 glass",
        'extra_specs': "Weight: 214 g\nDimensions: 163.6 x 78.1 x 7.9 mm\nColours: Cobalt Violet, Sky Blue, Black, White, Silver Shadow, Pink Gold\nWater resistance: IP68\n8K video recording",
        'in_the_box': "Galaxy S26 Ultra\nUSB-C cable\nSIM ejector tool\nQuick start guide\n(Charger may be sold separately - ask us)",
        'ai_notes': "For heavy camera users, creators and people who want the biggest Android screen. Compare against iPhone Pro Max for customers undecided between Android and iPhone. Confirm the exact RAM/storage in stock before promising.",
    },
    {
        'match': ['redmi note 13 pro'],
        'brand': 'Xiaomi', 'processor': 'Snapdragon 7s Gen 2 (5G) / Helio G99-Ultra (4G)',
        'display': '6.67-inch 1.5K AMOLED, 120Hz', 'os': 'Android with HyperOS / MIUI',
        'battery': '5100 mAh (5G) / 5000 mAh (4G)', 'charging': '67W turbo charging',
        'camera': '200MP main (OIS) + 8MP ultra-wide + 2MP macro, 16MP front',
        'sim': 'Dual SIM',
        'short_description': 'Mid-range phone with a 200MP camera, bright 120Hz AMOLED screen and 67W fast charging.',
        'highlights': "200MP main camera with OIS\n6.67-inch 1.5K AMOLED, 120Hz\n67W fast charging\nGorilla Glass Victus front\nSlim, light body",
        'extra_specs': "Splash resistance: IP54",
        'in_the_box': "Redmi Note 13 Pro\n67W charger\nUSB-C cable\nProtective case\nSIM ejector tool\nDocumentation",
        'ai_notes': "Best value pick for customers who want a great camera and screen at a mid-range price. The chipset and battery depend on the 4G or 5G version - check which one is in stock.",
    },
    {
        'match': ['airpods pro'],
        'brand': 'Apple', 'processor': 'Apple H2 chip', 'network': 'Bluetooth 5.3',
        'battery': 'Up to 6 hours listening (ANC on), up to 30 hours with case',
        'charging': 'Wireless (MagSafe / Qi / Apple Watch charger) and USB-C or Lightning case',
        'short_description': 'Active noise cancelling earbuds with Adaptive Audio, Transparency mode and a MagSafe charging case.',
        'highlights': "Active Noise Cancellation (up to 2x stronger than the first generation)\nAdaptive Audio and Transparency mode\nPersonalised Spatial Audio\nTouch control for volume\nUp to 30 hours of battery with the case\nDust, sweat and water resistant (IP54)",
        'extra_specs': "Water resistance: IP54 (earbuds and case)\nEar tips: XS, S, M, L\nWorks with: iPhone, iPad, Mac, Android (basic features)",
        'in_the_box': "AirPods Pro with charging case\nSilicone ear tips (XS, S, M, L)\nUSB-C charge cable\nDocumentation",
        'ai_notes': "For iPhone users who want noise cancelling and easy pairing. Works with Android as ordinary Bluetooth earbuds, but some features need an Apple device.",
    },
    {
        'match': ['amazfit gtr 4'],
        'brand': 'Amazfit', 'display': '1.43-inch AMOLED', 'os': 'Zepp OS', 'network': 'Bluetooth calling',
        'battery': 'Up to 14 days typical use',
        'camera': '', 'processor': '',
        'short_description': 'Premium smartwatch with dual-band GPS, 150+ sports modes and up to 14 days of battery.',
        'highlights': "1.43-inch HD AMOLED display\nDual-band GPS with route import\n150+ sports modes\nUp to 14 days of battery life\nBluetooth calling\n5 ATM water resistance",
        'extra_specs': "Water resistance: 5 ATM\nHealth tracking: heart rate, SpO2, sleep and stress\nCompatible with: Android and iOS (Zepp app)",
        'in_the_box': "Amazfit GTR 4 smartwatch\nMagnetic charging cable\nUser guide",
        'ai_notes': "For fitness and outdoor users who want long battery life instead of a daily-charged watch. Needs the Zepp app on the phone.",
    },
]

# Used for any other product that has no entry above (only what is true for the whole category).
CATEGORY_BOX = {
    'phone': "Handset\nUSB cable\nSIM ejector tool\nDocumentation",
    'watch': "Smartwatch\nCharging cable\nUser guide",
    'bud': "Earbuds with charging case\nUSB charging cable\nUser guide",
}
FIELDS = ['sku', 'short_description', 'highlights', 'processor', 'ram', 'storage', 'display', 'battery',
          'charging', 'camera', 'os', 'network', 'sim', 'color', 'extra_specs', 'in_the_box', 'faq',
          'ai_notes', 'brand']


def _category_box(product):
    text = f"{product.name} {product.category.name if product.category else ''}".lower()
    for key, box in CATEGORY_BOX.items():
        if key in text:
            return box
    return ''


def fill_product(product):
    """Fill empty detail fields on one product. Returns the list of field names changed."""
    name = product.name.lower()
    data = next((k for k in KNOWN if any(m in name for m in k['match'])), {})
    changed = []
    for field in FIELDS:
        value = data.get(field, '')
        if field == 'in_the_box' and not value:
            value = _category_box(product)
        if field == 'faq':
            value = COMMON_FAQ
        if value and not getattr(product, field):
            setattr(product, field, value)
            changed.append(field)
    return changed


def fill_all(dry_run=False, model=None):
    if model is None:
        from .models import Product as model
    report = []
    for product in model.objects.select_related('category'):
        changed = fill_product(product)
        if changed:
            report.append((product.name, changed))
            if not dry_run:
                product.save()
    return report
