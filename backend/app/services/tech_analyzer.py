import re
from bs4 import BeautifulSoup

TECH_SIGNATURES = {
    "wordpress": [
        {"type": "meta", "attrs": {"name": "generator"}, "content": "WordPress"},
        {"type": "link", "attrs": {"rel": "stylesheet"}, "href": "wp-content"},
        {"type": "link", "attrs": {"rel": "stylesheet"}, "href": "wp-includes"},
        {"type": "string", "value": "/wp-content/"},
        {"type": "string", "value": "/wp-json/"},
    ],
    "wix": [
        {"type": "meta", "attrs": {"name": "generator"}, "content": "Wix"},
        {"type": "string", "value": "wix-bolt"},
        {"type": "string", "value": "Wix.com"},
    ],
    "squarespace": [
        {"type": "meta", "attrs": {"name": "generator"}, "content": "Squarespace"},
        {"type": "string", "value": "squarespace.com"},
        {"type": "string", "value": "static.squarespace.com"},
    ],
    "shopify": [
        {"type": "meta", "attrs": {"name": "generator"}, "content": "Shopify"},
        {"type": "string", "value": "/cdn.shopify.com/"},
        {"type": "string", "value": "myshopify.com"},
    ],
    "webflow": [
        {"type": "meta", "attrs": {"name": "generator"}, "content": "Webflow"},
        {"type": "string", "value": "webflow"},
    ],
    "joomla": [
        {"type": "meta", "attrs": {"name": "generator"}, "content": "Joomla"},
        {"type": "string", "value": "/components/"},
        {"type": "string", "value": "/modules/"},
    ],
    "drupal": [
        {"type": "meta", "attrs": {"name": "generator"}, "content": "Drupal"},
        {"type": "string", "value": "/sites/default/"},
        {"type": "string", "value": "drupal.js"},
    ],
    "weebly": [
        {"type": "meta", "attrs": {"name": "generator"}, "content": "Weebly"},
        {"type": "string", "value": "weebly.com"},
    ],
    "ghost": [
        {"type": "meta", "attrs": {"name": "generator"}, "content": "Ghost"},
        {"type": "string", "value": "ghost.org"},
    ],
    "googlesites": [
        {"type": "string", "value": "sites.google.com"},
    ],
    "wampserver": [
        {"type": "string", "value": "wampserver"},
    ],
}

FRAMEWORK_SIGNATURES = {
    "react": [
        {"type": "string", "value": "react.js"},
        {"type": "string", "value": "react.production"},
        {"type": "string", "value": "__REACT_DEVTOOLS"},
        {"type": "string", "value": "data-reactroot"},
        {"type": "string", "value": "data-reactid"},
    ],
    "vue": [
        {"type": "string", "value": "vue.js"},
        {"type": "string", "value": "vue.min.js"},
        {"type": "string", "value": "__VUE_DEVTOOLS"},
        {"type": "string", "value": "data-v-"},
    ],
    "angular": [
        {"type": "string", "value": "angular.js"},
        {"type": "string", "value": "angular.min.js"},
        {"type": "string", "value": "ng-app"},
        {"type": "string", "value": "ng-version"},
    ],
    "nextjs": [
        {"type": "string", "value": "__NEXT_DATA__"},
        {"type": "string", "value": "/_next/static"},
    ],
    "gatsby": [
        {"type": "string", "value": "gatsby.js"},
        {"type": "string", "value": "___gatsby"},
    ],
    "jquery": [
        {"type": "string", "value": "jquery.js"},
        {"type": "string", "value": "jquery.min.js"},
        {"type": "string", "value": "jquery-"},
    ],
    "bootstrap": [
        {"type": "string", "value": "bootstrap.css"},
        {"type": "string", "value": "bootstrap.min.css"},
        {"type": "string", "value": "bootstrap.js"},
        {"type": "string", "value": "bootstrap.bundle"},
    ],
    "tailwind": [
        {"type": "string", "value": "tailwindcss"},
        {"type": "string", "value": "tailwind "},
    ],
}

ANALYTICS_SIGNATURES = {
    "google_analytics": [
        {"type": "string", "value": "gtag("},
        {"type": "string", "value": "ga("},
        {"type": "string", "value": "google-analytics.com/analytics.js"},
        {"type": "string", "value": "googletagmanager.com/gtag/js"},
    ],
    "google_tag_manager": [
        {"type": "string", "value": "googletagmanager.com/gtm.js"},
        {"type": "string", "value": "dataLayer"},
    ],
    "facebook_pixel": [
        {"type": "string", "value": "fbq("},
        {"type": "string", "value": "connect.facebook.net/en_US/fbevents.js"},
    ],
    "hotjar": [
        {"type": "string", "value": "hotjar"},
        {"type": "string", "value": "static.hotjar.com"},
    ],
    "hubspot": [
        {"type": "string", "value": "js.hs-scripts.com"},
        {"type": "string", "value": "hs-analytics"},
    ],
    "intercom": [
        {"type": "string", "value": "widget.intercom.io"},
        {"type": "string", "value": "Intercom('boot'"},
    ],
    "livechat": [
        {"type": "string", "value": "livechatinc.com"},
        {"type": "string", "value": "LiveChatWidget"},
    ],
    "tawkto": [
        {"type": "string", "value": "tawk.to"},
        {"type": "string", "value": "Tawk_API"},
    ],
    "calendly": [
        {"type": "string", "value": "calendly.com"},
        {"type": "string", "value": "assets.calendly.com"},
    ],
}

ECOMMERCE_SIGNATURES = {
    "woocommerce": [
        {"type": "string", "value": "woocommerce"},
        {"type": "string", "value": "/product/"},
        {"type": "string", "value": "/cart/"},
    ],
    "magento": [
        {"type": "meta", "attrs": {"name": "generator"}, "content": "Magento"},
        {"type": "string", "value": "mage/"},
    ],
    "bigcommerce": [
        {"type": "string", "value": "bigcommerce.com"},
    ],
}


def _check_signatures(soup: BeautifulSoup, html_text: str, signatures: dict) -> list[str]:
    detected = []
    for name, sigs in signatures.items():
        for sig in sigs:
            if sig["type"] == "meta":
                tag = soup.find("meta", attrs=sig["attrs"])
                if tag and sig["content"].lower() in (tag.get("content", "") or "").lower():
                    detected.append(name)
                    break
            elif sig["type"] == "link":
                tag = soup.find("link", attrs=sig["attrs"])
                if tag and sig.get("href", "") in (tag.get("href", "") or ""):
                    detected.append(name)
                    break
            elif sig["type"] == "string":
                if sig["value"].lower() in html_text.lower():
                    detected.append(name)
                    break
    return detected


def detect_tech_stack(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    html_lower = html.lower()

    cms = _check_signatures(soup, html_lower, TECH_SIGNATURES)
    frameworks = _check_signatures(soup, html_lower, FRAMEWORK_SIGNATURES)
    analytics = _check_signatures(soup, html_lower, ANALYTICS_SIGNATURES)
    ecommerce = _check_signatures(soup, html_lower, ECOMMERCE_SIGNATURES)

    return {
        "cms": list(set(cms)),
        "frameworks": list(set(frameworks)),
        "analytics_tools": list(set(analytics)),
        "ecommerce": list(set(ecommerce)),
    }
