
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

Install Python 2 or 3, then `pip install selenium colorama python-dateutil`.

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

## Overview of the files

Descriptions for the letters can be found in [Ex Libris Knowledge Base](http://knowledge.exlibrisgroup.com/Alma/Product_Documentation/Alma_Online_Help_%28English%29/Administration/Configuring_General_Alma_Functions/Configuring_Alma_Letters#Letter_Types).

### Templates

The files in `xsl/letters/call_template` contains templates that are used by the other files.
We have mostly modified the existing ones, but have also added a few new. These are marked *(new)* below.

* `footer.xsl`: Templates for footer elements:
  * `lastFooter`: a closing greeting ("Questions? Contact us... Kind regards... etc.)
  * `contactUs`: link to contact information
  * `myAccount`: link to my account in Primo
* `header.xsl`: Templates for style and introduction:
  * `normalizedDate` *(new)* : generates a date in `YYYY-MM-DD` format from `dd/mm/yyy` and strips away time.
  * `head` : Organization logo, letter name (heading) and right-aligned date
  * `headWithoutLogo` *(new)* : Letter name (heading) and right-aligned date
* `mailReason.xsl`:
  * `toWhomIsConcerned` : Defines the greeting ("Hi!" in our case) used in most emails.
* `senderReceiver.xsl`:
  * `senderReceiver` : The full name and address of the sender and receiver. Used in formal letters.
* `recordTitle.xsl` / `smsRecordTitle.xsl`:
  * `recordTitle` : Human-readable (not barcodes) short representation of a document/record (title + other metadata to identify the document), used when referring to a document/record in communication with users.
* `style.xsl`: Various CSS

## Specific elements

### Libnummer (norsk ISIL-kode)

Tre av sedlene brukes som sendelapper mellom bibliotek og har derfor libnummer nederst.
Nummeret må plasseres i en fast avstand fra bunnen av arket fordi det skal være synlig i
vinduskonvolutter for sending av dokumenter. For sending av bøker stikkes sedlene i bøkene
slik at arket stikker ut på bunnen av boka med libummeret synlig.

* `FulReasourceRequestSlipLetter`: Utlån til folkebibliotek og andre bibliotek som ikke bruker Alma. Libnummer hentes fra `notification_data/user_for_printing/identifiers/code_value[1]/value`.
* `ResourceSharingShippingSlipLetter`: Utlån til annet Alma-bibliotek basert på bestilling (*lending requests*). Libnummer hentes fra `notification_data/partner_shipping_info_list/partner_shipping_info[1]/address5`
  * Merk: `FulIncomingSlipLetter` (også kjent som `Resource sharing Lending Slip Letter`) ligner ganske mye på `ResourceSharingShippingSlipLetter`, og mange tror derfor denne kan brukes som sendeseddel for artikkelkopier – men denne mangler libnummer og adresseinformasjon og er nok ikke ment som det. Når bestillingen har fått status `Shipped` får man ut en `ResourceSharingShippingSlipLetter` som brukes som sendelapp. Gå til ship item via almamenyen, velg ship non returnable og huk av for automatisk slip. Eller trykk ‘print slip’ etter man har valgt ‘ship item’, ‘ship non returnable’ e.l.
* `FulTransitSlipLetter`: Sendelapp internt på UBO. Her har vi en hardkodet mapping fra `calculated_destination_name` til libnummer fordi libnummeret ikke er tilgjengelig i XML-dataene og lista over mottakere er overkommelig å vedlikeholde manuelt (mens vi venter på en bedre løsning).

For å få plassert libnummeret i en fast avstand fra bunnen av arket har vi konfigurert
html2ps ([dokumentasjon](http://user.it.uu.se/~jan/html2psug.html)) til å legge innhold
fra meta-taggen `libnummer` i bunntekst (footer):

```
@html2ps{
    footer {
      left: "$[libnummer]";
      center: " ";  /* override default value */
      font-size: 48pt;
    }
}
@page {
   margin-left: 2cm;
   margin-right: 3cm;
   margin-top: 0;
   margin-bottom: 6cm;
}
```

html2ps-oppsettet driftes av USITs [gruppe for drift av meldingstjenester](http://www.usit.uio.no/om/organisasjon/it-drift/kd/gmt/index.html). For å gjøre endringer i konfigurasjonen sender vi epost til postmaster at rt.uio.no der vi beskriver endringene – det har gått greit så langt, de svarer raskt.

Eksempel på en meta-tagg: `<meta name="libnummer" content="103 0310"/>`.


## Tips

* Documentation: https://knowledge.exlibrisgroup.com/Alma/Product_Documentation/Alma_Online_Help_%28English%29/Administration/Configuring_General_Alma_Functions/Configuring_Alma_Letters

* Footer: The link targets for "Contact us" and "My account" are set as `email_my_account` and `email_contact_us` in the General Customer Parameters mapping table (Administration > General Configuration > Configuration Menu > Other Settings). Despite the naming, these can be http URLs.

* For Sublime Text users: Sublime Text does not highlight .xsl files by default. Click the current syntax type in the lower right corner of the window. This will open the syntax selection menu with the option to Open all with current extension as... at the top of the menu. Select XML.
