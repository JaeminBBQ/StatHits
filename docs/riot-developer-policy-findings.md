# Riot Developer Policy Findings: ARAM: Mayhem stat-competition app

Researched 2026-09-27. Pages were fetched directly, and quotes are copied verbatim from the live pages on that date.
**[Primary]** means an official Riot page. **[Secondary]** means a community or third-party source, or a comment by an individual in a public tracker.

> **Blocking finding (read first).** Riot has made ARAM: Mayhem match data private in the public API. `match-v5` returns **403 Forbidden** for ARAM: Mayhem match IDs, and a Riot engineer called this "Expected behavior". As of 2026-09-27 we found no sign that this has changed. The app's core data source doesn't work for this queue with a normal API key. See Q6.

> **Two copies of the General Policies disagree.** Both are labelled "Last updated May 29, 2025":
> - the one at `developer.riotgames.com/policies/general` (called the **"portal copy"** below)
> - the one on Riot's Zendesk support site, `support-developer.riotgames.com` (called the **"support copy"** below)
>
> The support copy (and the support-site League of Legends policy) adds clauses the portal copy lacks. The clauses that matter here cover leaderboards, historic Riot IDs and the 20-participant minimum. The safe approach is to follow **both** copies. Where they differ, this document quotes both.

---

## 1. Monetization

**Direct answer**
- **API policy.** A product may be monetized only once it is registered in the Developer Portal with status **Approved** or **Acknowledged**. A throwaway 24h development key is not a registered product. An approved key does **not** count as Riot endorsing the product.
- **What's allowed:**
  - a **free tier is mandatory** (it may carry ads)
  - ads, subscriptions, donations and crowdfunding
  - tournament entry fees
  - currencies that can't be exchanged back into money
- **Paywalled content** is allowed only if it is "transformative". Riot also reserves the right to judge whether pricing is fair ("gouging").
- **What's prohibited:**
  - betting and gambling
  - ads inside Riot properties
  - crypto and blockchain (support copy: also NFTs)
- **Legal Jibber Jabber (LJJ)** bans commercial fan projects (crowdfunding, business entity, paywalls) without a written license. Its **Exception 3** allows commercial projects that (1) comply with the API Terms and Policies and (2) use a currently valid Riot API key granted specifically for that project. So a **separate written agreement isn't needed** as long as you stay inside the API policies with a project-specific approved key.
- **Caveat: the API Terms (Dec 2013) are stricter on paper.** Charging for access to game data needs Riot's "prior written approval". Advertising is explicitly exempt. The later General Policies tie approval to "Approved or Acknowledged" status, but they don't expressly say that status satisfies the 2013 "prior written approval" clause. Asking Riot through the support site before adding a paid tier is the conservative route.

**Quotes**
- General Policies, Monetization **[Primary]**:
  > "Your product cannot feature betting or gambling functionality."
  > "You may monetize your product as long as your product is registered on the Developer Portal and your product status is either Approved or Acknowledged."
  > "You must have a free tier of access for players, which may include advertising"
  > "Your content must be transformative if you are charging players for it" ... "Was value added to the original by creating new information, new aesthetics, new insights, and understandings? If so, then it was transformative."
  > "Acceptable ways to charge players are: Subscriptions, donations, or crowdfunding / Entry fees for tournaments / Currencies that cannot be exchanged back into fiat"
  > "Your monetization cannot gouge players or be unfair (yes, we get to decide that)"
  > "You may not place advertisements in Riot properties, which include in-game, loading screens, and the Riot Client."
- API Terms, Licensed Uses and Restrictions **[Primary]**:
  > "In the event You desire to resell or license any Application, charge for access to Game Information through a website or otherwise require payment for access to the Game Information, You must notify Riot and obtain Riot's prior written approval before undertaking such activities (please see Riot's full policy at http://www.riotgames.com/legal-jibber-jabber for more details). ... For the sake of clarity, You may advertise through such software applications and/or websites without asking for Riot's permission, provided You are otherwise complying with these API Terms."
- API Terms, No Partnership or Endorsement **[Primary]**:
  > "no act by Riot shall constitute endorsement, certification or approval of any Application, including, without limitation, Riot's registration of an Application and issuance of a Production Key."
