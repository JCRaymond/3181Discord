# 3181 Discord Scripts

To use, simply set the value of `"token"` in `config.json` to the token for your application. The name of the server created, number of sections and section names, as well as the number of groups per section is all specified in this file, and can be changed as needed.

To create a token, navigate to the [Discord Developer Portal]("https://www.discord.com/developers/applications"), and create a `New Application`. Then, go to the `Bot` tab on the left, and click `Add Bot`. It is recommended that you turn off the `Public Bot` option, since this is likely a private bot. You should now be able to copy the `Token`, and paste it into the config. Make sure to leave the double quotes around the token.

Requires `discord.py` and Python 3.6+ (fstrings).

Anyone is welcome to re-purpose this code to make their own Discord server, it mainly relies on the `layout.json` file to determine how the server should be setup.
