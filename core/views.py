from django.conf import settings
from django.shortcuts import render, get_object_or_404
from .models import Item, Order, OrderItem, BillingAddress, Payment
from django.views.generic import ListView, DetailView, View
from django.shortcuts import redirect
from django.utils import timezone
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import CheckoutForm
from django_countries.fields import CountryField

import stripe
import random
import string

stripe.api_key = settings.STRIPE_SECRET_KEY


def products(request):
	context = {
		'items': Item.objects.all()
	}
	return render(request, "products.html", context)

class HomeView(ListView):
	model = Item
	paginate_by = 8
	template_name = "home.html"
	

class OrderSummaryView(LoginRequiredMixin, View):
	def get(self, *args, **kwargs):
		try:
			order = Order.objects.get(user=self.request.user, ordered = False)
			context = {
				'order': order
			}
			return render(self.request, 'order_summary.html',  context)

		except ObjectDoesNotExist:
			messages.error(self.request, "Your order does not exist")
			return redirect("/")



class ItemDetailView(DetailView):
	model = Item
	template_name = "product.html"
	

@login_required
def add_to_cart(request, slug):
	item = get_object_or_404(Item, slug=slug)
	order_item, created = OrderItem.objects.get_or_create(
		item=item,
		user=request.user,
		ordered=False)
	order_qs = Order.objects.filter(user=request.user, ordered=False)
	if order_qs.exists():
		order = order_qs[0]
		if order.items.filter(item__slug=item.slug).exists():
			order_item.quantity += 1
			order_item.save()
			messages.info(request, "This item quantity was updated")
			return redirect("core:order-summary")

		else:
			messages.info(request, "This item was added to your cart")
			order.items.add(order_item)
			return redirect("core:order-summary")
	else:
		ordered_date = timezone.now()
		order = Order.objects.create(user=request.user, ordered_date=ordered_date)
		order.items.add(order_item)
		messages.info(request, "This item was added to your cart")

	return redirect("core:order-summary")


@login_required
def remove_from_cart(request, slug):
	item = get_object_or_404(Item, slug=slug)
	order_qs = Order.objects.filter(
		user=request.user,
		ordered=False
	)
	if order_qs.exists():
		order = order_qs[0]
		if order.items.filter(item__slug=item.slug).exists():
			order_item = OrderItem.objects.filter(
				item=item,
				user=request.user,
				ordered=False
			)[0]
			order.items.remove(order_item)
			order_item.delete()
			messages.info(request, "This item was removed from your cart.")
			return redirect("core:order-summary")
		else:
			messages.info(request, "This item was not in your cart")
			return redirect("core:product", slug=slug)
	else:
		messages.info(request, "You do not have an active order")
		return redirect("core:product", slug=slug)
	
	
@login_required
def remove_single_item_from_cart(request, slug):
	item = get_object_or_404(Item, slug=slug)
	order_qs = Order.objects.filter(
		user=request.user,
		ordered=False
	)
	if order_qs.exists():
		order = order_qs[0]

		if order.items.filter(item__slug=item.slug).exists():
			order_item = OrderItem.objects.filter(
				item=item,
				user=request.user,
				ordered=False
			)[0]
			if order_item.quantity > 1:
				order_item.quantity -= 1
				order_item.save()
			else:
				order.items.remove(order_item)
			messages.info(request, "This item quantity was updated.")
			return redirect("core:order-summary")
		else:
			messages.info(request, "This item was not in your cart")
			return redirect("core:product", slug=slug)
	else:
		messages.info(request, "You do not have an active order")
		return redirect("core:product", slug=slug)



class CheckoutView(View):
	def get(self, *args, **kwargs):
		form = CheckoutForm()
		context = {
			'form': form
		}
		return render(self.request, "checkout.html", context)
	
	def post(self, *args, **kwargs):
		form = CheckoutForm(self.request.POST or None)
		try:
			order = Order.objects.get(user=self.request.user, ordered = False)
			if form.is_valid():
				street_address = form.cleaned_data.get('street_address')
				apartment_address = form.cleaned_data.get('apartment_address')
				country = form.cleaned_data.get('conutry')
				zip = form.cleaned_data.get('zip')
				# same_billing_address = form.cleaned_data.get('same_billing_address')
				# save_info = form.cleaned_data.get('save_info')
				payment_option = form.cleaned_data.get('payment_option')
				#### FIX BILLING ADDRESS
				# shipping_address = BillingAddress(
				#     user = self.request.user,
				#     street_address = street_address,
				#     apartment_address = apartment_address,
				#     country = country,
				#     zip =  zip
				# )
				# shipping_address.save()
				# order.billing_address = billing_address
				order.save()
				
				if payment_option == 'S':
					return redirect('core:payment', payment_option='stripe')
				elif payment_option == 'P':
					return redirect('core:payment', payment_option='paypal')
				else:
					messages.warning(self.request, "Invalid payment option selected")
					return redirect('core:checkout')
 
              
		except ObjectDoesNotExist:
			messages.error(self.request, "Your order does not exist")
			return redirect("core:order-summary")

		
		
class PaymentView(View):
	def get(self, *args, **kwargs):
		order = Order.objects.get(user =self.request.user, ordered = False)
		context = {
			'order': order
		}
		return render(self.request, "payment.html", context)
	
	def post(self, *args, **kwargs):
		order = Order.objects.get(user =self.request.user, ordered = False)
		token = 'tok_visa'
		amount = int(order.get_total() * 100)
		
		try:
			charge = stripe.Charge.create(
				amount=amount,  
				currency="usd",
				source=token
					)

			payment = Payment()
			payment.stripe_charge_id = charge['id']
			payment.amount = order.get_total() 
			payment.save()
		
			order.ordered =True
			order.payment = payment
			order.save() 
			messages.success(self.request, "Your order was successful!")
			return redirect("/")

		except stripe.error.CardError as e:
			body = e.json_body()
			er = body.get('error', {})
			messages.warning(self.request, f"{err.get('message')}")
			return redirect("/")			

   
  