- Legal Jibber Jabber, section 2 **[Primary]**:
  > "You may not create commercial Projects, including any Project that crowdsources any portion of its funding, any Project that involves a business or legal entity, or any Project where you gate the content with a paywall (e.g., Patreon, YouTube Premium, etc.) without a written license agreement from us. We have only three exceptions."
  > "Exception 1: Ad Revenue — We permit individual players to promote their Projects on websites, streams, or videos and passively generate revenue through appropriate advertisements ..."
  > "Exception 3: API Dev Terms and Policies — We permit commercial Projects that both (1) comply with our API Terms and API Policies; and (2) use a currently valid Riot API key that we granted to you specifically for your Project. ... If we revoke your API key for any reason, you must immediately shut down your Project."

**Sources**
- https://developer.riotgames.com/policies/general (last updated May 29, 2025)
- https://developer.riotgames.com/terms (last updated December 9, 2013)
- https://www.riotgames.com/en/legal (Legal Jibber Jabber, last updated August 2018)

---

## 2. Displaying other players (Riot IDs, stats, privacy)

**Direct answer**
- **Showing other players is not prohibited.** Riot IDs and PUUIDs are returned for every participant in `match-v5`. Riot tells developers to display Riot IDs in place of summoner names.
- **No general opt-out requirement exists** for ordinary public matches. The one explicit opt-in rule covers **custom-game** match history: it may be shown publicly only if the player opts in, and otherwise only to that player through RSO.
- **Hidden or anonymous players.** The portal copy bans de-anonymizing players who can't reasonably be identified from visible information. The LoL docs ban identifying or analyzing players "deliberately hidden by the game".
- **Streamer mode.** No policy mentions it by name. It is best treated as covered by the "deliberately hidden" clause.
- **Historic Riot IDs.** The support copy (General and LoL policies) says products "may not expose a player's historic Riot IDs". Show only the current Riot ID, refreshed from `account-v1`, and don't keep a visible name history.
- **Which production use cases are pre-approved:**
  - pre-approved: "Showing (self) player stats"
  - pre-approved: "Aggregate player stats (no specific players)"
  - not on the list: a profile page for arbitrary specific players (op.gg style). It isn't prohibited, but approval is at Riot's discretion.
- **Other rules:**
  - The API Terms forbid using the API to "violate anyone's privacy rights".
  - The API Terms forbid messaging players through data obtained from the API.
  - Your own privacy policy is required for a production key (see Q7).

**Quotes**
- General Policies, Game Integrity (portal copy) **[Primary]**:
  > "Products cannot de-anonymize players who cannot reasonably be identified from visible information."
- General Policies (support copy) and support-site League of Legends policy **[Primary]**:
  > "Products may not expose a player's historic Riot IDs"
- LoL Developer API Policy, Game Integrity **[Primary]**:
  > "Products cannot identify or analyze players who are deliberately hidden by the game."
- LoL Game Policy, Unapproved Use Cases **[Primary]**:
  > "Products may not publicly display a player's match history from the custom match queue unless the player opts in to share this specifically for League of Legends. Otherwise, a player's custom match data may only be made available to them using RSO."
- LoL docs, Riot ID migration **[Primary]**:
  > "For third-party apps, displaying Riot IDs in place of summoner names within frontend fields is now necessary."
- API Terms **[Primary]**:
  > "Using the Riot Games API for any Application to violate anyone's privacy rights ..."
  > "Sending messages to or communicating with (or attempting to do the foregoing) other users of the Game through Game Information obtained from the Riot Games API."

**Sources**
- https://developer.riotgames.com/policies/general (May 29, 2025)
- https://support-developer.riotgames.com/hc/en-us/articles/22698591841939-General-Policies (edited 2025-05-29)
- https://developer.riotgames.com/docs/lol (no date shown on the page)
- https://support-developer.riotgames.com/hc/en-us/articles/22698698001939-League-of-Legends (edited 2025-03-11)
- https://developer.riotgames.com/terms (Dec 9, 2013)

---

## 3. Data storage, caching, retention, deletion

