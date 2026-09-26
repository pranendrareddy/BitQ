from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from razorpay.errors import SignatureVerificationError
from unittest.mock import patch

from .models import Customer, Feedback, Item, Order, Restaurant


class SignupTests(TestCase):
	def test_signup_page_renders(self):
		response = self.client.get('/signup/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'name="username"')

	def test_signup_creates_user(self):
		response = self.client.post('/signup/', {
			'username': 'newuser',
			'email': 'newuser@example.com',
			'password': 'Strong-password-123',
			'mobile': '1234567890',
			'address': 'Test address',
		})

		self.assertRedirects(response, '/signin/')
		self.assertTrue(Customer.objects.filter(username='newuser').exists())

	def test_customer_signin_shows_welcome_heading(self):
		Customer.objects.create(
			username='customer',
			password='customer-password',
			email='customer@example.com',
			mobile='1234567890',
			address='Customer address',
		)

		response = self.client.post('/signin/', {
			'username': 'customer',
			'password': 'customer-password',
		})

		self.assertContains(response, 'Welcome Customer')
		self.assertNotContains(response, '### elcome Customer!')

	def test_customer_can_submit_feedback(self):
		customer = Customer.objects.create(
			username='feedback-user',
			password='customer-password',
			email='feedback@example.com',
			mobile='1234567890',
			address='Customer address',
		)
		self.client.post('/signin/', {
			'username': 'feedback-user',
			'password': 'customer-password',
		})

		response = self.client.post('/feedback/', {
			'rating': '5',
			'message': 'Great restaurant choices.',
		})

		self.assertEqual(response.status_code, 200)
		self.assertTrue(Feedback.objects.filter(customer=customer, rating=5).exists())
		self.assertContains(response, 'Thanks, your feedback was sent')


class RestaurantTests(TestCase):
	def setUp(self):
		self.restaurant = Restaurant.objects.create(
			name='Visibility Kitchen',
			picture='https://example.com/kitchen.jpg',
			cuisine='Italian',
			rating='4.5',
		)
		Customer.objects.create(
			username='admin',
			password='admin-password',
			email='admin@example.com',
			mobile='1234567890',
			address='Admin address',
		)
		Customer.objects.create(
			username='customer',
			password='customer-password',
			email='customer@example.com',
			mobile='1234567890',
			address='Customer address',
		)

	def unlock_admin(self):
		response = self.client.post('/admin-access/', {'access_code': '819733'})
		self.assertRedirects(response, '/dashboard/')

	def test_admin_access_requires_correct_password(self):
		response = self.client.get('/admin-access/')
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'type="password"')

		response = self.client.post('/admin-access/', {'access_code': '000000'})
		self.assertContains(response, 'Incorrect admin password', status_code=200)
		self.assertRedirects(self.client.get('/dashboard/'), '/admin-access/')

		self.unlock_admin()
		self.assertEqual(self.client.get('/dashboard/').status_code, 200)

	def test_admin_signin_also_requires_access_code(self):
		response = self.client.post('/signin/', {
			'username': 'admin',
			'password': 'admin-password',
		})
		self.assertRedirects(response, '/admin-access/')
		self.assertRedirects(self.client.get('/dashboard/'), '/admin-access/')

	def test_restaurant_write_urls_require_admin_access_code(self):
		response = self.client.post('/open_add_restaurant/', {
			'name': 'Blocked Kitchen',
			'cuisine': 'Italian',
			'rating': '4.5',
		})

		self.assertRedirects(response, '/admin-access/')
		self.assertFalse(Restaurant.objects.filter(name='Blocked Kitchen').exists())
		self.assertRedirects(self.client.get(f'/restaurants/{self.restaurant.id}/update/'), '/admin-access/')

	def test_admin_can_create_update_and_delete_menu_items(self):
		self.unlock_admin()
		response = self.client.get(f'/restaurants/{self.restaurant.id}/menu/')
		self.assertContains(response, 'Add a menu item')

		response = self.client.post(f'/restaurants/{self.restaurant.id}/menu/', {
			'action': 'add',
			'name': 'Lemon Pasta',
			'description': 'Lemon, herbs, and parmesan.',
			'price': '199.50',
			'vegeterian': 'on',
			'picture': '',
		})
		self.assertRedirects(response, f'/restaurants/{self.restaurant.id}/menu/')
		item = Item.objects.get(restaurant=self.restaurant, name='Lemon Pasta')
		self.assertEqual(item.price, 199.5)
		self.assertTrue(item.vegeterian)

		response = self.client.post(f'/restaurants/{self.restaurant.id}/menu/', {
			'action': 'update',
			'item_id': item.id,
			'edit-name': 'Lemon Herb Pasta',
			'edit-description': 'Fresh lemon, herbs, and parmesan.',
			'edit-price': '219.00',
			'edit-picture': item.picture,
		})
		self.assertRedirects(response, f'/restaurants/{self.restaurant.id}/menu/')
		item.refresh_from_db()
		self.assertEqual(item.name, 'Lemon Herb Pasta')
		self.assertEqual(item.price, 219.0)
		self.assertFalse(item.vegeterian)

		response = self.client.post(f'/restaurants/{self.restaurant.id}/menu/', {
			'action': 'delete',
			'item_id': item.id,
		})
		self.assertRedirects(response, f'/restaurants/{self.restaurant.id}/menu/')
		self.assertFalse(Item.objects.filter(id=item.id).exists())

	def test_admin_can_update_order_status_seen_in_order_history(self):
		customer = Customer.objects.get(username='customer')
		order = Order.objects.create(customer=customer, total_price=250, payment_method='cash')
		item = Item.objects.create(restaurant=self.restaurant, name='Herb Bowl', description='Fresh herbs.', price=250)
		order.items.add(item)
		self.unlock_admin()

		response = self.client.get('/manage/orders/')
		self.assertContains(response, f'Order #{order.id}')
		self.assertContains(response, 'Placed')

		response = self.client.post(f'/manage/orders/{order.id}/status/', {
			'status': 'out_for_delivery',
			'next': 'admin_orders',
		})
		self.assertRedirects(response, '/manage/orders/')
		order.refresh_from_db()
		self.assertEqual(order.status, 'out_for_delivery')

		response = self.client.get('/order_history/customer/')
		self.assertContains(response, 'Out for delivery')
		self.assertContains(response, 'Herb Bowl × 1')
		self.assertContains(self.client.get('/dashboard/'), 'Out for delivery')

		response = self.client.post(f'/manage/orders/{order.id}/status/', {'status': 'unknown'})
		self.assertEqual(response.status_code, 400)
		order.refresh_from_db()
		self.assertEqual(order.status, 'out_for_delivery')

	def test_admin_sees_restaurant_management_controls(self):
		self.unlock_admin()

		response = self.client.get('/restaurants/')

		self.assertContains(response, 'Add Restaurant')
		self.assertContains(response, 'Update Restaurant Info')
		self.assertContains(response, 'Delete Restaurant')

	def test_admin_dashboard_shows_live_summary_and_feedback_area(self):
		self.unlock_admin()
		response = self.client.get('/dashboard/')

		self.assertContains(response, 'Recent restaurants')
		self.assertContains(response, 'Registered customers')
		self.assertContains(response, 'Customer feedback')
		self.assertContains(response, 'Visibility Kitchen')

	def test_admin_dashboard_has_dedicated_route(self):
		self.unlock_admin()

		response = self.client.get('/dashboard/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'BitQ')
		self.assertContains(response, 'Visibility Kitchen')

	def test_dashboard_requires_admin_session(self):
		response = self.client.get('/dashboard/')

		self.assertRedirects(response, '/admin-access/')

	def test_logout_clears_admin_session(self):
		self.unlock_admin()

		response = self.client.get('/logout/')

		self.assertRedirects(response, '/signin/')
		self.assertRedirects(self.client.get('/dashboard/'), '/admin-access/')

	def test_admin_dashboard_shows_recent_feedback(self):
		Feedback.objects.create(
			customer=Customer.objects.get(username='customer'),
			rating=4,
			message='Fast and friendly service.',
		)

		self.unlock_admin()
		response = self.client.get('/dashboard/')

		self.assertContains(response, 'Fast and friendly service.')
		self.assertContains(response, '1 received')

	def test_customer_does_not_see_restaurant_management_controls(self):
		self.client.post('/signin/', {'username': 'customer', 'password': 'customer-password'})

		response = self.client.get('/restaurants/')

		self.assertNotContains(response, 'Add Restaurant')
		self.assertNotContains(response, 'Update Restaurant Info')
		self.assertNotContains(response, 'Delete Restaurant')

	def test_add_restaurant_page_renders(self):
		self.unlock_admin()
		response = self.client.get('/open_add_restaurant/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'name="name"')

	def test_add_restaurant_creates_restaurant(self):
		self.unlock_admin()
		response = self.client.post('/open_add_restaurant/', {
			'name': 'Test Kitchen',
			'picture': 'https://example.com/kitchen.jpg',
			'cuisine': 'Italian',
			'rating': '4.5',
		})

		self.assertRedirects(response, '/restaurants/')
		restaurant = Restaurant.objects.get(name='Test Kitchen')
		self.assertEqual(restaurant.picture, 'https://example.com/kitchen.jpg')
		self.assertEqual(restaurant.cuisine, 'Italian')
		self.assertEqual(restaurant.rating, 4.5)

	def test_restaurant_list_shows_details(self):
		Restaurant.objects.create(
			name='Test Kitchen',
			picture='https://example.com/kitchen.jpg',
			cuisine='Italian',
			rating='4.5',
		)

		response = self.client.get('/restaurants/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Test Kitchen')
		self.assertContains(response, 'Italian')
		self.assertContains(response, '4.5')

	def test_add_restaurant_uploads_photo(self):
		self.unlock_admin()
		photo = SimpleUploadedFile(
			'restaurant.jpg',
			b'fake image data',
			content_type='image/jpeg',
		)

		response = self.client.post('/open_add_restaurant/', {
			'name': 'Photo Kitchen',
			'cuisine': 'Indian',
			'rating': '4.0',
			'photo': photo,
		})

		self.assertRedirects(response, '/restaurants/')
		restaurant = Restaurant.objects.get(name='Photo Kitchen')
		self.assertTrue(restaurant.photo.name.startswith('restaurant_photos/'))
		self.assertTrue(restaurant.photo.name.endswith('.jpg'))

	def test_update_restaurant_post_redirects_back_to_list(self):
		self.unlock_admin()
		restaurant = Restaurant.objects.create(
			name='Old Name',
			picture='https://example.com/old.jpg',
			cuisine='Italian',
			rating='3.5',
		)

		response = self.client.post(f'/restaurants/{restaurant.id}/update/', {
			'name': 'New Name',
			'picture': 'https://example.com/new.jpg',
			'cuisine': 'Mexican',
			'rating': '4.8',
		})

		self.assertRedirects(response, '/restaurants/')
		restaurant.refresh_from_db()
		self.assertEqual(restaurant.name, 'New Name')
		self.assertEqual(restaurant.cuisine, 'Mexican')
		self.assertEqual(float(restaurant.rating), 4.8)

	def test_restaurant_detail_page_renders(self):
		restaurant = Restaurant.objects.create(
			name='Detail Kitchen',
			picture='https://example.com/detail.jpg',
			cuisine='French',
			rating='4.9',
		)

		response = self.client.get(f'/restaurants/{restaurant.id}/view/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Detail Kitchen')
		self.assertContains(response, 'French')
		self.assertContains(response, '4.9')

	def test_restaurant_list_search_filters_results(self):
		Restaurant.objects.create(
			name='Italian Corner',
			picture='https://example.com/italian.jpg',
			cuisine='Italian',
			rating='4.6',
		)
		Restaurant.objects.create(
			name='Spice Route',
			picture='https://example.com/spice.jpg',
			cuisine='Indian',
			rating='4.2',
		)

		response = self.client.get('/restaurants/?q=Italian')

		self.assertContains(response, 'Italian Corner')
		self.assertNotContains(response, 'Spice Route')

	def test_customer_can_view_menu_items(self):
		restaurant = Restaurant.objects.create(
			name='Detail Kitchen',
			picture='https://example.com/detail.jpg',
			cuisine='French',
			rating='4.9',
		)
		Item.objects.create(
			restaurant=restaurant,
			name='Paneer Bowl',
			description='Healthy bowl with grilled vegetables.',
			price=250.0,
			vegeterian=True,
		)

		response = self.client.get(f'/view_menu/{restaurant.id}/customer/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Paneer Bowl')
		self.assertContains(response, 'Add to cart')
		self.assertContains(response, 'Vegetarian only')

	def test_customer_home_shows_sample_restaurants_and_navigation(self):
		response = self.client.post('/signin/', {
			'username': 'customer',
			'password': 'customer-password',
		})

		self.assertContains(response, 'Spice Harbor')
		self.assertContains(response, 'Noodle Garden')
		self.assertContains(response, 'Cart (0)')
		self.assertContains(response, '>Orders</a>')

	def test_add_to_cart_posts_item_and_shows_correct_price(self):
		customer = Customer.objects.create(
			username='cart-user',
			password='password',
			email='cart@example.com',
			mobile='1234567890',
			address='Cart street',
		)
		item = Item.objects.create(restaurant=self.restaurant, name='Taco Plate', description='Loaded taco platter.', price=320.0)

		response = self.client.get(f'/add_to_cart/{item.id}/cart-user/')
		self.assertEqual(response.status_code, 405)
		self.assertFalse(customer.cart.exists())

		response = self.client.post(f'/add_to_cart/{item.id}/cart-user/')
		self.assertRedirects(response, '/show_cart/cart-user')
		self.client.post(f'/add_to_cart/{item.id}/cart-user/')
		response = self.client.get('/show_cart/cart-user')

		self.assertContains(response, 'Taco Plate')
		self.assertContains(response, '₹640.00')
		self.assertEqual(customer.cart.get().total_price(), 640)
		self.assertEqual(customer.cart.get().lines.get(item=item).quantity, 2)

		self.client.post(f'/cart/cart-user/item/{item.id}/decrease/')
		self.assertEqual(customer.cart.get().lines.get(item=item).quantity, 1)
		self.client.post(f'/cart/cart-user/remove/{item.id}/')
		response = self.client.get('/show_cart/cart-user')
		self.assertContains(response, 'Your cart is empty')
		self.assertNotContains(response, 'Proceed to checkout')

	def test_cash_checkout_creates_order_and_order_history_shows_it(self):
		customer = Customer.objects.create(
			username='history-user',
			password='password',
			email='history@example.com',
			mobile='1234567890',
			address='History street',
		)
		item = Item.objects.create(restaurant=self.restaurant, name='Taco Plate', description='Loaded taco platter.', price=320.0)
		cart = customer.cart.create()
		cart.items.add(item)

		response = self.client.post('/checkout/history-user/', {'payment_method': 'cash'})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Payment Successful')
		self.assertContains(response, 'Taco Plate')
		order = Order.objects.get(customer=customer)
		self.assertEqual(order.total_price, 320)
		self.assertEqual(order.payment_method, 'cash')
		self.assertFalse(cart.items.exists())

		response = self.client.get('/order_history/history-user/')
		self.assertContains(response, 'Taco Plate')

	@patch('delivery.views.razorpay.Client')
	@override_settings(RAZORPAY_KEY_ID='test_key', RAZORPAY_KEY_SECRET='test_secret')
	def test_razorpay_checkout_uses_paise_and_verifies_callback(self, razorpay_client):
		customer = Customer.objects.create(
			username='online-user',
			password='password',
			email='online@example.com',
			mobile='1234567890',
			address='Online street',
		)
		item = Item.objects.create(restaurant=self.restaurant, name='Noodle Bowl', description='Fresh noodles.', price=125.50)
		cart = customer.cart.create()
		cart.items.add(item)
		razorpay_client.return_value.order.create.return_value = {'id': 'order_test_123'}

		response = self.client.post('/checkout/online-user/', {'payment_method': 'razorpay'})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '"amount": 12550')
		self.assertFalse(Order.objects.filter(customer=customer).exists())
		self.assertEqual(razorpay_client.return_value.order.create.call_args.kwargs['data']['amount'], 12550)

		response = self.client.post('/payment_success/online-user/razorpay/', {
			'razorpay_payment_id': 'pay_test_123',
			'razorpay_order_id': 'order_test_123',
			'razorpay_signature': 'test_signature',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Payment Successful')
		self.assertTrue(Order.objects.filter(customer=customer, payment_method='razorpay').exists())
		razorpay_client.return_value.utility.verify_payment_signature.assert_called_once()

	def test_online_checkout_is_disabled_without_razorpay_credentials(self):
		customer = Customer.objects.create(
			username='cash-only-user',
			password='password',
			email='cash-only@example.com',
			mobile='1234567890',
			address='Cash street',
		)
		item = Item.objects.create(restaurant=self.restaurant, name='Market Salad', description='Greens and herbs.', price=190)
		cart = customer.cart.create()
		cart.items.add(item)

		response = self.client.post('/checkout/cash-only-user/', {'payment_method': 'razorpay'})

		self.assertEqual(response.status_code, 503)
		self.assertContains(response, 'Online payment is not configured', status_code=503)
		self.assertFalse(Order.objects.filter(customer=customer).exists())

	@patch('delivery.views.razorpay.Client')
	@override_settings(RAZORPAY_KEY_ID='test_key', RAZORPAY_KEY_SECRET='test_secret')
	def test_invalid_razorpay_signature_does_not_create_order(self, razorpay_client):
		customer = Customer.objects.create(
			username='invalid-payment-user',
			password='password',
			email='invalid-payment@example.com',
			mobile='1234567890',
			address='Online street',
		)
		item = Item.objects.create(restaurant=self.restaurant, name='Noodle Bowl', description='Fresh noodles.', price=125.50)
		cart = customer.cart.create()
		cart.items.add(item)
		razorpay_client.return_value.order.create.return_value = {'id': 'order_test_invalid'}
		razorpay_client.return_value.utility.verify_payment_signature.side_effect = SignatureVerificationError('invalid signature')
		self.client.post('/checkout/invalid-payment-user/', {'payment_method': 'razorpay'})

		response = self.client.post('/payment_success/invalid-payment-user/razorpay/', {
			'razorpay_payment_id': 'pay_test_invalid',
			'razorpay_order_id': 'order_test_invalid',
			'razorpay_signature': 'invalid_signature',
		})

		self.assertEqual(response.status_code, 400)
		self.assertContains(response, 'Online payment could not be verified', status_code=400)
		self.assertFalse(Order.objects.filter(customer=customer).exists())
