const STRIPE_ASSET_ROOT = "/assets/stripe-press";

function stripeAssetUrl(localFile) {
  return `${STRIPE_ASSET_ROOT}/${localFile}`;
}

window.ShelfStripe = { STRIPE_ASSET_ROOT, stripeAssetUrl };