**Direct answer**
- **Caching.** The policies are **silent** on how long you may store or cache match data. No rule says "don't store" and no maximum cache time is given, so storing match data for display is implicitly allowed. You must stop using it and delete all of it if your license ends.
- **Deletion (GDPR).** Riot commits to GDPR standards globally. It forwards player deletion requests to "all active developers" as lists of identifiers "through Riot Channels". The channel isn't specified further; in practice, watch Developer Portal messages and email.
- **Refresh cadence.** A 2018 DevRel post recommends:
  - deleting associations with accounts renamed to `rtbf(summonerID)`
  - re-syncing player accounts **at least once every 30 days**

  Those are recommendations, not hard rules. The rtbf-rename mechanism predates Riot IDs, and we found no current replacement for it.
- **Non-users.** No specific rule covers storing data about players who never signed up. The general privacy, "no data broker" and de-anonymization rules still apply, and so does GDPR if you have EU users.
- **Retention on Riot's side.** Match data is kept 2 years and timelines 1 year, and a player's match list shows at most the last 1,000 matches. **[Secondary]**: this was quoted in a GitHub issue; we did not find it on an official page.

**Quotes**
- API Terms, GDPR **[Primary]**:
  > "While GDPR is a European Union regulation Riot Games has committed to following the standards put forth in the regulation globally. As a developer using the Riot Games API, you may have access to personal data subject to the GDPR. When Riot Games receives a request from an end user to delete their personal data, we will be passing the request to all active developers by sharing a list of identifiers (e.g. accountId) for the end users through Riot Channels."
- API Terms, Termination **[Primary]**:
  > "Upon termination of these API Terms, You shall immediately cease using the Materials, including without limitation any Game Information in Your possession, as well as delete all of the Game Information in Your possession."
- LoL Developer API Policy **[Primary]**:
  > "No apps serving as a 'data broker' between our API and another third-party company."
- DevRel post "GDPR Right to be Forgotten Compliance" **[Primary]**:
  > "Accounts that have been forgotten by Riot Games will have their summoner names renamed to the following format: rtbf(summonerID) ... When you detect a summoner name following this format, we recommend removing any associations with the account that you may have. Additionally we recommend updating the accounts of players at least once every 30 days."
  > "UPDATE 03/4/19: ... We are now renaming summoners to rtbf(SummonerID) and changing the level to 1 when a RTBF request is complete."
- GitHub issue #1175 comment **[Secondary]**:
  > "Match data is retained for 2 years, match timelines for 1 year. A player's match list will only show up to the last 1000 matches played."

**Sources**
- https://developer.riotgames.com/terms (Dec 9, 2013)
- https://developer.riotgames.com/docs/lol
- https://www.riotgames.com/en/DevRel/gdpr-right-to-be-forgotten-compliance (Sept 28, 2018; updated Mar 4, 2019)
- https://github.com/RiotGames/developer-relations/issues/1175 (Aug 1, 2026) **[Secondary]**

---

## 4. Branding, assets, names and domains

**Direct answer**
- **Game assets.** Champion, item and other icons from **Data Dragon** are explicitly allowed. They fall under "Data Dragon" (General Policies) and "Game-Specific static data" (LoL policy).
- **Community Dragon** isn't Riot's. It is a fan project that runs under LJJ, and Riot's policies neither name nor approve it. Its use by developers is widespread but a gray area. Prefer Data Dragon, and use CDragon only for assets DDragon lacks, such as Mayhem augment icons.
- **Logos and trademarks.** Press Kit logos may be used only where "inevitable" or "unavoidable" to serve the product's core value.
- **App name and domain:**
  - **Legal Jibber Jabber** forbids registering domain names or social accounts "that uses Riot Games or any of our trademarks, trade names, character names, etc." and forbids using the marks as search keywords, unless you have a written license.
  - **Recommendation:** avoid "League of Legends", "LoL", "Riot", champion names and "ARAM: Mayhem" in the domain and app name. Using the words descriptively in page text ("stats for ARAM: Mayhem players") is normal.
  - **Silence:** the policies don't say whether "ARAM" alone is a Riot trademark; trademark status wasn't verified. It is safest to treat it as covered by "names related to our IP".
- **Boilerplate** must appear "in a location that is readily visible to players". The site footer on every page is the usual placement. There are three slightly different official versions (below). Using the General Policies wording is fine. The LJJ notice is a separate requirement for fan projects that use Riot assets, and adding both costs nothing.

