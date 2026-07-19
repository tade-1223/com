from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Product


class Cart:
    SESSION_KEY = 'cart'

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(self.SESSION_KEY)
        if cart is None:
            cart = self.session[self.SESSION_KEY] = {}
        self.cart = cart

    def add(self, product, quantity=1, override_quantity=False):
        product_id = str(product.id)
        if product_id not in self.cart:
            self.cart[product_id] = {
                'name': product.name,
                'quantity': 0,
                'price': str(product.price),
                'slug': product.slug,
            }
        if override_quantity:
            self.cart[product_id]['quantity'] = quantity
        else:
            self.cart[product_id]['quantity'] += quantity
        self.save()

    def remove(self, product):
        product_id = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def set_quantity(self, product_id, quantity):
        if str(product_id) in self.cart:
            if quantity > 0:
                self.cart[str(product_id)]['quantity'] = quantity
            else:
                del self.cart[str(product_id)]
            self.save()

    def clear(self):
        self.session[self.SESSION_KEY] = {}
        self.save()

    def save(self):
        self.session.modified = True

    def __iter__(self):
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        cart = self.cart.copy()
        for product in products:
            item = cart[str(product.id)]
            item['product'] = product
            item['price'] = Decimal(item['price'])
            item['total_price'] = item['price'] * item['quantity']
            yield item

    def __len__(self):
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self):
        return sum(Decimal(item['price']) * item['quantity'] for item in self.cart.values())


def product_list(request):
    products = Product.objects.filter(available=True)
    return render(request, 'store/product_list.html', {'products': products})


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, available=True)
    return render(request, 'store/product_detail.html', {'product': product})


@require_POST
def cart_add(request, slug):
    product = get_object_or_404(Product, slug=slug, available=True)
    quantity = request.POST.get('quantity', '1')
    try:
        quantity = int(quantity)
    except ValueError:
        quantity = 1
    cart = Cart(request)
    cart.add(product=product, quantity=quantity)
    messages.success(request, f'Added {product.name} to your cart.')
    return redirect('store:cart_detail')


def cart_detail(request):
    cart = Cart(request)
    if request.method == 'POST':
        for product_id in list(cart.cart.keys()):
            quantity = request.POST.get(f'quantity_{product_id}')
            if quantity is None:
                continue
            try:
                quantity = int(quantity)
            except ValueError:
                quantity = 1
            cart.set_quantity(product_id, quantity)
        messages.success(request, 'Cart updated successfully.')
        return redirect('store:cart_detail')

    return render(request, 'store/cart.html', {'cart': cart})


def cart_remove(request, slug):
    product = get_object_or_404(Product, slug=slug)
    cart = Cart(request)
    cart.remove(product)
    messages.success(request, f'Removed {product.name} from your cart.')
    return redirect('store:cart_detail')


def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.info(request, 'Your cart is empty. Add products before checking out.')
        return redirect('store:product_list')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()

        if not name or not phone or not address:
            messages.error(request, 'Please complete all checkout fields.')
        else:
            order_data = {
                'name': name,
                'phone': phone,
                'address': address,
                'total': cart.get_total_price(),
            }
            cart.clear()
            return render(request, 'store/order_complete.html', {'order_data': order_data})

    return render(request, 'store/checkout.html', {'cart': cart})
