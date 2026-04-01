# ---------------------------------------------------------------------------
# Known third-party payment processors.
#
# When a checkout page redirects to one of these domains, the TOCTOU domain
# guard treats it as a pass — the vendor intent was already approved by the
# policy gate, and these processors are independently trusted infrastructure.
#
# Users can extend this list via POP_ALLOWED_PAYMENT_PROCESSORS in .env
# without modifying this file.
#
# To propose additions, open a PR at github.com/agentpayorg/project-aegis.
# Include: processor name, domain, and one or two example vendors that use it.
# ---------------------------------------------------------------------------

KNOWN_PAYMENT_PROCESSORS: frozenset[str] = frozenset({
    # ── Stripe ──
    "stripe.com",           # Stripe-hosted checkout & Payment Links
    "js.stripe.com",        # Stripe Elements (iframe injection)
    # ── Zoho ──
    "zohosecurepay.com",    # Zoho Payments / Zoho Commerce checkout
    # ── Square ──
    "squareup.com",         # Square POS & Square Online checkout
    "square.com",           # Square marketing domain (some checkout flows)
    # ── PayPal / Braintree ──
    "paypal.com",           # PayPal Checkout
    "braintreegateway.com", # Braintree (PayPal subsidiary)
    # ── Adyen ──
    "adyen.com",            # Adyen Drop-In & Components
    # ── Checkout.com ──
    "checkout.com",         # Checkout.com hosted pages
    # ── Paddle ──
    "paddle.com",           # Paddle (SaaS billing & checkout)
    # ── FastSpring ──
    "fastspring.com",       # FastSpring (software & digital goods)
    # ── Gumroad ──
    "gumroad.com",          # Gumroad (creators / digital products)
    # ── Recurly / Chargebee (subscription billing) ──
    "recurly.com",
    "chargebee.com",
    # ── Event & ticketing platforms ──
    "eventbrite.com",       # Eventbrite
    "ti.to",                # Tito (tech conferences: RailsConf, WWDC alt, etc.)
    "lu.ma",                # Luma (tech meetups & events)
    "universe.com",         # Universe ticketing
    # ── Other ──
    "2checkout.com",        # 2Checkout / Verifone
    "authorize.net",        # Authorize.net (AIM / SIM hosted forms)
})
