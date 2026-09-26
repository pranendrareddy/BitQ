from django.contrib import admin

from .models import Cart, Customer, Feedback, Item, Restaurant

# Register your models here.
admin.site.register(Customer)
admin.site.register(Item)
admin.site.register(Cart)

@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
	list_display = ('name', 'picture', 'cuisine', 'rating', 'photo')
	search_fields = ('name', 'cuisine')
	fields = ('name', 'picture', 'photo', 'cuisine', 'rating')


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
	list_display = ('customer', 'rating', 'message', 'created_at')
	list_filter = ('rating', 'created_at')
	search_fields = ('customer__username', 'message')