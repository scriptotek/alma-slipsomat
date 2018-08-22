# encoding=utf8
from __future__ import print_function

import os
import os.path
import re
import time
import sys
import hashlib
import json
import difflib
import tempfile

from datetime import datetime
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.errorhandler import NoSuchElementException
from xml.etree import ElementTree
from colorama import Fore, Back, Style

try:
    input = raw_input  # Python 2
except NameError:
    pass  # Python 3


def normalize_line_endings(text):
    # Normalize line endings to LF and strip ending linebreak.
    # Useful when collaborating cross-platform.
    return text.replace('\r\n', '\n').replace('\r', '\n').strip()


def color_diff(diff):
    for line in diff:
        if line.startswith('+'):
            yield Fore.GREEN + line + Fore.RESET
        elif line.startswith('-'):
            yield Fore.RED + line + Fore.RESET
        elif line.startswith('^'):
            yield Fore.BLUE + line + Fore.RESET
        else:
            yield line


def resolve_conflict(filename, local_content, remote_content, msg):
    print()
    print('\n' + Back.RED + Fore.WHITE +
          '\n\n  Conflict: ' + msg + '\n' + Style.RESET_ALL)

    msg = 'Continue with {}?'.format(filename)
    while True:
        response = input(Fore.CYAN + "%s [y: yes, n: no, d: diff] " % msg + Style.RESET_ALL).lower()[:1]
        if response == 'd':
            show_diff(remote_content, local_content)
        else:
            return response == 'y'


def show_diff(dst, src):
    src = src.text.strip().splitlines()
    dst = dst.text.strip().splitlines()

    print()
    for line in color_diff(difflib.unified_diff(dst, src, fromfile='Alma', tofile='Local')):
        print(line)


class LetterContent(object):

    def __init__(self, text):
        self.text = text.replace('\r\n', '\n').replace('\r', '\n').strip()
        self.validate()

    @property
    def sha1(self):
        m = hashlib.sha1()
        m.update(self.text.encode('utf-8'))
        return m.hexdigest()

    def validate(self):
        if self.text == '':
            return
        try:
            ElementTree.fromstring(self.text)
        except ElementTree.ParseError as e:
            print('%sError: The file contains invalid XML:%s' % (Fore.RED, Style.RESET_ALL))
            print(Fore.RED + str(e) + Style.RESET_ALL)
            return


class LocalStorage(object):
    """File storage abstraction class."""

    def __init__(self, status_file):
        self.status_file = status_file

    def is_modified(self, filename):
        """Return True if the letter has local changes not yet pushed to Alma."""
        local_content = self.get_content(filename)
        return local_content.text != '' and local_content.sha1 != self.status_file.checksum(filename)

    def get_content(self, filename):
        """
        Read the contents of a letter from disk and return it as a LetterContent object.

        If no local version exists yet, an empty LetterContent object is returned.
        """
        if not os.path.isfile(filename):
            return LetterContent('')
        with open(filename, 'rb') as fp:
            return LetterContent(fp.read().decode('utf-8'))

    def store(self, filename, content, modified):
        """
        Store the contents of a letter to disk.

        The method first checks if the local version has changes that will be overwritten.
        """
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        local_content = self.get_content(filename)
        if local_content.text != '' and local_content.sha1 != self.status_file.checksum(filename):
            # The local file has been changed
            if not resolve_conflict(filename, content, local_content,
                                    'Pulling in this file would cause local changes to be overwritten.'):
                return False

        # Actually store the contents to disk
        with open(filename, 'wb') as f:
            f.write(content.text.encode('utf-8'))

        # Update the status file
        self.status_file.set_checksum(filename, content.sha1)
        self.status_file.set_modified(filename, modified)

        return True

    def store_default(self, filename, content):
        """
        Store the contents of a default letter to disk.

        Since the default letters cannot be uploaded, only downloaded, we do not care to check
        if the local file has changes that will be overwritten.
        """
        defaults_filename = os.path.join('defaults', filename)
        if not os.path.exists(os.path.dirname(defaults_filename)):
            os.makedirs(os.path.dirname(defaults_filename))
        with open(defaults_filename, 'wb') as f:
            f.write(content.text.encode('utf-8'))

        # Update the status file
        self.status_file.set_default_checksum(filename, content.sha1)


