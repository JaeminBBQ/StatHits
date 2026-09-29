# Riot Compliance Checklist

Hard rules. Research and quotes are in `riot-developer-policy-findings.md`; the player ToS is in `riot-terms-of-service-2024-12-01.txt`.

## Always
- [ ] Footer on every page, verbatim (`APP_NAME` filled in):
  > "{APP_NAME} isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc."
- [ ] Official Riot API only. No LCU, Live Client Data API, replay parsing, or scraping of Riot sites.
- [ ] No MMR/Elo/skill rating, no tiers, and never the words "ranked"/"rank" for our features.
- [ ] No augment or Arena item win rates. Showing a player's own augment picks is fine.
- [ ] Riot IDs (`gameName#tagLine`), never summoner names. Never show historic Riot IDs.
- [ ] Don't de-anonymize or expose players the game hides.
- [ ] The API key is never exposed client-side, logged, or committed.
- [ ] App name and domain contain no Riot trademarks or champion names.
- [ ] Images: Data Dragon only (Community Dragon is a gray area; ask before using it).

## Before going public
- [ ] Register the product on the developer portal; get a personal key (small private group) → production key (public).
- [ ] Owned, verified domain; ToS and Privacy Policy pages; a working site showing the user flows.
- [ ] Handle Riot's GDPR deletion requests; let members delete their data.
- [ ] No prizes or contests with prizes without written OK from Riot (API Terms bar operating contests/sweepstakes).
- [ ] Monetization only after approval; a free tier is required; ads are OK; ask Riot before any paywall.