**Quotes**
- General Policies, Core Policies **[Primary]**:
  > "Use the following assets in the development and marketing of your product: Data Dragon / Press Kit / Using Riot logos, trademarks etc. from the Press Kit must be limited to those cases where such use is inevitable to serve the core value of the product"
  > "You must post the following legal boilerplate to your product in a location that is readily visible to players"
  > "[Your product] isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc."
- LoL Developer API Policy (same requirement, slightly different wording) **[Primary]**:
  > "[Your Product Name] is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc"
  > "Only the following Riot IP assets may be used in the development and marketing of your product: Press kit ... Example: Using Riot logos and trademarks from the Press Kit must be limited to cases where such use is unavoidable in order to serve the core value of the product. / Game-Specific static data"
- LoL docs, Data Dragon **[Primary]**:
  > "Data Dragon is our way of centralizing League of Legends game data and assets, including champions, items, runes, summoner spells, and profile icons. All of which can be used by third-party developers."
- Legal Jibber Jabber, section 5 **[Primary]**:
  > "Unless you have a written license agreement with us, you may not use any of our logos or trademarks anywhere in your Project or on any website, advertising material, video, or other publication. You may not register domain names, social media accounts, or similar stuff that uses Riot Games or any of our trademarks, trade names, character names, etc. You may not use our trademarks or names related to our IP as keywords or internet search tags."
- Legal Jibber Jabber, section 6 **[Primary]**:
  > "[The title of your Project] was created under Riot Games' "Legal Jibber Jabber" policy using assets owned by Riot Games.  Riot Games does not endorse or sponsor this project."
- API Terms **[Primary]**:
  > the Application must not "make any direct or indirect reference thereto in a way that does or may constitute a direct or indirect endorsement, certification or approval by Riot"
- Community Dragon self-description **[Secondary]**:
  > CommunityDragon "was created under Riot Games' 'Legal Jibber Jabber' policy ... Riot Games does not endorse or sponsor this project."

**Sources**
- https://developer.riotgames.com/policies/general (May 29, 2025)
- https://developer.riotgames.com/docs/lol
- https://www.riotgames.com/en/legal (August 2018)
- https://developer.riotgames.com/terms (Dec 9, 2013)
- https://www.communitydragon.org/documentation **[Secondary]**

---

## 5. Competitions, leaderboards, prizes

**Direct answer**
- **Leaderboards.** A weekly stat leaderboard (most damage, highest AP, biggest crit) among signed-up users is **likely allowed**, but it isn't pre-approved.
  - Ranked alternatives and MMR/Elo calculators are banned.
  - The support copy adds an **explicit carve-out**: leaderboards or rankings built on "a third party platform's community tournaments or challenges that would not reasonably be interpreted as official are allowed."
  - Weekly single-stat challenges fit that carve-out as long as they don't look official and don't produce a skill rating.
  - Avoid anything that reads as a general "best player" or skill ranking, such as a composite score across all games.
  - "Official Ladder Leaderboards" is the only leaderboard type on the pre-approved production use-case list.
- **Prizes: high risk. Don't offer them without asking Riot in writing first.**
  - The **API Terms** forbid using the API "to sponsor or operate any contest, sweepstakes or other promotion". Read literally, that covers API-driven competitions with prizes. The terms date from 2013 but are still the ones in force.
  - The **General Policies** tournament rules add requirements if there are entry fees: at least 70% of fees go to the prize pool, win conditions must be fair and transparent, and no gambling. The portal copy also requires at least 20 participants; the support copy drops that.
  - The **LoL Esports Community Competition Guidelines (Aug 3, 2026)** now replace the NA/EU tournament organizer policies. They allow community competitions (including "an online community competition") with **no caps** on prizes, entry fees or sponsorships. They forbid:
    - Riot logos in event marketing
    - implying the event is official
    - gambling, fantasy and crypto sponsors
  - **Scope is ambiguous.** Those guidelines are written for tournaments and events, and they don't clearly cover an API-driven stat leaderboard. They also don't override the API Terms' contest clause.
  - **Legal risk outside Riot's rules.** Paid entry plus prize can be illegal gambling or a sweepstakes under local law.

