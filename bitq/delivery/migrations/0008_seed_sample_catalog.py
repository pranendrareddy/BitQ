from django.db import migrations


CATALOG = [
    {
        'name': 'Spice Harbor',
        'cuisine': 'Indian',
        'rating': '4.7',
        'picture': 'https://images.unsplash.com/photo-1585937421612-70a008356fbe?auto=format&fit=crop&w=900&q=85',
        'items': [
            ('Paneer Tikka Wrap', 'Smoky paneer, mint chutney, and crisp vegetables.', 279, True, 'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&w=800&q=85'),
            ('Butter Chicken Bowl', 'Creamy tomato curry served with fragrant rice.', 349, False, 'https://images.unsplash.com/photo-1603894584373-5ac82b2ae398?auto=format&fit=crop&w=800&q=85'),
            ('Masala Fries', 'Golden fries tossed with house spice and lime.', 149, True, 'https://images.unsplash.com/photo-1573080496219-bb080dd4f877?auto=format&fit=crop&w=800&q=85'),
        ],
    },
    {
        'name': 'Noodle Garden',
        'cuisine': 'Asian',
        'rating': '4.6',
        'picture': 'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=900&q=85',
        'items': [
            ('Chilli Noodles', 'Wok-tossed noodles with garlic, greens, and chilli.', 249, True, 'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=85'),
            ('Sesame Chicken', 'Crispy chicken glazed with sesame soy sauce.', 329, False, 'https://images.unsplash.com/photo-1525755662778-989d0524087e?auto=format&fit=crop&w=800&q=85'),
            ('Veg Dumplings', 'Steamed vegetable dumplings with ginger dip.', 199, True, 'https://images.unsplash.com/photo-1563245372-f21724e3856d?auto=format&fit=crop&w=800&q=85'),
        ],
    },
    {
        'name': 'Burger Foundry',
        'cuisine': 'Burgers',
        'rating': '4.5',
        'picture': 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=900&q=85',
        'items': [
            ('Smash Cheeseburger', 'Double-seared patty, cheddar, pickles, and sauce.', 329, False, 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=800&q=85'),
            ('Chicken Smash Burger', 'Crispy chicken, slaw, and pepper mayo.', 299, False, 'https://images.unsplash.com/photo-1606755962773-d324e0a13086?auto=format&fit=crop&w=800&q=85'),
            ('Truffle Fries', 'Crisp fries with parmesan and truffle seasoning.', 189, True, 'https://images.unsplash.com/photo-1630384060421-cb20d0e0649d?auto=format&fit=crop&w=800&q=85'),
        ],
    },
    {
        'name': 'Olive & Hearth',
        'cuisine': 'Italian',
        'rating': '4.8',
        'picture': 'https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=900&q=85',
        'items': [
            ('Margherita Pizza', 'Tomato, mozzarella, basil, and olive oil.', 329, True, 'https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=800&q=85'),
            ('Pesto Pasta', 'Basil pesto, parmesan, and toasted pine nuts.', 349, True, 'https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=800&q=85'),
            ('Garlic Focaccia', 'Warm rosemary focaccia with whipped garlic butter.', 169, True, 'https://images.unsplash.com/photo-1619531040576-f9416740661b?auto=format&fit=crop&w=800&q=85'),
        ],
    },
    {
        'name': 'Green Plate',
        'cuisine': 'Healthy',
        'rating': '4.4',
        'picture': 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=900&q=85',
        'items': [
            ('Avocado Grain Bowl', 'Avocado, grains, greens, and lemon tahini.', 329, True, 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=800&q=85'),
            ('Falafel Salad', 'Herb falafel, crunchy greens, and hummus.', 289, True, 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=800&q=85'),
            ('Mango Smoothie', 'Ripe mango blended with yogurt and a hint of lime.', 159, True, 'https://images.unsplash.com/photo-1505252585461-04db1eb84625?auto=format&fit=crop&w=800&q=85'),
        ],
    },
]


def seed_catalog(apps, schema_editor):
    Restaurant = apps.get_model('delivery', 'Restaurant')
    Item = apps.get_model('delivery', 'Item')
    database = schema_editor.connection.alias

    for entry in CATALOG:
        restaurant, _ = Restaurant.objects.using(database).get_or_create(
            name=entry['name'],
            defaults={
                'cuisine': entry['cuisine'],
                'rating': entry['rating'],
                'picture': entry['picture'],
            },
        )
        for name, description, price, vegetarian, picture in entry['items']:
            Item.objects.using(database).get_or_create(
                restaurant=restaurant,
                name=name,
                defaults={
                    'description': description,
                    'price': price,
                    'vegeterian': vegetarian,
                    'picture': picture,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0007_cartitem_alter_cart_items_orderitem_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_catalog, migrations.RunPython.noop),
    ]