class StatusFile(object):

    def __init__(self):
        letters = {}
        if os.path.exists('status.json'):
            with open('status.json') as fp:
                contents = json.load(fp)
            letters = contents['letters']

        self.letters = letters

    def save(self):
        data = {
            'version': 1,
            'letters': self.letters,
        }
        jsondump = json.dumps(data, sort_keys=True, indent=2)

        # Remove trailling spaces (https://bugs.python.org/issue16333)
        jsondump = re.sub(r'\s+$', '', jsondump, flags=re.MULTILINE)

        # Normalize to unix line endings
        jsondump = normalize_line_endings(jsondump)

        with open('status.json', 'wb') as fp:
            fp.write(jsondump.encode('utf-8'))

    def get(self, filename, property, default=None):
        if filename not in self.letters:
            return default
        return self.letters[filename].get(property)

    def set(self, filename, property, value):
        if filename not in self.letters:
            self.letters[filename] = {}
        self.letters[filename][property] = value
        self.save()

    def modified(self, filename):
        return self.get(filename, 'modified')

    def checksum(self, filename):
        return self.get(filename, 'checksum')

    def default_checksum(self, filename):
        return self.get(filename, 'default_checksum')

    def set_modified(self, filename, modified=None):
        if modified is None:
            modified = datetime.now().strftime('%d/%m/%Y')
        self.set(filename, 'modified', modified)

    def set_checksum(self, filename, checksum):
        self.set(filename, 'checksum', checksum)

    def set_default_checksum(self, filename, checksum):
        self.set(filename, 'default_checksum', checksum)


