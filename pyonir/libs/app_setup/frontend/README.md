# Pyonir Themes

This application supports a flexible theming system, allowing users to switch between different visual styles.  
Themes provide control over colors, typography, spacing, and other UI elements to create a consistent and customizable user experience.

### Theme Name

This folder contains a Pyonir theme for your web application. Pyonir uses this README to understand how the theme is structured, including templates, styles, and any custom configuration.

**Folder Structure**

```
frontend/themes/<theme-name>/
│
├─ templates/         # HTML or template files used by Pyonir
├─ styles/            # CSS, SCSS, or Tailwind files
├─ assets/            # Images, fonts, icons, etc.
└─ README.md          # This file (theme configuration guide)
```

### Templates

Place all template files inside the templates folder.

Pyonir will automatically detect the templates in this folder.

Naming conventions are flexible, but it’s recommended to keep template names descriptive:
```html
home.html
post.html
user/profile.html
```

### Public Assests

Include all vendor related assets in the public folder.

```html
frontend/
└─ public/
    └─ vendor-style.css
└─ static/
    └─ your-app-style.css
```


Pyonir will automatically load these styles when the theme is activated.

### Template Assets

Add any template related images, fonts, or other static assets in the assets folder.

Pyonir will serve assets from this folder when referenced in templates or styles.