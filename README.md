
This is a collection of the XSL files used to generate letters and slips in Alma, as customized by the University of Oslo Library. Included in this repo are also scripts for pulling and pushing the files to Alma using Selenium browser automation (since no API or other access method is available).

## Configuration

Copy `config.cfg.dist` to `config.cfg` and fill in the empty values:

* `domain` is your Feide domain, e.g. `uio.no`
* `username` is your Feide username
* `password` can be left blank if you want to be asked for it each time. This is the recommended solution,
  since it's not recommended to store your password in plain text.
* `firefox_path` is the path to the Firefox binary (the path should not be quoted even if it contains spaces)
  * Example on Mac (Firefox installed through homebrew-cask): `/opt/homebrew-cask/Caskroom/firefox/38.0.5/Firefox.app/Contents/MacOS/firefox-bin`
  * Example on Windows: `C:\Program Files (x86)\Mozilla Firefox\firefox.exe`

Dependencies:

Install Python 2 or 3, then `pip install selenium colorama python-dateutil`

## Workflow

- `git pull` to pull in changes from other users.

- Optional: `python slipsomat.py pull` will check if any files have been updated
  directly in Alma (without using `slipsomat`), fetch those and update `status.json`.
  Comparison is done by comparing the update date in Alma with the update date in `status.json`.
  Alma does not provide time granularity for updates, only date, so for files that have been
  modified today, the script will open the letter in Alma to get the text and calculate a
  checksum to compare with the checksum in `status.json`.
  Note: If you skip this step, `slipsomat` will still warn you if you try to push a
  letter that have been modified remotely (checksums not matching), but then you will
  have to merge manually.

- After having made modifications to one or more letters, run `python slipsomat.py push`
  to push the updates to Alma. Comparison is done by comparing checksums of the local files
  with the checksums in `status.json`. Before making any changes, the script will print a list
  of files and confirm that you want to upload these.

- After having tested the modifications, do a `git commit` (remember to include the updated
  `status.json`) and `git push`

## Todo

- Add command for getting/pushing strings from the "Letter emails" page.


## Tips

* Documentation: https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/Alma_Online_Help_%28English%29/Administration/Configuring_General_Alma_Functions/Configuring_Alma_Letters

* Footer: The link targets for "Contact us" and "My account" are set as `email_my_account` and `email_contact_us` in the General Customer Parameters mapping table (Administration > General Configuration > Configuration Menu > Other Settings). Despite the naming, these can be http URLs.

* For Sublime Text users: Sublime Text does not highlight .xsl files by default. Click the current syntax type in the lower right corner of the window. This will open the syntax selection menu with the option to Open all with current extension as... at the top of the menu. Select XML.