class TemplateConfigurationTable(object):
    """Interface to "Customize letters" in Alma."""

    def __init__(self, worker):
        self.filenames = []
        self.update_dates = []
        self.worker = worker
        self.open()
        self.read()

    def open(self):
        try:
            self.worker.first(By.CSS_SELECTOR, '#TABLE_DATA_fileList')
        except NoSuchElementException:
            self.worker.get('/mng/action/home.do')

            # Open Alma configuration
            self.worker.wait_for_and_click(
                By.CSS_SELECTOR, '#ALMA_MENU_TOP_NAV_configuration')
            # text() = "General"
            self.worker.click(By.XPATH, '//*[@href="#CONF_MENU6"]')
            self.worker.click(By.XPATH, '//*[text() = "Customize Letters"]')
            self.worker.wait_for(By.CSS_SELECTOR, '#TABLE_DATA_fileList')

        return self

    def modified(self, filename):
        idx = self.filenames.index(filename)
        return self.update_dates[idx]

    def set_modified(self, filename, date):
        # Allow updating a single date instead of having to re-read the whole table
        idx = self.filenames.index(filename)
        self.update_dates[idx] = date

    def print_letter_status(self, filename, msg, progress=None, newline=False):
        sys.stdout.write('\r{:100}'.format(''))  # We clear the line first
        if progress is not None:
            sys.stdout.write('\r[{}] {:60} {}'.format(
                progress,
                filename.split('/')[-1],
                msg
            ))
        else:
            sys.stdout.write('\r{:60} {}'.format(
                filename.split('/')[-1],
                msg
            ))
        if newline:
            sys.stdout.write('\n')
        sys.stdout.flush()

    def read(self):

        # Identify the indices of the column headers we're interested in
        elems = self.worker.all(By.CSS_SELECTOR, '#TABLE_DATA_fileList tr > th')
        column_headers = [el.get_attribute('id') for el in elems]
        filename_col = column_headers.index('SELENIUM_ID_fileList_HEADER_cfgFilefilename') + 1
        updatedate_col = column_headers.index('SELENIUM_ID_fileList_HEADER_updateDate') + 1

        # Read the filename column
        elems = self.worker.all(By.CSS_SELECTOR,
                                '#TABLE_DATA_fileList tr > td:nth-child(%d) > a' % filename_col)
        self.filenames = [el.text.replace('../', '') for el in elems]

        # Read the modification date column
        elems = self.worker.all(By.CSS_SELECTOR,
                                '#TABLE_DATA_fileList tr > td:nth-child(%d) > span' % updatedate_col)
        self.update_dates = [el.text for el in elems]

        # return [{x[0]:2 {'modified': x[1], 'index': n}} for n, x in enumerate(zip(filenames, update_dates))]

    def is_customized(self, index):
        updated_by = self.worker.first(By.ID, 'SPAN_SELENIUM_ID_fileList_ROW_%d_COL_cfgFileupdatedBy' % index)

        return updated_by.text not in ('-', 'Network')

    def assert_filename(self, filename):
        # Assert that we are at the right letter
        element = self.worker.wait.until(
            EC.presence_of_element_located((By.ID, 'pageBeanconfigFilefilename'))
        )
        elt = element.text.replace('../', '')
        assert elt == filename, "%r != %r" % (elt, filename)

    def open_letter(self, filename):
        self.open()

        # Open a letter and return its contents as a LetterContent object.
        index = self.filenames.index(filename)
        self.worker.wait.until(EC.presence_of_element_located(
            (By.ID, 'SELENIUM_ID_fileList_ROW_%d_COL_cfgFilefilename' % index))
        )

        time.sleep(0.2)

        # Open the "ellipsis" menu.
        self.worker.scroll_into_view_and_click(
            '#input_fileList_{}'.format(index), By.CSS_SELECTOR)
        time.sleep(0.2)

        if self.is_customized(index):
            # Click "Edit" menu item
            edit_btn_selector = '#ROW_ACTION_fileList_{}_c\\.ui\\.table\\.btn\\.edit a'.format(index)
            self.worker.scroll_into_view_and_click(edit_btn_selector, By.CSS_SELECTOR)
        else:
            # Click "Customize" menu item
            customize_btn_selector = '#ROW_ACTION_fileList_{} a'.format(index)
            self.worker.scroll_into_view_and_click(customize_btn_selector, By.CSS_SELECTOR)

        # We should now be at the letter edit form. Assert that filename is indeed correct
        self.assert_filename(filename)

        txtarea = self.worker.first(By.ID, 'pageBeanfileContent')
        return LetterContent(txtarea.text)

    def open_default_letter(self, filename):
        """Open a default letter and return its contents as a LetterContent object."""
        self.open()

        index = self.filenames.index(filename)
        self.worker.wait.until(EC.presence_of_element_located(
            (By.ID, 'SELENIUM_ID_fileList_ROW_%d_COL_cfgFilefilename' % index)))

        if self.is_customized(index):

            # Open the "ellipsis" menu
            self.worker.scroll_into_view_and_click('input_fileList_%d' % index)
            time.sleep(0.2)

            # Click "View Default" menu item
            self.worker.scroll_into_view_and_click(
                'ROW_ACTION_fileList_%d_c.ui.table.btn.view_default' % index)
            time.sleep(0.2)

        else:
            # Click the filename
            self.worker.scroll_into_view_and_click(
                '#SELENIUM_ID_fileList_ROW_%d_COL_cfgFilefilename a' % index, By.CSS_SELECTOR)
            time.sleep(0.2)

        # Assert that filename is indeed correct
        self.assert_filename(filename)

        # Read text area content
        txtarea = self.worker.first(By.ID, 'pageBeanfileContent')
        return LetterContent(txtarea.text)

    def close_letter(self):
        # If we are at specific letter, press the "go back" button.
        elems = self.worker.all(By.CSS_SELECTOR, '.pageTitle')
        if len(elems) != 0:
            title = elems[0].text.strip()
            if title == 'Configuration File':
                try:
                    backBtn = self.worker.first(By.ID, 'PAGE_BUTTONS_cbuttonback')
                    backBtn.click()
                except NoSuchElementException:
                    pass
                try:
                    backBtn = self.worker.first(By.ID, 'PAGE_BUTTONS_cbuttonnavigationcancel')
                    backBtn.click()
                except NoSuchElementException:
                    pass

    def put_contents(self, filename, content):
        """
        Save letter contents to Alma.

        This method assumes the letter has already been opened.
        """
        self.assert_filename(filename)

        # The "normal" way to set the value of a textarea with Selenium is to use
        # send_keys(), but it took > 30 seconds for some of the larger letters.
        # So here's a much faster way:
        txtarea = self.worker.first(By.ID, 'pageBeanfileContent')
        txtarea_id = txtarea.get_attribute('id')

        value = content.text.replace('"', '\\"').replace('\n', '\\n')
        script = 'document.getElementById("%s").value = "%s";' % (txtarea_id, value)
        self.worker.driver.execute_script(script)

        # Submit the form
        try:
            btn = self.worker.first(By.ID, 'PAGE_BUTTONS_cbuttonsave')
        except NoSuchElementException:
            btn = self.worker.first(By.ID, 'PAGE_BUTTONS_cbuttoncustomize')
        btn.click()

        # Wait for the table view.
        # Longer timeout per https://github.com/scriptotek/alma-slipsomat/issues/33
        self.worker.wait_for(By.CSS_SELECTOR, '.typeD table', timeout=40)

        return True