**Quotes**
- General Policies, Game Integrity (portal copy) **[Primary]**:
  > "Products cannot create alternatives for official skill ranking systems such as the ranked ladder. Prohibited alternatives include MMR or ELO calculators."
- Support copy of General Policies and support LoL policy (adds a sentence) **[Primary]**:
  > "... Prohibited alternatives include MMR or ELO calculators. Leaderboards or rankings based off of a third party platform's community tournaments or challenges that would not reasonably be interpreted as official are allowed."
- LoL Game Policy, Examples of Approved Use Cases for Production Keys **[Primary]**:
  > "Showing (self) player stats / Running tournaments. / Training tools that allow players to view their own match histories and aggregate stats. / Looking For Game (LFG) tools. / ... / Aggregate player stats (no specific players). / Official Ladder Leaderboards."
- API Terms **[Primary]**:
  > "Using the Riot Games API for any Application to violate anyone's privacy rights ..., to infringe on intellectual property rights ..., to sponsor or operate any contest, sweepstakes or other promotion, to harass or defame others ..."
- General Policies, Tournament Policies (portal copy) **[Primary]**:
  > "Tournaments must / Follow all monetization policies above / Allot at least 70% of the entry fees to the prize pool / Win conditions must be fair and transparent to players (we determine fair) / Must have at least 20 participants / Not include any gambling"

  The support copy omits "Must have at least 20 participants".
- NA and EU Tournaments support articles (edited 2026-09-18) **[Primary]**:
  > "This page has been updated. Please refer to the League of Legends Esports Community Competition Guidelines for the most current rules and information."
- LoL Esports Community Competition Guidelines (Aug 3, 2026) **[Primary]**:
  > "You're free to organize League of Legends competitions at nearly any scale, whether that's a local LAN at your PC café, a school or university, an online community competition, an open bracket, or a larger invitational event."
  > "There are no fixed caps on entry fees, sponsorship revenue, prize pools, or spectator ticketing under these guidelines."
  > "That means you may not: Use Riot Games logos in event marketing ... Present your tournament as an official Riot or LoL Esports competition. Your event name and promotional materials should clearly communicate that your competition is not an official Riot Games or LoL Esports event."
  > "Don't mishandle prize money, entry fees, or sponsorship commitments."
  > Restricted sponsors include "Gambling, sportsbooks, and casinos / Fantasy esports operators (including daily fantasy) / ... Cryptocurrencies, NFTs, or unregulated financial instruments ..."

**Sources**
- https://developer.riotgames.com/policies/general (May 29, 2025)
- https://support-developer.riotgames.com/hc/en-us/articles/22698591841939-General-Policies (edited 2025-05-29)
- https://developer.riotgames.com/docs/lol
- https://developer.riotgames.com/terms (Dec 9, 2013)
- https://support-developer.riotgames.com/hc/en-us/articles/22698775429395-NA-Tournaments (2026-09-18)
- https://lolesports.com/en-GB/news/lol-esports-community-competition-guidelines (Aug 3, 2026)

---

## 6. Game-mode-specific rules: augments, ARAM: Mayhem data, queue ID

**Direct answer**
- **Augment policy.** The written policy bans displaying win rates for "Augments or Arena Mode items". It doesn't say whether this covers ARAM: Mayhem augments, but the wording ("Augments", not "Arena augments") reads broadly enough to cover them. The app already avoids augment win rates, which is correct.
- **Mayhem match data is private in match-v5 (the blocker).**
  - **What fails:** `GET /lol/match/v5/matches/{matchId}` returns **403** for ARAM: Mayhem games (reported Oct 22, 2025). Timelines are presumably also blocked; we didn't test this directly.
  - **What still works:** match ID lists via `by-puuid/.../ids` appear to work. Per issue #1175, though, Mayhem games are left out of the returned match list even though they count toward the 1,000-match cap.
  - **Riot's position:** issue #1109 was closed Dec 18, 2025. A commenter whose GitHub profile says "Senior Backend Software Engineer at Riot Games" wrote: **"Expected behavior. Mayhem matches are private."**
  - **Still open:** feature request #1154 ("Release ARAM Mayhem match data on API without win/loss stats"), last activity June 10, 2026. No Riot reply.
  - **Third-party sites:** aramstats.lol said on 6/23/26 that Mayhem data is "unavailable in the Riot API".
  - **Special access exists but is private.** One site operator (a community member, not Riot) says they have "legitimate access to all Mayhem games" under "a very strict set of rules agreed upon between the Game Modes team" and themselves. So private access is possible but negotiated case by case, and there is no public process for it.
  - **Workarounds** rely on the local League Client API (LCU). They only see the signed-in user's own games, they fall outside the official Web API, and they bring their own policy questions (register the product, Vanguard, etc.).
  - **No official announcement.** We found no DevRel blog post or X post about Mayhem being private. The evidence is the 403 behavior plus the Riot engineer's GitHub comment.
