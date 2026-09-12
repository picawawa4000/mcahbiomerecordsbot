# Minecraft@Home Biome Records Bot

Bot that turns [this](https://docs.google.com/spreadsheets/d/1uiC9-eObIh16oEemAKQoRGp2elyv5nlDcnu_c5lxOtM/edit?gid=0#gid=0) into [this](https://mcseedfinding.miraheze.org/wiki/Largest_Biomes_Records).

For GitHub Actions, use an owner-only OAuth 2 consumer registered as `MCAHBiomeRecordsBot` on [Miraheze Meta](https://meta.miraheze.org/wiki/Special:OAuthConsumerRegistration/propose/oauth2), with permission to edit existing pages. The bot currently has only the `user` group on Meta; Meta requires `autoconfirmed`, `confirmed`, or `sysop` to propose OAuth consumers. Ask a Meta administrator about granting the bot `confirmed` if the registration page refuses access. Once registered, save the access token shown there as the repository Actions secret `MW_OAUTH_TOKEN`. The workflow prefers this token over `MW_PASSWORD`; the password remains a fallback until OAuth is configured. Do not commit the token.

An HTTP 403 while fetching a login token happens before account authentication. The script includes Cloudflare diagnostics for this response; switching credentials will not necessarily resolve an edge-level block on GitHub-hosted runners.
