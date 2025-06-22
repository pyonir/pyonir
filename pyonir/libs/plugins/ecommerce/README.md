# 🛒 Online Shopping Cart Plugin

A lightweight and modular shopping cart plugin designed for seamless integration into any web-based storefront. Easily manage products, quantities, pricing, and cart state with flexible APIs and optional UI bindings.

## Features

- Add, update, and remove products from the cart
- Persistent cart state (localStorage or session-based)
- Subtotal, tax, discount, and total calculation
- Coupon and promo code support
- Configurable tax and shipping logic
- Extensible with custom logic (e.g., for inventory validation)
- Lightweight, framework-agnostic core (can be used with React, Vue, Angular, etc.)

## Installation

```bash
npm install online-shopping-cart-plugin
```

Or include via CDN:

```html
<script src="https://cdn.example.com/shopping-cart.min.js"></script>
```

## Basic Usage

```js
import ShoppingCart from 'online-shopping-cart-plugin';

const cart = new ShoppingCart();

// Add a product
cart.addItem({
  id: 'prod-101',
  name: 'T-Shirt',
  price: 19.99,
  quantity: 1,
  metadata: {
    size: 'M',
    color: 'Black'
  }
});

// Update quantity
cart.updateItem('prod-101', { quantity: 2 });

// Get current cart
const items = cart.getItems();

// Calculate totals
console.log(cart.getSubtotal());
console.log(cart.getTotal()); // Includes tax/shipping if configured

// Remove item
cart.removeItem('prod-101');

// Clear the cart
cart.clear();
```

## API

### `addItem(item: CartItem): void`

Adds a new item to the cart or increases quantity if already present.

### `updateItem(itemId: string, updates: Partial<CartItem>): void`

Updates quantity or metadata of an existing item.

### `removeItem(itemId: string): void`

Removes an item from the cart.

### `getItems(): CartItem[]`

Returns a list of all cart items.

### `getSubtotal(): number`

Returns the subtotal before tax/shipping.

### `getTotal(): number`

Returns the total including tax/shipping/discounts.

### `applyCoupon(code: string): boolean`

Applies a discount coupon, returns `true` if valid.

### `clear(): void`

Empties the cart.

## Configuration

You can pass options to the constructor:

```js
const cart = new ShoppingCart({
  taxRate: 0.08,
  shippingRate: 5.0,
  persist: true // stores cart in localStorage
});
```

## Type Definitions

```ts
type CartItem = {
  id: string;
  name: string;
  price: number;
  quantity: number;
  metadata?: Record<string, any>;
};
```

## Customization

You can extend the plugin to support:

- Custom tax/shipping calculations
- Inventory checks
- Currency formatting
- Backend syncing

```js
class MyCart extends ShoppingCart {
  calculateTax(subtotal) {
    return subtotal * 0.1; // override for custom tax
  }
}
```

## Browser Support

Fully supports all modern browsers. For older browsers (e.g., IE11), a polyfill may be required for localStorage and ES6 features.

## License

MIT License © 2025 YourNameOrCompany

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.