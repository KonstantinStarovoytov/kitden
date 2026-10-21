# Kitden: licensing and early sales options

Reviewed: 2026-10-18. Status: **research and proposals, not approved commercial terms**.

## Basis and boundaries

The approved [brief](../project-brief.md) describes a local developer utility, with a browser
interface, no required login, and safe changes to Claude Code, Codex, and Cursor settings.
The owner confirmed Poland as the seller country during this research. Legal form and tax
residency were not established. Local inspection found `kitden` 0.2.0 in `pyproject.toml`,
without a license field; the file inventory found no root LICENSE or contribution agreement.
This is not an audit of historical releases, ownership, or dependencies.

Billing and a public SaaS are outside the current implementation scope. The owner requested
commercial research; this note does not authorize a billing implementation, public release,
license change, or expansion of the feature specification.

## Recommended commercial sequence — proposal

1. Run a free beta with clear distribution terms. Validate installation, a useful first finding,
   and repeat use before building a checkout or entitlement service.
2. Interview users who solved a real setup problem. Test an actual paid offer once the promised
   product can be delivered. Download counts and compliments are not willingness to pay.
3. Keep inventory, source visibility, existing safety checks, backup, undo, and uninstall usable
   without a subscription. Payment expiry must never prevent recovery of a prior change.
4. Test a paid local edition only if users identify a recurring benefit. Candidate future benefits
   include saved setup profiles, historical comparisons, and reproducible setup bundles. These
   are research ideas, not implemented features or approved first-release scope.
5. Use hosted checkout and a license key rather than building account management. Publish the
   website, documentation, and downloads; the user's setup and credentials stay on their machine.

**Pricing experiments, not market facts:** compare a $29 early-access license with a $49 regular
license including twelve months of updates. Clearly define continued use of the last eligible
version, supported client versions, and an optional renewal. Do not promise permanent compatibility
with continuously changing AI clients or lifetime support. Test a yearly maintenance offer only
after observing repeat value. Avoid charging per tool call: Kitden is not a traffic gateway.

An alternative is fully open software funded by sponsorship or paid support. It is simpler to
license but its revenue is unproven. Human support services need a payment product that accepts
services; do not assume a digital-software merchant-of-record plan permits them.

## License choices

Selling downloads, selling additional usage rights, and selling the company or project are
different activities. Open source does not prohibit commercial use or charging for copies.
It also lets recipients exercise redistribution rights under the chosen license.

| Model | What can be sold | Important tradeoff | Fit |
| --- | --- | --- | --- |
| Apache-2.0 for the whole app | Official builds, support, future separate features | Others can distribute competing builds and closed derivatives under the license conditions | Strong adoption option; weak exclusivity |
| MPL-2.0 core, separate proprietary features | A commercial edition containing both | Covered files and modifications must remain available under MPL on distribution; separate original files can have different terms | Reasonable open-core candidate if the boundary is real |
| AGPL-3.0 plus a commercial alternative | Paid exceptions to copyleft, where the seller controls the required rights | Ordinary commercial use is already allowed; individual local users may have little reason to buy an exception | Poor default for this first local utility |
| Proprietary app with a free tier or trial | Paid local license, updates, optional features | Less code transparency; marketplace rules may constrain distribution | Direct paid-product option if exclusive control is the priority |

