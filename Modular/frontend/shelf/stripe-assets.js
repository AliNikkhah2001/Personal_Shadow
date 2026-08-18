export const STRIPE_ASSET_ROOT = "/assets/stripe-press";

export function stripeAssetUrl(localFile) {
  return `${STRIPE_ASSET_ROOT}/${localFile}`;
}