# Commands ---------------------------------------------------------------------------------

def pull_defaults(table, local_storage, status_file):
    """
    Update the local copies of the default versions of the Alma letters.

    This command downloads the latest version of all the default versions of the Alma letters.
    If you keep the folder under version control, this allows you to detect changes in the
    default letters. Unfortunately, there is no way of knowing if a default letter has changed
    without actually opening it, so we have to open each and every letter. This takes some time
    of course.

    Params:
        table: TemplateConfigurationTable object
        local_storage: LocalStorage object
        status_file: StatusFile object
    """
    count_new = 0
    count_changed = 0
    for idx, filename in enumerate(table.filenames):
        progress = '%d/%d' % ((idx + 1), len(table.filenames))
        table.print_letter_status(filename, 'checking...', progress)
        try:
            content = table.open_default_letter(filename)
        except TimeoutException:
            # Retry once
            table.print_letter_status(filename, 'retrying...', progress)
            content = table.open_default_letter(filename)
        table.close_letter()

        old_sha1 = status_file.default_checksum(filename)

        if content.sha1 == old_sha1:
            table.print_letter_status(filename, 'no changes', progress, True)
            continue

        # Write contents to default letter
        local_storage.store_default(filename, content)

        if old_sha1 is None:
            count_new += 1
            table.print_letter_status(filename, Fore.GREEN + 'fetched new letter @ {}'.format(
                content.sha1[0:7]) + Style.RESET_ALL, progress, True)
        else:
            count_changed += 1
            if old_sha1 == content.sha1:
                table.print_letter_status(
                    filename, Fore.GREEN + 'no changes' + Style.RESET_ALL, progress, True)
            else:
                table.print_letter_status(filename, Fore.GREEN + 'updated from {} to {}'.format(
                    old_sha1[0:7], content.sha1[0:7]) + Style.RESET_ALL, progress, True)

    sys.stdout.write(Fore.GREEN + 'Fetched {} new, {} changed default letters\n'.format(
        count_new, count_changed) + Style.RESET_ALL)