- **Missing augment fields (separate issues, Arena-focused):**
  - #1059: `playerAugment5`/`playerAugment6` always 0 (open)
  - #1157: Arena augment data incomplete (open, May 2026)

  These don't matter for Mayhem while the Mayhem endpoints return 403.
- **Queue ID.** **2400** = "ARAM: Mayhem" on Howling Abyss, confirmed in Riot's official `queues.json` (added around Dec 26, 2025 per issue #1114). The CommunityDragon client data also lists 2401, 2403 and 2405 ("ARAM: Mayhem"), 2410 ("ARAM: Mayhem Tournament") and 2450 ("ARAM: Mayhem Classic-ish"), plus custom-game variants 3240, 3270 and 3280 **[Secondary]**. Classic ARAM is 450.

**Quotes**
- LoL Game Policy, Unapproved Use Cases **[Primary]**:
  > "Products cannot display win rates for Augments or Arena Mode items. This applies to all websites, applications and overlays."
  > "Products may not provide any game-session-specific information that would be previously unknown to the player."
- Official queues.json **[Primary]**:
  > `{"queueId": 2400, "map": "Howling Abyss", "description": "ARAM: Mayhem", "notes": null}`
- GitHub issue #1109, comment from lucasMesquitaBorges (profile: Riot Games engineer), 2025-12-18 **[Secondary; the author appears to work at Riot, but this isn't a policy page]**:
  > "Expected behavior. Mayhem matches are private."
- Same thread, 2026-03-31, community member **[Secondary]**:
  > "No, its private, there are no plans for that to change that anyone is aware of"
- Issue #1154, community member geozukunft **[Secondary]**:
  > "**I** do have legitimate access to all Mayhem games for the purposes of my website with a very strict set of rules agreed upon between the Game Modes team and me to not show any stats that they don't want to be public."

**Sources**
- https://developer.riotgames.com/docs/lol
- https://static.developer.riotgames.com/docs/lol/queues.json (fetched 2026-09-27)
- https://github.com/RiotGames/developer-relations/issues/1109 (opened 2025-10-22, closed 2025-12-18) **[Secondary]**
- https://github.com/RiotGames/developer-relations/issues/1154 (open; last activity 2026-06-10) **[Secondary]**
- https://github.com/RiotGames/developer-relations/issues/1114 (closed 2025-12-26) **[Secondary]**
- https://github.com/RiotGames/developer-relations/issues/1175 (2026-08-01) **[Secondary]**
- https://aramstats.lol/updates (entry 6/23/26) **[Secondary]**
- https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/queues.json **[Secondary]**

---

## 7. Keys, approval, RSO

**Direct answer**

| Key | Rate limit (per region) | Allowed use | Public site? |
|---|---|---|---|
| Development | 20 req/1s, 100 req/2min (change log, 2017). Expires every 24h. | Tinkering and prototypes "not meant for public consumption" | **No.** "You may not maintain a public product with a development API key." Nothing allows even a brief public launch. |
| Personal | 20 req/1s, 100 req/2min. Never raised. | Just the developer or "a small private community"; personal sites. Standard APIs only, no Tournaments API. Requires a registered product with a detailed description. | **No.** "public consumption includes open alpha/beta tests" |
| Production | Starting limit 500 req/10s, 30,000 req/10min. Can be raised later. | Public products. One product per key. | **Yes** |

- **Private group gray zone.** A personal key may serve "a small private community", for example a friends group that signs up. How small, and whether invite-only signup counts, isn't defined.
- **Production application requirements:**
  - a website on a domain you own, verified by uploading a text string
  - a functioning or near-complete app, or a testable prototype, showing the user flows
  - **Terms of Service and Privacy Policy pages**
  - no GitHub repos accepted in place of a working site

  Reviews run weekly and can take up to about 3 weeks.
