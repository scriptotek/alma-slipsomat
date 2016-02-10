
This is a collection of the XSL files used to generate letters and slips in Alma, as customized by the University of Oslo Library. Included in this repo is also scripts for pulling and pushing the files to Alma using Selenium browser automation (since no API or other access method is available).

## Configuration

Copy `config.cfg.dist` to `config.cfg` and fill in the empty values:

* `domain` is your Feide domain, e.g. `uio`
* `username` is your Feide username
* `password` can be left blank if you want to be asked for it each time. This is the recommended solution,
  since it's not recommended to store your password in plain text.
* `firefox_path` is the path to the Firefox binary. If you're on a Mac, this is not the path to the `.app` file. Example on Mac (Firefox installed through homebrew-cask): `/opt/homebrew-cask/Caskroom/firefox/38.0.5/Firefox.app/Contents/MacOS/firefox-bin`.

Dependencies:

Install Python 2 or 3, then `pip install selenium colorama python-dateutil`

## Running

- Run `python slipsomat.py pull` to fetch updated vesions of all XSLT files from Alma.
- `python slipsomat.py push xsl/letters/FulReturnReceiptLetter.xsl` to push a single file. Work-in-progress, be careful.



## Tips

For Sublime Text users: Sublime Text does not highlight .xsl files by default. Click the current syntax type in the lower right corner of the window. This will open the syntax selection menu with the option to Open all with current extension as... at the top of the menu. Select XML.
