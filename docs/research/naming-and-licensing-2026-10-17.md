# Naming and licensing research

Reviewed: 2026-10-17, naming updated 2026-10-18. Status: the name is decided (Kitden, owner,
2026-10-18); the license is still a proposal.

## Product basis

The approved [project brief](../project-brief.md) describes a local page for understanding
and safely changing what Claude Code, Codex, and Cursor load. It covers plugins, skills,
hooks, marketplaces, and MCP connections, including one connection to an existing gateway.
The product does not build or proxy a gateway. The name should fit this wider purpose.

Proposed positioning: **See and manage your AI coding setup in one place.**

## Naming method and limits

We searched exact names on the public web, with additional software, app, GitHub, npm,
and PyPI keywords for finalists. This is an initial collision screen, not trademark clearance.
Search engines can miss projects, packages, registered marks, and unregistered businesses.
No candidate domain, package name, or social handle has been reserved or confirmed available.
Negative search results are observations, not evidence of exclusive rights.

Before adopting a name, check package registries directly, domains, similar spellings,
and relevant trademark registers. [WIPO](https://www.wipo.int/en/web/global-brand-database)
also recommends checking national and regional registers beyond its global database.

## Shortlist — proposed

| Name | Intended meaning | Strength | Limitation | Search observation |
| --- | --- | --- | --- | --- |
| **Kitden** | Kit + den: the room where your kit lives | Short, broad enough for future features | Needs a tagline | No product found; free on PyPI and npm; no GitHub account; `.dev`, `.ai`, `.si` not registered; `.com` registered since 2017 (registry lookups, 2026-10-18) |
| **Kitshed** | Kit + shed: where tools are kept | Tool-shed image is easy to understand | "Shed" is also a verb | No product found; free on PyPI and npm; no GitHub account or repositories; `.dev`, `.ai`, `.si` not registered; `.com` in use |
| **Kitstow** | Kit + stow: your kit, put away neatly | Same family as the original favorite | Harder to say | No product found; free on PyPI and npm; no repositories; `.com`, `.dev`, `.ai`, `.si` not registered |
| **Riglens** | A lens into your development rig | Fits visibility, sources, and duplicate detection | Hardware association; visibility is clearer than management | No clear software product surfaced, but RIGLENS is an Appleton industrial part identifier in distributor catalogs |
| **Rigtrail** | Follow where each part of your setup comes from | Fits provenance and explaining cross-client loading | Can sound like a runtime tracing product | The name appeared as an animation rigging module in public production notes; no clear standalone competing product surfaced |

**Decided (owner, 2026-10-18): Kitden.** The other names stay here as researched alternatives.
Proposed tagline for Kitden: **Your AI setup, in one place.**
Proposed tagline for Riglens: **Know what your agents load.**

Search queries included `"Kitrove"`, `"Kitrove" software app`,
`"Kitrove" github npm pypi`, `"Riglens"`, `"Riglens" software github npm pypi`,
`"Rigtrail" software`, and `"Rigtrail" app software github`.

The Riglens non-software collision is visible in the
[Rexel product listing](https://www.rexelusa.com/p/263541/appleton/app-riglens-rigmaster-lens-frame-/781381190381/riglens).
The Rigtrail reference is in [public rigging notes](https://hackmd.io/JnUjDA48TYKOUVpuiZK-Hw).
Neither observation establishes whether trademark use would be allowed.

## Names screened out

These are branding judgments, not findings of trademark infringement.

| Name | Evidence | Recommendation |
| --- | --- | --- |
| Kitrove | [kitrove.dev](https://kitrove.dev): open-source, local-first tool that collects skills from AI coding tools and moves them to another tool; [repository](https://github.com/Kapital-Labs/kitrove) with release v0.1.0-rc.4.1 (found 2026-10-18) | Reject: same category. The 2026-10-17 search missed it |
| AgentSetup | [PyPI package](https://pypi.org/project/agentsetup/) by Agentable, maintainer kaptinlin; also [another GitHub project](https://github.com/rendrag-git/agentsetup) | Do not use as the public package or brand without resolving the collision. It is the current local working name |
| AgentShelf | [Local cross-client agent asset browser](https://github.com/yigitkonur/agentshelf) and [another AI platform](https://agentshelf.ai/) | Reject: direct category overlap |
| AgentTidy | [Existing AI agent project](https://github.com/Azayzel/AgentTidy) | Reject: adjacent category |
| SetupLens | [Existing industrial setup software](https://www.setuplens.com/) | Reject: established exact-name software |
| Riglane | [Existing AI workflow tool](https://riglane.dev/) | Reject: adjacent category |
| SetupHarbor | Installation component named on [AppHarbor](https://appsharbor.com/) | Reject: setup software overlap |
| Loadfolio | [Framer template](https://www.framer.com/marketplace/templates/loadfolio/) | Reject: existing developer-facing digital product |
| Kitstead | [Guest operations product](https://kitstead-str-guest-ops.juniormelo1995.chatgpt.site/) | Lower priority: existing digital-product brand |
| Kitspan | [Sportswear business](https://kitspan.com/) | Lower priority: exact brand already in use |

The PyPI finding is based on the indexed registry result reviewed on this date. Direct page
retrieval failed during this session; recheck the registry before release. We have not
established whether the owner has any relationship with that publisher.

### Related product finding

AgentShelf's README describes a local browser UI for skills, rules, MCP servers, instructions,
and plugins across Claude Code, Codex, Cursor, and other tools. It describes previews,
copying, conflict handling, and undo. These are project claims, not runtime verification.
This is a close comparison candidate missing from the current brief's comparison table.
Kitrove (see above) is another one: it moves skills between AI coding tools.
Do not market our product as the first cross-client inventory without a deeper comparison.
This research does not change the approved implementation scope.

## License options — research

Selling copies, selling an alternative commercial license, and selling the project or company
are different transactions. Open-source licensing does not by itself prevent an acquisition.
It does affect what exclusive control a buyer can obtain over previously released code.

| Option | What others can do | Main obligation or limitation | Fit for this project |
| --- | --- | --- | --- |
| MIT | Use commercially, modify, distribute, and include in closed products | Preserve the required copyright and permission notice | Simple adoption; little control over competing derivatives |
| Apache-2.0 | Commercial use and closed derivatives | License and notice requirements; explicit contributor patent grant with conditions | Default proposal if broad open-source adoption is the priority |
| MPL-2.0 | Commercial use and combination with separate closed code | On distribution, covered files and changes to them remain available under MPL | Middle ground if sharing changes to the core matters |
| AGPL-3.0 | Commercial use and competing forks | Copyleft when conveying covered works; modified network versions must offer corresponding source to remote users | Consider when open derivatives or dual licensing are deliberate goals |
| Proprietary terms | Only the uses granted in the contract | Author defines distribution and modification rights, subject to dependency obligations | Appropriate if retaining exclusive commercial control is the priority |

Sources: [MIT text](https://opensource.org/license/mit),
[Apache text](https://www.apache.org/licenses/LICENSE-2.0),
[Mozilla FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/),
[AGPL text, especially section 13](https://opensource.org/license/agpl-3.0).

MPL has no AGPL-style network source trigger. Server use alone is not distribution under
Mozilla's FAQ; code delivered to a browser is a different case. AGPL does not ban commercial
use, competition, or charging money. It does not automatically cover every independent system
communicating with the program. Neither license guarantees contributions will be sent upstream.

Restrictions such as “no commercial use” or “no competing service” are not consistent with
the [Open Source Definition](https://opensource.org/osd). A source-available license may use
such restrictions, but its exact terms need separate review. “Open core” is a business model,
not the name of a license.

## Acquisition and ownership

**Existing grants remain relevant.** Apache's copyright grant is expressly irrevocable,
subject to its terms. Selling the project does not turn an already licensed release into
exclusive code. Changing future releases also requires sufficient rights in their contents.
[Apache sections 2–4](https://www.apache.org/licenses/LICENSE-2.0).

**Alternative licenses require rights.** A copyright holder may offer their code under
multiple licenses. A later buyer cannot assume that all third-party contributions can be
relicensed simply because they are in the repository.
[GNU licensing FAQ](https://www.gnu.org/licenses/gpl-faq.en.html#ReleaseUnderGPLAndNF).

**Contribution terms matter before outside contributions arrive.** A suitable contributor
agreement may grant relicensing rights; copyright assignment is another, different mechanism.
A CLA does not automatically transfer copyright: its wording matters. A DCO records a
contributor's certification of origin and right to contribute under the indicated license;
it is not a blanket copyright transfer or unrestricted relicensing grant.
[Apache contributor agreements](https://www.apache.org/licenses/contributor-agreements.html),
[DCO text](https://developercertificate.org/).

Proposed preparation for a possible sale:

- Keep the authorship and contribution history, including contractor and employment terms.
- Keep an inventory of dependency versions, licenses, and any copied code or assets.
- Keep ownership of the domain, brand assets, and project accounts clear.
- Choose contribution terms before accepting substantial outside work if dual licensing matters.
- Have counsel review ownership and sale terms for the relevant jurisdictions before a transaction.

This is practical preparation, not a completed rights or dependency audit. AI-assisted code
also needs provenance review; exclusive rights should not be assumed merely because a model
generated it. The application license cannot erase third-party obligations.

## Recommendation — proposed, not applied

For an open local developer utility, start the decision with **Apache-2.0**. This prioritizes
adoption and integration while accepting that others can ship competing closed derivatives.
The business case for an acquisition would then depend on the maintained product, brand,
users, expertise, and future development, rather than exclusive access to published code.
That is a strategic assessment, not a prediction of buyer demand.

If sharing improvements to distributed core files is important, prefer **MPL-2.0**.
If paid exceptions to copyleft are an intended revenue source, evaluate **AGPL plus a separate
commercial license**, together with suitable contribution rights. Do not select AGPL merely
because a future sale is possible.

If the owner wants to retain the ability to sell exclusive control of unreleased code,
keep that code private while deciding; use explicit proprietary terms for any early distribution.
Do not treat a public repository with no license as a usable distribution policy.
[GitHub's no-license guidance](https://choosealicense.com/no-permission/).

Local inspection found no root LICENSE and no license field in pyproject.toml at review time.
This does not establish the repository's past licensing or legal status.
No license, public name, package name, or contribution policy was changed by this research.
Final legal choices should be reviewed with a software/IP lawyer in the owner's jurisdiction.
