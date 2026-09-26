from functools import wraps
from hmac import compare_digest

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
import razorpay

from .forms import MenuItemForm
from .models import Cart, CartItem, Customer, Feedback, Item, Order, OrderItem, Restaurant


# Create your views here.
def index(request):
    return render(request, 'delivery/index.html')


def health_check(request):
    return HttpResponse('ok', content_type='text/plain')


def customer_home(request, username):
    customer = get_object_or_404(Customer, username=username)
    return render(request, 'Customer_Home.html', customer_home_context(customer))


def open_sighup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Your account was created successfully.')
            return redirect('index')
    else:
        form = UserCreationForm()

    return render(request, 'delivery/SignUP.html', {'form': form})


def open_sighin(request):
    return render(request, 'delivery/singin.html')


def dashboard_context():
    return {
        'restaurant_count': Restaurant.objects.count(),
        'customer_count': Customer.objects.exclude(username='admin').count(),
        'recent_restaurants': Restaurant.objects.order_by('-id')[:5],
        'feedback_count': Feedback.objects.count(),
        'recent_feedback': Feedback.objects.select_related('customer')[:5],
        'order_count': Order.objects.count(),
        'recent_orders': Order.objects.select_related('customer').prefetch_related('lines__item')[:5],
        'status_choices': Order.STATUS_CHOICES,
    }


def admin_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.session.get('is_admin'):
            return redirect('admin_access')
        return view(request, *args, **kwargs)

    return wrapped


@require_http_methods(['GET', 'POST'])
def admin_access(request):
    if request.session.get('is_admin'):
        return redirect('dashboard')

    error = None
    if request.method == 'POST':
        access_code = request.POST.get('access_code', '')
        if compare_digest(access_code, settings.ADMIN_PANEL_ACCESS_CODE):
            request.session.cycle_key()
            request.session['is_admin'] = True
            request.session.pop('customer_id', None)
            return redirect('dashboard')
        error = 'Incorrect admin password. Please try again.'

    return render(request, 'delivery/admin_access.html', {'error': error})


@admin_required
def dashboard(request):
    return render(request, 'delivery/admin_home.html', dashboard_context())


def logout_view(request):
    request.session.flush()
    return redirect('signin')


def customer_home_context(customer, feedback_sent=False):
    cart_count = CartItem.objects.filter(cart__customer=customer).aggregate(total=Sum('quantity'))['total'] or 0
    return {
        'username': customer.username,
        'restaurantList': Restaurant.objects.annotate(menu_item_count=Count('items')).order_by('name'),
        'cart_count': cart_count,
        'feedback_sent': feedback_sent,
    }


def signup(request):
    if request.method != 'POST':
        return render(request, 'delivery/SignUP.html')

    username = request.POST.get('username')
    password = request.POST.get('password') or request.POST.get('password1')
    email = request.POST.get('email')
    mobile = request.POST.get('mobile')
    address = request.POST.get('address')

    if Customer.objects.filter(username=username).exists():
        return HttpResponse('Duplicate username!')

    Customer.objects.create(
        username=username,
        password=password,
        email=email,
        mobile=mobile,
        address=address,
    )
    return redirect('signin')