class TestPage(object):
    """Interface to "Notification Template" in Alma."""

    def __init__(self, worker):
        self.worker = worker

    def open(self):
        try:
            self.worker.first(By.ID, 'cbuttonupload')
        except NoSuchElementException:
            self.worker.get('/mng/action/home.do')

            # Open Alma configuration
            self.worker.wait_for_and_click(By.CSS_SELECTOR, '#ALMA_MENU_TOP_NAV_configuration')
            self.worker.click(By.XPATH, '//*[@href="#CONF_MENU6"]')  # text() = "General"
            self.worker.click(By.XPATH, '//*[text() = "Notification Template"]')

            self.worker.wait_for(By.ID, 'cbuttonupload')

    def test(self, filename, lang):

        self.open()
        wait = self.worker.waiter()

        if not os.path.isfile(filename):
            print('%sERROR: File not found: %s%s' % (Fore.RED, filename, Fore.RESET))
            return

        file_root, file_ext = os.path.splitext(filename)

        png_path = '%s_%s.png' % (file_root, lang)
        html_path = '%s_%s.html' % (file_root, lang)

        tmp = tempfile.NamedTemporaryFile('wb')
        with open(filename, 'rb') as fp:
            tmp.write(re.sub('<preferred_language>[a-z]+</preferred_language>',
                             '<preferred_language>%s</preferred_language>' % lang,
                             fp.read().decode('utf-8')).encode('utf-8'))
        tmp.flush()

        # Set language
        element = self.worker.first(By.ID, 'pageBeanuserPreferredLanguage')
        element.click()
        element = self.worker.first(By.ID, 'pageBeanuserPreferredLanguage_hiddenSelect')
        select = Select(element)
        opts = {el.get_attribute('value'): el.get_attribute('innerText') for el in select.options}
        if lang not in opts:
            print('%sERROR: Language not found: %s%s' % (Fore.RED, lang, Fore.RESET))
            return

        longLangName = opts[lang]

        element = wait.until(EC.element_to_be_clickable(
            (By.XPATH,
             '//ul[@id="pageBeanuserPreferredLanguage_hiddenSelect_list"]/li[@title="%s"]/a' % longLangName)
        ))
        element.click()

        # Upload the XML
        file_field = self.worker.first(By.ID, 'pageBeannewFormFile')
        file_field.send_keys(tmp.name)

        upload_btn = self.worker.first(By.ID, 'cbuttonupload')
        upload_btn.click()

        self.worker.wait_for(By.CSS_SELECTOR, '.infoErrorMessages')

        run_btn = wait.until(
            EC.element_to_be_clickable(
                (By.ID, 'PAGE_BUTTONS_admconfigure_notification_templaterun_xsl'))
        )

        cwh = self.worker.driver.current_window_handle

        run_btn.click()
        time.sleep(1)

        # Take a screenshot
        found_win = False
        for handle in self.worker.driver.window_handles:
            self.worker.driver.switch_to_window(handle)
            if 'beanContentParam=htmlContent' in self.worker.driver.current_url:
                self.worker.driver.set_window_size(
                    self.worker.config.get('screenshot', 'width'), 600)
                with open(html_path, 'w+b') as html_file:
                    html_file.write(self.worker.driver.page_source.encode('utf-8'))
                print('Saved output: %s' % html_path)
                if self.worker.driver.save_screenshot(png_path):
                    print('Saved screenshot: %s' % png_path)
                else:
                    print('Failed to save screenshot')
                found_win = True
                break

        if not found_win:
            print(Fore.RED + 'ERROR: Failed to produce output!' + Fore.RESET)
        self.worker.driver.switch_to_window(cwh)
        tmp.close()


