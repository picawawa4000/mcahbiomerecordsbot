# Minecraft@Home Biome Records Bot

Bot that turns [this](https://docs.google.com/spreadsheets/d/1uiC9-eObIh16oEemAKQoRGp2elyv5nlDcnu_c5lxOtM/edit?gid=0#gid=0) into [this](https://mcseedfinding.miraheze.org/wiki/Largest_Biomes_Records).

For GitHub Actions, use an owner-only OAuth 2 consumer registered as `MCAHBiomeRecordsBot` on [Miraheze Meta](https://meta.miraheze.org/wiki/Special:OAuthConsumerRegistration/propose/oauth2), with permission to edit existing pages. The bot currently has only the `user` group on Meta; Meta requires `autoconfirmed`, `confirmed`, or `sysop` to propose OAuth consumers. Ask a Meta administrator about granting the bot `confirmed` if the registration page refuses access. Once registered, save the access token shown there as the repository Actions secret `MW_OAUTH_TOKEN`. The workflow currently prefers `MW_PASSWORD` so the browser can handle the Cloudflare check; OAuth is used only if no password is configured. Do not commit either secret.

When `MW_OAUTH_TOKEN` is absent, the workflow uses Chromium and `MW_PASSWORD` to log in through the wiki page. This can complete a normal JavaScript challenge, but cannot solve a challenge that requires human interaction. OAuth uses the API directly; it cannot bypass an edge-level Cloudflare block on GitHub-hosted runners.
