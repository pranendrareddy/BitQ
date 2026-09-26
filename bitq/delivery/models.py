from django.db import models
from decimal import Decimal

# Create your models here.
class Customer(models.Model):
    username = models.CharField(max_length = 20)
    password = models.CharField(max_length = 20)
    email = models.CharField(max_length = 20)
    mobile = models.CharField(max_length = 10)
    address = models.CharField(max_length = 50)


class Feedback(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='feedback')
    rating = models.PositiveSmallIntegerField()
    message = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.customer.username} - {self.rating}/5'


class Restaurant(models.Model):
    name = models.CharField(max_length=100)
    picture = models.URLField(blank=True)
    photo = models.FileField(upload_to='restaurant_photos/', blank=True)
    cuisine = models.CharField(max_length=100)
    rating = models.DecimalField(max_digits=2, decimal_places=1)

    def __str__(self):
        return self.name

    @property
    def restaurant_name(self):
        return self.name

    @property
    def city(self):
        return self.cuisine

    @property
    def operating_hours(self):
        return 'Not specified'

class Item(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete = models.CASCADE, related_name = "items")
    name = models.CharField(max_length = 20)
    description = models.CharField(max_length = 200)
    price = models.FloatField()
    vegeterian = models.BooleanField(default=False)
    picture = models.URLField(max_length = 400, default='https://www.indiafilings.com/learn/wp-content/uploads/2024/08/How-to-Start-Food-Business-In-India.jpg')


class Cart(models.Model):
    customer = models.ForeignKey(Customer, on_delete = models.CASCADE, related_name = "cart")
    items = models.ManyToManyField("Item", through='CartItem', related_name="carts")

    def total_price(self):
        return sum((line.subtotal for line in self.lines.select_related('item')), Decimal('0.00'))


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='lines')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='cart_lines')
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('cart', 'item'), name='unique_item_per_cart'),
        ]

    @property
    def subtotal(self):
        return Decimal(str(self.item.price)) * self.quantity


class Order(models.Model):
    STATUS_CHOICES = [
        ('placed', 'Placed'),
        ('preparing', 'Preparing'),
        ('out_for_delivery', 'Out for delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='order_set')
    items = models.ManyToManyField(Item, through='OrderItem', related_name='orders')
    total_price = models.FloatField(default=0)
    payment_method = models.CharField(max_length=50, default='cash')
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default='placed')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.customer.username} - ₹{self.total_price}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='lines')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='order_lines')
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('order', 'item'), name='unique_item_per_order'),
        ]

    @property
    def subtotal(self):
        return Decimal(str(self.item.price)) * self.quantity