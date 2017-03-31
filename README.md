
This repo contains our `slipsomat` script for pulling and pushing files to Alma
using Selenium browser automation. The script computes and stores checksums of
all the letters to protect you from overwriting the work of others.

Huh?!? Using something like Selenium for synchronizing files might seem like a
rather silly approach. It is! It works… sort-of, but we'd much prefer that
Ex Libris implemented a proper protocol we could use, so please go and vote for
[this idea](http://ideas.exlibrisgroup.com/forums/308173-alma/suggestions/12471084-synchronizing-xsl-templates-with-external-systems) on Ideas
Exchange to put some pressure on Ex Libris to do just that.

## Setup

You will need Python 2.7 or 3.3 or later. Install using `python setup.py install`,
or `pip install -e . ` if you plan to hack on the script and want an *editable install*.

Once installed, you can run `slipsomat` from any directory containing a `slipsomat.cfg`
file. To get started with your own files, you can create an empty directory with a
`slipsomat.cfg` with the following contents:

```
[login]
domain=
instance=
institution=
auth_type=SAML
username=
password=

[selenium]
browser=firefox
firefox_path=
```

where you fill in the blank values.

* `domain` is your Feide domain, e.g. `uio.no`
* `instance` is the Alma instance name, e.g. `bibsys-k`
* `institution` the Alma institution name, e.g. `47BIBSYS_UBO`
* `auth_type=SAML` means you authenticate using Feide.
* `username` is your (Feide) username
* `password` can be left blank if you want to be asked for it each time. This
  is the recommended solution, since the password is stored in plain text.

* `browser` can be set to `firefox`, `chrome` or `phantomjs`. Currently, `firefox`
  is the driver we've had the most success with, and it's also the easiest to
  get started with. Both `chrome` and `phantomjs` requires separate driver
  installs, while `firefox` can use your standard firefox installation.
* `firefox_path` is the path to the Firefox binary (the path should not be quoted
  even if it contains spaces)
  * Example on Mac (Firefox installed through homebrew-cask):
  `/opt/homebrew-cask/Caskroom/firefox/38.0.5/Firefox.app/Contents/MacOS/firefox-bin`
  * Example on Windows: `C:\Program Files (x86)\Mozilla Firefox\firefox.exe`


## Debugging

If you have `inquirer` installed (does not work on Windows), slipsomat will give
you some options for starting a debug session if the script crashes.

## Getting started

The `slipsomat` command will give you an interactive shell where you can type various
commands. Type `help` for an overview.

To get started in an empty directory, type `pull` to pull in all the XSLT files from your Alma
instance and store them in a folder named `xsl` (will be created if not there already).
Optionally, type `defaults` to pull in all default letters too. Note that a `status.json` file
is also created. This holds the checksums for all the letters, allowing the script to easily keep
track of which files have been modified (locally or in Alma).

Once you have a directory with all your files you're free to put them under version control
if you like. Here's the repo we use for our files: https://github.com/scriptotek/alma-letters-ubo

## Workflow

In a workspace directory (a directory having a `slipsomat.cfg` file):

1. Start by doing `git pull` to pull in changes from other users.

2. `slipsomat` to start the script

3. Optional: the slipsomat command `pull` will check if any files have been updated
  directly in Alma (without using `slipsomat`), fetch those and update `status.json`.
  Comparison is done by comparing the update date in Alma with the update date in `status.json`.
  Alma does not provide time granularity for updates, only date, so for files that have been
  modified today, the script will open the letter in Alma to get the text and calculate a
  checksum to compare with the checksum in `status.json`.
  Note: If you skip this step, `slipsomat` will still warn you if you try to push a
  letter that have been modified remotely (checksums not matching), but then you will
  have to merge manually.

4. After having made modifications to one or more letters, run the slipsomat command `push`
  to push the updates to Alma. Comparison is done by comparing checksums of the local files
  with the checksums in `status.json`. Before making any changes, the script will print a list
  of files and confirm that you want to upload these.

5. After having tested the modifications, do a `git commit` (remember to include the updated
  `status.json`) and `git push`

The shell has a command history, and tab completion. For example `test Ful<tab><tab>`.

### Updating default letters

- Use the `slipsomat` command `defaults` to pull in all default letters.
  Note that the command takes quite some time to run, since all letters have to
  be checked as Alma provides no information whatsoever on when the default
  letters were last updated.

## See also

* [open issues](https://github.com/scriptotek/alma-slipsomat/issues)
* [alma-letters-ubo](https://github.com/scriptotek/alma-letters-ubo) for our XSLT files