def pull(table, local_storage, status_file):
    """
    Update the local files with changes made in Alma.

    This will download letters whose remote checksum does not match the value in status.json.

    Params:
        table: TemplateConfigurationTable object
        local_storage: LocalStorage object
        status_file: StatusFile object
    """
    today = datetime.now().strftime('%d/%m/%Y')
    count_new = 0
    count_changed = 0
    for idx, filename in enumerate(table.filenames):
        progress = '%3d/%3d' % ((idx + 1), len(table.filenames))

        table.print_letter_status(filename, '', progress)

        if table.modified(filename) == status_file.modified(filename) and status_file.modified(filename) != today:
            # Update date has not changed, so no need to check the actual
            # contents of the letter.
            table.print_letter_status(filename, 'no changes', progress, True)
            continue

        # Update date has changed, or is today (and we don't have time granularity),
        # so we should check if there are changes.

        table.print_letter_status(filename, 'checking...', progress)
        try:
            content = table.open_letter(filename)
        except TimeoutException:
            # Retry once
            table.print_letter_status(filename, 'retrying...', progress)
            content = table.open_letter(filename)

        table.close_letter()

        old_sha1 = status_file.checksum(filename)
        if content.sha1 == old_sha1:
            table.print_letter_status(filename, 'no changes', progress, True)
            continue

        # Store letter and update status.json
        if not local_storage.store(filename, content, table.modified(filename)):
            table.print_letter_status(
                filename, Fore.RED + 'skipped due to conflict' + Style.RESET_ALL, progress, True)
            continue

        if old_sha1 is None:
            count_new += 1
            table.print_letter_status(filename, Fore.GREEN + 'fetched new letter @ {}'.format(
                content.sha1[0:7]) + Style.RESET_ALL, progress, True)
        else:
            count_changed += 1
            table.print_letter_status(filename, Fore.GREEN + 'updated from {} to {}'.format(
                old_sha1[0:7], content.sha1[0:7]) + Style.RESET_ALL, progress, True)

    sys.stdout.write(Fore.GREEN + 'Fetched {} new, {} changed letters\n'.format(
        count_new, count_changed) + Style.RESET_ALL)


def push(table, local_storage, status_file, files=None):
    """
    Push local changes to Alma.

    This will upload files that have been modified locally to Alma.

    Params:
        table: TemplateConfigurationTable object
        local_storage: LocalStorage object
        status_file: StatusFile object
        files: list of filenames. If None, all files that have changed will be pushed.
    """
    files = files or []
    if len(files) == 0:
        # If no files were specified, we will look for files that have changes.
        for filename in table.filenames:
            if local_storage.is_modified(filename):
                files.append(filename)

        if len(files) == 0:
            sys.stdout.write(
                Fore.GREEN + 'Found no modified files.' + Style.RESET_ALL + '\n')
            return

        sys.stdout.write(
            Fore.GREEN + 'Found {} modified file(s):'.format(len(files)) + Style.RESET_ALL + '\n')
        for filename in files:
            print(' - {}'.format(filename))

        msg = 'Push the file(s) to Alma? '
        if input("%s (y/N) " % msg).lower() != 'y':
            print('Aborting')
            return

    count_pushed = 0
    for idx, filename in enumerate(files):
        progress = '%d/%d' % ((idx + 1), len(files))
        table.print_letter_status(filename, 'pushing', progress)
        old_sha1 = status_file.checksum(filename)

        local_content = local_storage.get_content(filename)
        remote_content = table.open_letter(filename)

        # Read text area content
        if remote_content.sha1 != old_sha1:
            msg = 'The remote version has changed. Overwrite remote version?'
            if not resolve_conflict(filename, local_content, remote_content, msg):
                table.print_letter_status(filename, 'skipped', progress, True)

                # Go back
                table.close_letter()

                # Skip to next letter
                continue

        table.put_contents(filename, local_content)
        count_pushed += 1
        msg = 'updated from {} to {}'.format(
            old_sha1[0:7], local_content.sha1[0:7])
        table.print_letter_status(filename, msg, progress, True)

        # Update the status file
        status_file.set_checksum(filename, local_content.sha1)
        status_file.set_modified(filename)

    sys.stdout.write(
        Fore.GREEN + 'Pushed {} file(s)\n'.format(count_pushed) + Style.RESET_ALL)


def test(testpage, files, languages):
    """
    Test the output of an XML file by running a "notification template" test in Alma.

    Params:
        worker: worker object
        files: list of XML files in test-data to use
        languages: list og languages to test
    """
    testpage.open()

    for n, filename in enumerate(files):
        for m, lang in enumerate(languages):
            cur = n * len(languages) + m + 1
            tot = len(languages) * len(files)
            print('[%d/%d] Testing "%s" using language "%s"' % (cur, tot,
                                                                os.path.basename(filename),
                                                                lang))

            testpage.test(filename, lang)
