# Launch skills and supporting tools

Reviewed: 2026-10-18. Status: recommendations, not installed or executed.

## Method

Used the installed find-skills workflow: inspected the skills.sh leaderboard, searched by
task, checked the upstream repository and individual SKILL.md sources. A local
`npx --no-install skills find launch-strategy` search produced no result and was interrupted;
the evidence below comes from the web directory and upstream sources. No skill was installed.
Popularity is a screening signal, not a security audit or evidence of commercial success.

## Small recommended set

The [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills)
repository showed approximately 55.3K GitHub stars when reviewed. It is a community project,
not an official OpenAI, Anthropic, or Cursor package. Its README declares MIT licensing.
The following four skill sources were read to assess their fit.

| Skill | Useful output for Kitden | Directory installs shown on review date |
| --- | --- | --- |
| [product-marketing](https://www.skills.sh/coreyhaines31/marketingskills/product-marketing) | One reusable description of buyer, problem, proof, positioning, and unresolved assumptions | 79.7K |
| [launch](https://www.skills.sh/coreyhaines31/marketingskills/launch) | Staged beta/release plan and launch assets | 74.2K |
| [pricing](https://www.skills.sh/coreyhaines31/marketingskills/pricing) | Packaging and willingness-to-pay experiments | 75.1K |
| [copywriting](https://www.skills.sh/coreyhaines31/marketingskills/copywriting) | Clear landing page, install page, and product description | 227.6K |

The counts are directory-reported installations, not unique active users or audited quality.
Older search results use `product-marketing-context`, `launch-strategy`, and `pricing-strategy`.
The upstream README maps them to the current names above. Do not install both generations.

Source files reviewed:

- [product-marketing/SKILL.md](https://github.com/coreyhaines31/marketingskills/blob/main/skills/product-marketing/SKILL.md)
- [launch/SKILL.md](https://github.com/coreyhaines31/marketingskills/blob/main/skills/launch/SKILL.md)
- [pricing/SKILL.md](https://github.com/coreyhaines31/marketingskills/blob/main/skills/pricing/SKILL.md)
- [copywriting/SKILL.md](https://github.com/coreyhaines31/marketingskills/blob/main/skills/copywriting/SKILL.md)

Optional installation command, not run:

```sh
npx skills add coreyhaines31/marketingskills --skill product-marketing launch pricing copywriting
```

Review the resolved revision and selected target agents before installing. Prefer project-level
installation of this small subset. Do not install the entire catalog or duplicate it across
directories that clients already share.

## Fit and limitations

These are workflow guides, not agents that can create demand by themselves. The launch and
pricing skills lean toward SaaS. For Kitden, substitute local utility adoption, successful
installation, useful findings, safe changes, and return use for generic signup/seat metrics.
Do not add accounts, subscriptions, email capture gates, or analytics merely because a template
suggests them. Pricing is an experiment until users pay; a skill cannot establish market price.

The source launch guide includes case-study performance claims. Those claims were not separately
verified and are not used as evidence for Kitden's expected results. Platform-specific posting
rules take precedence over generic launch advice. Reading these files did not authorize external
posting, email, ads, account connections, or spending.

Proposed order: product-marketing -> copywriting -> launch; use pricing once the paid value is
clear. Store research and decisions in files so a focused agent can read only its own inputs.
The brief remains authoritative for product scope; a marketing context file must not silently
turn proposed commercial features into committed requirements.

## Official packaging helper

[Cursor Create Plugin](https://cursor.com/marketplace/cursor/create-plugin) is published and
verified by Cursor. Its listing describes `create-plugin-scaffold`,
`review-plugin-submission`, a plugin architect, and quality rules. It is useful after choosing
to build a Cursor package. It is not a payment or customer-acquisition service. Its install count
was not established here; it is recommended for its official provenance and specific packaging
job, not inferred popularity. The documented Cursor command is `/add-plugin create-plugin`.
It was not installed or executed. Source-level review is still needed before use.

## Hosting the public face

Proposed: a static website for positioning, a short video, a synthetic-data interactive demo,
installation instructions, compatibility information, release notes, and later a checkout link.
[Cloudflare Pages supports static HTML deployment](https://developers.cloudflare.com/pages/framework-guides/deploy-anything/).
This is sufficient for a first public site; it does not require moving the local engine to a cloud
server. No hosting plan price or account eligibility was assumed.

The online demo must say it uses sample data and cannot inspect a visitor's computer. Real
configuration access remains in the installed local product. The public site must not get a
silent bridge to localhost.

Keep the stack small: one marketing skill set, one distribution process, one hosted checkout
when needed. A SaaS boilerplate, CRM, mass-posting agent, or ad-automation service is not a
prerequisite for the first external users.
