from django.contrib import admin
from .models import Order, Item, OrderItem, Payment


admin.site.register(Item)
admin.site.register(OrderItem)
admin.site.register(Order)
admin.site.register(Payment)