- **RSO.** Only for approved **production** applications. Newly approved production apps receive an invite to apply. You can't get RSO on a dev or personal key.
- **Rate limits are a secondary blocker.** With Mayhem private (Q6), a production key still wouldn't return Mayhem matches unless Riot grants special access.

**Quotes**
- Developer Portal docs **[Primary]**:
  > "DEVELOPMENT API KEYS ... These interim API keys are temporarily granted for products that are not meant for public consumption but benefit from temporary access to the API. The purpose of a development API key is for you to tinker with the Riot Games API and potentially develop a prototype ... They also deactivate every 24 hours."
  > "PERSONAL API KEYS ... Personal API keys should be used for products that are intended for just the developer or a small private community. These products can be registered without the verification process, but won't be approved for rate limit increases. You may request access to the Standard APIs, but not the Tournaments API. Personal keys require a detailed description of the product."
  > "The rate limit for a personal keys is by design very limited: 20 requests every 1 second / 100 requests every 2 minutes"
  > "You may not run your application for public consumption using a personal key, regardless of how long the approval process for your production key takes. Note that public consumption includes open alpha/beta tests."
  > "You may not maintain a public product with a development API key. ... Typically requires a working prototype before receiving an API key. ... 500 requests every 10 seconds / 30,000 requests every 10 minutes"
- API change log (July 5, 2017) **[Primary]**:
  > "Development API keys now expire after 24 hours. ... the rate limit for these keys has been raised to 20 calls every second and 100 calls every 2 minutes."
- FAQ / Production Key Applications **[Primary]**:
  > "Production keys are reserved for fully functioning applications that can clearly demonstrate their user flows. We need to see a website to understand what your app does, view your Terms of Service and Privacy Policy, and to make sure your app is in a good state for a production key."
  > "Can I submit my Github for a production key? No."
  > "We cannot grant production keys to applications without a verified website."
  > "Applications are typically reviewed weekly for the previous week. However, ... sometimes the review process can take up to three weeks."
- LoL docs, Game Policy **[Primary]**:
  > "Riot needs to see the user flow to understand what your intended player experience is, such as account creation process, login pipeline, or queuing up for match pipeline. You must also send a link to a working site, mockup, prototype, or rendering where it is easy to understand the user flows of the tool."
  > "RSO or Riot Sign On, allows players to safely link their Riot Account to other applications. This access is only available to developers with Production Level API Keys."
- FAQ, RSO **[Primary]**:
  > "RSO Clients are only available for applications that have an existing, approved production application ID. All newly approved production applications will receive a link inviting them to apply for RSO access."
- Developer Portal docs, review criteria **[Primary]**:
  > "If your website isn't complete, we're unlikely to approve your product."

**Sources**
- https://developer.riotgames.com/docs/portal (no date shown; support copy edited 2024-05-30)
- https://www.riotgames.com/en/DevRel/riot-games-api-change-log
- https://developer.riotgames.com/docs/faqs
- https://support-developer.riotgames.com/hc/en-us/articles/22801383038867-Production-Key-Applications
- https://support-developer.riotgames.com/hc/en-us/articles/22801670382739-RSO-Riot-Sign-On
- https://developer.riotgames.com/docs/lol

---

## Action items for this app