def signin(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        try:
            Customer.objects.get(username=username, password=password)
            if username == 'admin':
                request.session['is_admin'] = False
                return redirect('admin_access')
            else:
                request.session['is_admin'] = False
                customer = Customer.objects.get(username=username)
                request.session['customer_id'] = customer.id
                return render(
                    request,
                    'Customer_Home.html',
                    customer_home_context(customer),
                )

        except Customer.DoesNotExist:
            messages.error(request, 'Invalid username or password. Please try again.')
            return render(request, 'delivery/singin.html')

    return render(request, 'delivery/singin.html')


def submit_feedback(request):
    customer_id = request.session.get('customer_id')
    if not customer_id or request.method != 'POST':
        return redirect('signin')

    message = request.POST.get('message', '').strip()
    rating = request.POST.get('rating', '').strip()

    try:
        rating_value = int(rating)
    except (TypeError, ValueError):
        rating_value = 0

    if message and 1 <= rating_value <= 5:
        Feedback.objects.create(
            customer_id=customer_id,
            rating=rating_value,
            message=message,
        )

    customer = get_object_or_404(Customer, id=customer_id)
    return render(
        request,
        'Customer_Home.html',
        customer_home_context(customer, bool(message and 1 <= rating_value <= 5)),
    )

@admin_required
def open_add_restaurant(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        picture = request.POST.get('picture', '').strip()
        photo = request.FILES.get('photo')
        cuisine = request.POST.get('cuisine', '').strip()
        rating = request.POST.get('rating', '').strip()

        if not name or not cuisine or not rating:
            return render(
                request,
                'delivery/add_restaurant.html',
                {'error': 'Name, cuisine, and rating are required.'},
            )

        try:
            rating_value = float(rating)
        except ValueError:
            return render(
                request,
                'delivery/add_restaurant.html',
                {'error': 'Rating must be a number between 0 and 5.'},
            )

        if not 0 <= rating_value <= 5:
            return render(
                request,
                'delivery/add_restaurant.html',
                {'error': 'Rating must be a number between 0 and 5.'},
            )

        Restaurant.objects.create(
            name=name,
            picture=picture,
            photo=photo,
            cuisine=cuisine,
            rating=rating_value,
        )
        return redirect('restaurant_list')

    return render(request, 'delivery/add_restaurant.html')


def restaurant_list(request):
    search_query = (request.GET.get('q') or '').strip()
    restaurants = Restaurant.objects.order_by('name')

    if search_query:
        restaurants = restaurants.filter(
            Q(name__icontains=search_query) | Q(cuisine__icontains=search_query)
        )

    return render(
        request,
        'delivery/show.resturant.html',
        {
            'restaurants': restaurants,
            'is_admin': request.session.get('is_admin', False),
            'search_query': search_query,
        },
    )


def restaurant_detail(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    return render(
        request,
        'delivery/restaurant_detail.html',
        {
            'restaurant': restaurant,
            'is_admin': request.session.get('is_admin', False),
        },
    )


@admin_required
def update_restaurant(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        picture = request.POST.get('picture', '').strip()
        cuisine = request.POST.get('cuisine', '').strip()
        rating = request.POST.get('rating', '').strip()

        if not name or not cuisine or not rating:
            return render(
                request,
                'delivery/update_restaurant.html',
                {'restaurant': restaurant, 'error': 'Name, cuisine, and rating are required.'},
            )

        try:
            rating_value = float(rating)
        except ValueError:
            return render(
                request,
                'delivery/update_restaurant.html',
                {'restaurant': restaurant, 'error': 'Rating must be a number between 0 and 5.'},
            )

        if not 0 <= rating_value <= 5:
            return render(
                request,
                'delivery/update_restaurant.html',
                {'restaurant': restaurant, 'error': 'Rating must be a number between 0 and 5.'},
            )

        restaurant.name = name
        restaurant.picture = picture
        restaurant.cuisine = cuisine
        restaurant.rating = rating_value
        restaurant.save()
        return redirect('restaurant_list')

    return render(request, 'delivery/update_restaurant.html', {'restaurant': restaurant})


@admin_required
def delete_restaurant(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    restaurant.delete()
    return redirect('restaurant_list')


@admin_required
def update_menu(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    item_form = MenuItemForm()
    editing_item = None
    edit_form = None

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            item_form = MenuItemForm(request.POST)
            if item_form.is_valid():
                item = item_form.save(commit=False)
                item.restaurant = restaurant
                item.save()
                messages.success(request, f'{item.name} was added to {restaurant.name}.')
                return redirect('update_menu', restaurant_id=restaurant.id)
        elif action == 'update':
            editing_item = get_object_or_404(
                Item,
                id=request.POST.get('item_id'),
                restaurant=restaurant,
            )
            edit_form = MenuItemForm(request.POST, instance=editing_item, prefix='edit')
            if edit_form.is_valid():
                edit_form.save()
                messages.success(request, 'Menu item updated.')
                return redirect('update_menu', restaurant_id=restaurant.id)
        elif action == 'delete':
            item = get_object_or_404(
                Item,
                id=request.POST.get('item_id'),
                restaurant=restaurant,
            )
            item.delete()
            messages.success(request, 'Menu item removed.')
            return redirect('update_menu', restaurant_id=restaurant.id)
        else:
            return HttpResponseBadRequest('Unsupported menu action.')
    elif request.GET.get('edit'):
        editing_item = get_object_or_404(
            Item,
            id=request.GET['edit'],
            restaurant=restaurant,
        )
        edit_form = MenuItemForm(instance=editing_item, prefix='edit')

    return render(request, 'delivery/manage_menu.html', {
        'restaurant': restaurant,
        'items': restaurant.items.order_by('name'),
        'item_form': item_form,
        'editing_item': editing_item,
        'edit_form': edit_form,
    })


@admin_required
@require_POST
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    new_status = request.POST.get('status', '')
    valid_statuses = {choice[0] for choice in Order.STATUS_CHOICES}
    if new_status not in valid_statuses:
        return HttpResponseBadRequest('Unsupported order status.')

    order.status = new_status
    order.save(update_fields=('status',))
    messages.success(request, f'Order #{order.id} status updated to {order.get_status_display()}.')
    destination = 'dashboard' if request.POST.get('next') == 'dashboard' else 'admin_orders'
    return redirect(destination)


@admin_required
def admin_orders(request):
    return render(request, 'delivery/admin_orders.html', {
        'orders': Order.objects.select_related('customer').prefetch_related('lines__item'),
        'status_choices': Order.STATUS_CHOICES,
    })


def view_menu(request, restaurant_id, username):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    items = restaurant.items.order_by('name')
    cart = Cart.objects.filter(customer__username=username).first()
    cart_count = cart.lines.aggregate(total=Sum('quantity'))['total'] if cart else 0
    return render(
        request,
        'customer_menu.html',
        {'username': username, 'restaurant': restaurant, 'itemlist': items, 'cart_count': cart_count or 0},
    )

@require_POST
def add_to_cart(request, item_id, username):
    item = get_object_or_404(Item, id=item_id)
    customer = get_object_or_404(Customer, username=username)

    cart, _ = Cart.objects.get_or_create(customer=customer)
    line, created = CartItem.objects.get_or_create(cart=cart, item=item)
    if not created:
        line.quantity += 1
        line.save(update_fields=('quantity',))

    return redirect('show_cart', username=username)


def show_cart(request, username):
    customer = get_object_or_404(Customer, username=username)
    cart = Cart.objects.filter(customer=customer).first()
    cart_items = list(cart.lines.select_related('item', 'item__restaurant')) if cart else []
    cart_count = sum(line.quantity for line in cart_items)
    total_price = cart.total_price() if cart else 0

    return render(request, 'delivery/cart.html', {
        'cart_items': cart_items,
        'itemList': cart_items,
        'total_price': total_price,
        'cart_count': cart_count,
        'username': username,
    })


@require_POST
def update_cart_quantity(request, username, item_id, action):
    customer = get_object_or_404(Customer, username=username)
    line = get_object_or_404(CartItem, cart__customer=customer, item_id=item_id)
    if action == 'increase':
        line.quantity += 1
    elif action == 'decrease':
        line.quantity = max(1, line.quantity - 1)
    else:
        return HttpResponseBadRequest('Unsupported quantity action.')
    line.save(update_fields=('quantity',))
    return redirect('show_cart', username=username)


@require_POST
def remove_from_cart(request, username, item_id):
    customer = get_object_or_404(Customer, username=username)
    CartItem.objects.filter(cart__customer=customer, item_id=item_id).delete()
    return redirect('show_cart', username=username)

def checkout(request, username):
    customer = get_object_or_404(Customer, username=username)
    cart = Cart.objects.filter(customer=customer).first()
    cart_items = list(cart.lines.select_related('item', 'item__restaurant')) if cart else []
    total_price = cart.total_price() if cart else 0

    if total_price == 0:
        return render(request, 'delivery/CheckOut.html', {
            'error': 'Your cart is empty!',
            'username': username,
        })

    if request.method == 'POST':
        method = request.POST.get('payment_method', 'cash')
        if method == 'cash':
            return _complete_order(request, customer, cart, total_price, method)

        if method != 'razorpay':
            return render(request, 'delivery/CheckOut.html', {
                'username': username,
                'cart_items': cart_items,
                'total_price': total_price,
                'razorpay_configured': bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET),
                'selected_method': 'razorpay',
                'error': 'Choose cash on delivery or secure online payment.',
            }, status=400)

        if method == 'razorpay':
            if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
                return render(request, 'delivery/CheckOut.html', {
                    'username': username,
                    'cart_items': cart_items,
                    'total_price': total_price,
                    'razorpay_configured': False,
                    'selected_method': 'cash',
                    'error': 'Online payment is not configured on this deployment. Cash on delivery is available.',
                }, status=503)

            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            order_data = {
                'amount': int(total_price * 100),
                'currency': 'INR',
                'payment_capture': '1',
            }
            order = client.order.create(data=order_data)
            request.session['pending_razorpay_order_id'] = order['id']
            request.session['last_payment_total'] = str(total_price)
            return render(request, 'delivery/CheckOut.html', {
                'username': username,
                'cart_items': cart_items,
                'total_price': total_price,
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'order_id': order['id'],
                'amount_paise': order_data['amount'],
                'selected_method': method,
                'razorpay_configured': True,
                'customer_email': customer.email,
                'customer_mobile': customer.mobile,
            })

    return render(request, 'delivery/CheckOut.html', {
        'username': username,
        'cart_items': cart_items,
        'total_price': total_price,
        'razorpay_configured': bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET),
        'selected_method': 'cash',
    })


def _complete_order(request, customer, cart, total_amount, payment_method):
    cart_lines = list(cart.lines.select_related('item')) if cart else []
    order = Order.objects.create(
        customer=customer,
        total_price=total_amount,
        payment_method=payment_method,
    )
    OrderItem.objects.bulk_create([
        OrderItem(order=order, item=line.item, quantity=line.quantity)
        for line in cart_lines
    ])
    order_lines = list(order.lines.select_related('item'))
    if cart:
        cart.items.clear()

    method_label = 'Cash on Delivery' if payment_method == 'cash' else 'Razorpay Payment'
    history = Order.objects.filter(customer=customer)[:5]
    return render(request, 'delivery/payment_success.html', {
        'username': customer.username,
        'payment_method': method_label,
        'total_amount': total_amount,
        'items': [line.item for line in order_lines],
        'order_lines': order_lines,
        'history': history,
    })


@require_POST
def payment_success(request, username, payment_method):
    customer = get_object_or_404(Customer, username=username)
    expected_order_id = request.session.get('pending_razorpay_order_id')
    payment_id = request.POST.get('razorpay_payment_id')
    order_id = request.POST.get('razorpay_order_id')
    signature = request.POST.get('razorpay_signature')

    if payment_method != 'razorpay' or not expected_order_id or order_id != expected_order_id:
        return redirect('checkout', username=username)

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature,
        })
    except razorpay.errors.SignatureVerificationError:
        return render(request, 'delivery/CheckOut.html', {
            'username': username,
            'error': 'Online payment could not be verified. Please try again.',
            'selected_method': 'razorpay',
        }, status=400)

    cart = Cart.objects.filter(customer=customer).first()
    total_amount = request.session.pop('last_payment_total', '0.00')
    request.session.pop('pending_razorpay_order_id', None)
    return _complete_order(request, customer, cart, total_amount, payment_method)


def order_history(request, username):
    customer = get_object_or_404(Customer, username=username)
    orders = Order.objects.filter(customer=customer).prefetch_related('lines__item')
    return render(request, 'delivery/order_history.html', {
        'username': username,
        'orders': orders,
    })