Sources: [Apache sections 2–6](https://www.apache.org/licenses/LICENSE-2.0),
[MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/),
[AGPL text](https://opensource.org/license/agpl-3-0).

MPL's boundary is covered source files, not a promise that every improvement is sent upstream.
Its server-side use alone is not distribution; delivered browser code is a separate matter.
AGPL has source obligations for conveying covered works and for modified versions used over a
network. It is neither a commercial-use ban nor an automatic claim over independent clients.
An open-core business model needs an explicit component/license map. A license key cannot remove
rights already granted for open-source code.

**Decision proposal:** retain Apache-2.0 as the adoption-first option from the
[earlier research](naming-and-licensing-2026-10-17.md). If selling exclusive local features is now
the priority, evaluate a clearly separated MPL core/proprietary edition or a proprietary app
before publishing the whole implementation under a permissive license. Do not choose AGPL merely
because an acquisition might happen. No license is applied by this note.

Marketplace packaging has its own policy requirements. [Cursor's marketplace policy](https://prod.cursor.com/help/security-and-privacy/marketplace-security)
requires open-source plugins, ships no binaries, and manually reviews each update. A source-visible plugin that launches a
separate paid engine is not automatically an accepted marketplace submission. Validate that exact
distribution shape before relying on it; a direct download remains a separate route.

## Checkout shortlist — verified vendor documentation

Merchant of record (MoR) means the provider is the seller of record for covered transactions and
handles the relevant customer sales-tax processes. It does not determine the owner's Polish
business registration, income-tax, bookkeeping, or other obligations.

| Provider | Published fees at review | Useful for Kitden | Limits |
| --- | --- | --- | --- |
| **Lemon Squeezy** | 5% + $0.50 base; +1.5% international transactions, +1.5% PayPal, +0.5% subscriptions; payout fees can apply | Hosted checkout, downloads, automatic license keys; first integration candidate | Verify approval, payout currency and final cost; online API is not a ready-made offline license design |
| **Polar** | New Starter organizations: 5% + $0.50; +1.5% non-US cards; payout fees apply | Hosted checkout and built-in keys, activation limits, expiry; close alternative | Old 4% + $0.40 quotes are grandfathered, not the current new-seller rate |
| **Paddle Billing** | 5% + $0.50 per checkout transaction on published standard pricing | MoR checkout and subscriptions | Current Billing expects the seller to build download/key fulfillment; Classic documentation can mislead |
| **Stripe Payments** | Depends on seller location and payment method; no single figure used here | Flexible hosted Checkout and Payment Links | Ordinary Payments leaves the business as merchant of record |
| **Stripe Managed Payments** | Adds 3.5% to standard processing; subscription billing fees can also apply | A real Stripe MoR option, subject to eligibility | Digital products only; separate license delivery needed; human tech support/consulting excluded |

Fee evidence: [Lemon pricing](https://www.lemonsqueezy.com/pricing),
[Lemon additional fees](https://docs.lemonsqueezy.com/help/getting-started/fees),
[Polar fees](https://polar.sh/docs/merchant-of-record/fees),
[Paddle pricing](https://www.paddle.com/pricing),
[Stripe Managed Payments pricing](https://support.stripe.com/questions/managed-payments-pricing?locale=en-GB).
These are not complete net-revenue quotes: taxes, currency conversion, refunds, chargebacks,
payouts, product type, and individually agreed terms can change the outcome.

Product evidence: [Lemon license generation](https://docs.lemonsqueezy.com/help/licensing/generating-license-keys),
[Polar license keys](https://polar.sh/docs/features/benefits/license-keys),
[Paddle fulfillment change](https://developer.paddle.com/migrate/start/),
[Stripe MoR comparison](https://docs.stripe.com/payments/managed-payments).

Poland appears explicitly in [Polar's payout list](https://polar.sh/docs/merchant-of-record/supported-countries)
and [Lemon's bank payout list](https://docs.lemonsqueezy.com/help/getting-started/supported-countries).
[Paddle](https://www.paddle.com/help/legal/sanctions/which-countries-are-supported-by-paddle)
supports software sellers outside its excluded countries; Poland is not excluded.
[Stripe Managed Payments eligibility](https://docs.stripe.com/payments/managed-payments/eligibility)
lists PL among supported business locations. All still require the applicable verification and
product approval. Country support does not establish that this particular seller is approved.

**Proposed selection:** start by testing Lemon Squeezy's sandbox purchase, key email, activation,
refund, and download delivery. Compare Polar on the same flow if onboarding or UX is unsuitable.
Do not integrate four providers. No live account or purchase was created for this research.

## Keep local use independent of checkout availability — proposal

The free app should work without a Kitden account. A paid edition can ask for an emailed key once.
Purchase and optional activation naturally disclose purchase data to the payment provider; that
must not also upload local inventory, file paths, or credentials.

Polar and Lemon document online license endpoints. A license key alone does not establish
cryptographically verified offline access. Define outage and offline behavior explicitly: cached
entitlement with a reasonable grace period, or a signed license document verified locally.
Fully offline perpetual access delays revocation and can increase sharing; accept that tradeoff
deliberately rather than promising immediate revocation and permanent offline use together.

[Keygen's offline licensing documentation](https://keygen.sh/docs/choosing-a-licensing-model/offline-licenses/)
is a useful reference if signed offline licenses become necessary. It is not a recommendation to
add a second licensing service to the first release. Never embed a payment provider's privileged
API token or a private signing key in the downloadable app.

## Preserve acquisition options

Apache's grants for existing releases are expressly irrevocable subject to their terms. A sale
does not turn those copies into exclusive code. Future licenses depend on rights in the affected
code, including contributor and dependency rights. A prospective buyer may value the maintained
product, brand, customer relationships, revenue and expertise; demand for an acquisition is not
established by this research. [Apache text](https://www.apache.org/licenses/LICENSE-2.0).

Maintain clear records of authorship, contractor/employer rights, third-party code and assets,
domain ownership, and customer commitments. A DCO certifies the contributor's right to submit
under the indicated license; it is not unrestricted relicensing permission. A suitable CLA can
grant additional rights but does not necessarily assign copyright. Review wording before inviting
substantial contributions if dual licensing matters.
[DCO](https://developercertificate.org/),
[Apache contribution agreements](https://www.apache.org/licenses/contributor-agreements.html).

Before collecting payment, resolve seller legal form, distribution terms, refund/support promises,
provider approval, and the source/proprietary boundary. Have a Polish accountant review the local
business treatment and an IP/software lawyer review material licensing or sale terms. This note
is a strategy comparison, not a completed legal or tax opinion.

## Verification limits

Checked primary license texts, provider documentation, the current brief, constitution, prior
research, package metadata and visible license filenames. No checkout, payout, package license
compliance, or offline activation was tested. This document-only task does not need application
tests. No implementation, settings, purchases, publication, or licensing changes were made.
