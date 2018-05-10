
`slipsomat` is a small tool for pulling and pushing letters to Alma using
Selenium browser automation. It allows to you to keep an up-to-date local
copy of all the letters, so you can keep them under version control. And
by storing checksums of all the letters, it can warn you if you're about
to overwrite a letter that has been modified by someone else without pulling
in their changes.

This tool exists because Alma doesn't provide a way to synchronize the letters,
only a web form to edit them. With over 100 different letters, editing them
using a web form (with no syntax highlighting) is very tedious. We have also
brought this up on Ideas Exchange – feel free to add your vote to
[our idea there](http://ideas.exlibrisgroup.com/forums/308173-alma/suggestions/12471084-synchronizing-xsl-templates-with-external-systems).

## Setup

Slipsomat works with Python 3.3 and later. We also try to maintain Python 2.7
support, but don't always test it, so it may accidentally break. The same goes
for Windows, which we try to support, but don't test regularly, so accidental
incompatibilities might slip in. Please use our
[issue tracker](https://github.com/scriptotek/alma-slipsomat/issues) to report
any problem.

Install with pip:

    pip install -U slipsomat

Once installed, you can run `slipsomat` from any directory containing a
`slipsomat.cfg` config file.
To get started, create an empty directory with a `slipsomat.cfg` file with the
following contents:

```
[login]
auth_type=
domain=
instance=
institution=
username=
password=

[selenium]
browser=firefox
default_timeout=20

[window]
width=1200
height=700
```

where you fill in the blank values.

* Set `auth_type=Feide` if you authenticate using Feide SAML. Set `auth_type=SAML`
  for Shibboleth or other SAML providers (submit an issue if it doesn't work with
  your provider!).
  Set `auth_type=basic` to use the standard Alma login.
* `domain` is your Feide domain, e.g. `uio.no`. If you don't use Feide as your
  SAML provider, you can leave this empty.
* `instance` is the Alma instance name, which is the first part of your ALMA URL.
  If your Alma URL is `bibsys-k.alma.exlibrisgroup.com`, then `bibsys-k` is the
  instance name.
* `institution` the Alma institution name, e.g. `47BIBSYS_UBO`
* `username` is your username.
* `password` can be left blank if you want to be asked for it each time. This
  is the recommended solution, since the password is stored in plain text.
* `browser` can be set to `firefox`, `chrome` or `phantomjs`. The corresponding
  driver must be installed (GeckoDriver for Firefox, ChromeDriver for Chrome).
  I've had success with all three browsers, but from time to time a browser can
  start crashing or freezing at some point. First thing to try then is to upgrade
  both Selenium and the browser driver. If there's still problems, switch to
  another browser for some time. If *that* doesn't help, there might be an issue
  with slipsomat. Please file an issue.

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


### Testing the output of a letter

Alma lets you test the output on the Notification Template page, but doing this
manually each time is boring, so slipsomat provides you with the `test` command
to automate that.

Create a folder called "test-data" in the same folder as the `slipsomat.cfg` file.
Add one or more XML files you want to test there.

Start `slipsomat` and run the command

    test filename.xml

where `filename.xml` is a file in the "test-data" folder. This will upload the
XML file to the Notification Template page and store the resulting HTML output
and a screenshot in the "test-data" folder.

To test multiple files at the same time, you can use Unix style pathname pattern
expansion ("globbing"). E.g. to test all XML files in the "test-data" folder, use the
`*` wildcard character:

    test *.xml

By default, the command will use English as the letter language. To test
another language, just append `@` and the language code to the filename.
Example:

    test filename.xml@nn

You can even test multiple languages in one go by specifying multiple language
codes separated by comma like so:

    test filename.xml@en,no,nn

This can also be used in combination with globbing. To test all XML files in the
"test-data" folder in three languages:

    test *.xml@en,no,nn

## See also

* [open issues](https://github.com/scriptotek/alma-slipsomat/issues)
* the [alma-letters-ubo repo](https://github.com/scriptotek/alma-letters-ubo) for our XSLT files


## Development

### Editable install

If you want an *editable install* that you can hack on yourself:

    git clone https://github.com/scriptotek/alma-slipsomat.git
    cd alma-slipsomat
    pip install -U -e .


### Using slipsomat as a Python library

Given that you have created a `slipsomat.cfg` file, here's how to start
experimenting:

```python
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from slipsomat.worker import Worker
from slipsomat.slipsomat import TemplateConfigurationTable

worker = Worker('slipsomat.cfg')

# Start the browser and log in using the credentials from slipsomat.cfg
worker.connect()

# Open and parse the letters table
table = TemplateConfigurationTable(worker)

# Open the default version of the SmsFulCancelRequestLetter letter
table.open_default_letter('xsl/letters/sms/SmsFulCancelRequestLetter.xsl')

# Use Selenium to click some element
wait = worker.waiter()
element = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Open Alma configuration"]')))
element.click()
```

Note: During development, it might be a good idea to set `default_timeout` in
`slipsomat.cfg` to a small value (like 3 seconds) to avoid having to wait a
long time every time you write a wrong selector.