1. **Resolve the data-source blocker before building further.** Confirm the 403 with your dev key on a known Mayhem match ID. Then open a support-site ticket (https://support-developer.riotgames.com) describing the app, and ask whether special Mayhem data access exists for a stat-competition product with no win rates and no augment stats. Also decide on a fallback: either widen scope to classic ARAM (queue 450) and Arena, where match-v5 works, or use an LCU-based uploader for users' own games, which needs its own policy review.
2. **Don't launch publicly on the dev key**, not even briefly. Register the product now. Use a personal key only for a small private friends group, and apply for a production key when a near-complete site exists.
3. **Prepare for the production application:**
   - an owned, verified domain
   - Terms of Service and Privacy Policy pages
   - a working site or demo showing the signup, leaderboard and profile flows
4. **Add the boilerplate to the site footer on every page:** "[App name] isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc." Optionally add the LJJ notice too.
5. **Choose a name and domain without Riot marks:** no "League", "LoL", "Riot", "ARAM", "Mayhem" or champion names. No Riot logos. Use Data Dragon for icons; use CommunityDragon only where needed, as best effort.
6. **Frame leaderboards as unofficial, per-stat weekly challenges.** No composite skill score or MMR-like rating, and no "official" styling.
7. **No prizes for now.** If you want them later, get written confirmation from Riot DevRel first, citing the API Terms' "contest, sweepstakes" clause. Also check local sweepstakes and gambling law. Never combine an entry fee with a prize without legal review.
8. **Handle privacy and data:**
   - Show only current Riot IDs, refreshed via `account-v1`, and never historic names.
   - Don't surface custom-game history.
   - Re-sync stored players at least every 30 days.
   - Build a way to delete a player's data on request (from a user or from Riot's forwarded GDPR lists).
   - Collect only the data the competitions need.
9. **Before monetizing:** product status must be Approved or Acknowledged, the free tier must remain, and any paid features must be "transformative". Ads are fine. Ask Riot before adding subscriptions or paywalls (because of the API Terms' "prior written approval" clause).
10. **Keep tracking these threads:** GitHub issues #1109, #1154 and #1157, the developer portal policies (the two General Policies copies differ), and the DevRel X account.

---

## Sources

| Source | Type | Last updated / date |
|---|---|---|
| https://developer.riotgames.com/policies/general | Primary | May 29, 2025 |
| https://support-developer.riotgames.com/hc/en-us/articles/22698591841939-General-Policies | Primary | May 29, 2025 (edited 2025-05-29T17:12Z; contains extra clauses) |
| https://developer.riotgames.com/policies/game-specific | Primary | Aug 21, 2026 (index page linking to /docs/lol#game-policy) |
| https://developer.riotgames.com/docs/lol | Primary | No date on page |
| https://support-developer.riotgames.com/hc/en-us/articles/22698698001939-League-of-Legends | Primary | Edited 2025-03-11 |
| https://developer.riotgames.com/terms | Primary | Dec 9, 2013 |
| https://developer.riotgames.com/docs/portal | Primary | No date; support copy edited 2024-05-30 |
| https://developer.riotgames.com/docs/faqs | Primary | No date; support FAQ articles edited 2023-12-04 |
| https://support-developer.riotgames.com/hc/en-us/articles/22801383038867-Production-Key-Applications | Primary | Edited 2023-12-04 |
| https://support-developer.riotgames.com/hc/en-us/articles/22801670382739-RSO-Riot-Sign-On | Primary | Edited 2023-12-04 |
| https://support-developer.riotgames.com/hc/en-us/articles/22698775429395-NA-Tournaments | Primary | Edited 2026-09-18 (redirects to LoL Esports guidelines) |
| https://lolesports.com/en-GB/news/lol-esports-community-competition-guidelines | Primary | Aug 3, 2026 |
| https://www.riotgames.com/en/legal (Legal Jibber Jabber) | Primary | August 2018 |
| https://www.riotgames.com/en/DevRel/gdpr-right-to-be-forgotten-compliance | Primary | Sept 28, 2018 (updated Mar 4, 2019) |
| https://www.riotgames.com/en/DevRel/riot-games-api-change-log | Primary | Dev-key entry July 5, 2017 |
| https://static.developer.riotgames.com/docs/lol/queues.json | Primary | Fetched 2026-09-27 |
| https://github.com/RiotGames/developer-relations/issues/1109 | Secondary | 2025-10-22 to 2026-03-31 |
| https://github.com/RiotGames/developer-relations/issues/1154 | Secondary | 2026-04-22 to 2026-06-10 (open) |
| https://github.com/RiotGames/developer-relations/issues/1114 | Secondary | Closed 2025-12-26 |
| https://github.com/RiotGames/developer-relations/issues/1175 | Secondary | 2026-08-01 |
| https://github.com/RiotGames/developer-relations/issues/1157 and /1059 | Secondary | Open |
| https://aramstats.lol/updates | Secondary | Entry 6/23/26 |
| https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/queues.json | Secondary | Fetched 2026-09-27 |
| https://www.communitydragon.org/documentation | Secondary | n/a |
