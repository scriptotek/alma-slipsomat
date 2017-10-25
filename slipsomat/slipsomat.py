# encoding=utf-8
from __future__ import print_function
# from __future__ import unicode_strings

from selenium.webdriver.support.ui import Select
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.remote.errorhandler import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

try:
    import inquirer
except ImportError:
    inquirer = None

import dateutil.parser
import time
import sys
import re
import getpass
import hashlib
import os.path
import platform
import json
import traceback
from xml.etree import ElementTree
import atexit

try:
    import ConfigParser
except Exception:
    import configparser as ConfigParser  # python 3

try:
    input = raw_input  # Python 2
except NameError:
    pass  # Python 3

from datetime import datetime
import colorama
from colorama import Fore, Back, Style

import argparse

colorama.init()


def normalize_line_endings(txt):
    # Normalize to unix line endings
    return txt.replace('\r\n', '\n').replace('\r', '\n').strip()


def get_sha1(txt):
    m = hashlib.sha1()
    m.update(txt.encode('utf-8'))
    return m.hexdigest()


class Browser(object):
    """
    Selenium browser automation
    """

    def __init__(self, cfg_file, default_timeout=10):
        """
        Construct a new Browser object
        Params:
            cfg_file: Name of config file
        """
        self.driver = None
        self.config = self.read_config(cfg_file)
        self.instance = self.config.get('login', 'instance')
        self.default_timeout = default_timeout

    def waiter(self):
        return WebDriverWait(self.driver, self.default_timeout)

    def wait_for(self, by, by_value):
        return self.wait.until(EC.visibility_of_element_located((by, by_value)))

    def send_keys(self, by, by_value, text):
        element = self.wait_for(by, by_value)
        element.send_keys(text)
        return element

    def click(self, by, by_value):
        element = self.wait.until(EC.element_to_be_clickable((by, by_value)))
        element.click()
        return element

    def close(self):
        try:
            self.driver.close()
        except Exception as e:
            print("\nException closing driver:", e)

    def restart(self):
        if "config" in vars(self):  # check for test mode
            self.close()
            self.connect()

    @staticmethod
    def read_config(cfg_file):
        config = ConfigParser.ConfigParser({'domain': ''})
        config.read(cfg_file)

        if config.get('login', 'username') == '':
            raise RuntimeError('No username configured')

        if config.get('login', 'password') == '':
            config.set('login', 'password', getpass.getpass())

        if not config.has_section('selenium'):
            config.add_section('selenium')

        if not config.has_section('selenium'):
            config.add_section('selenium')

        if not config.has_option('selenium', 'browser') or config.get('selenium', 'browser') == '':
            config.set('selenium', 'browser', 'firefox')

        return config

    def get_driver(self):
        # Start a new browser and return the WebDriver

        browser_name = self.config.get('selenium', 'browser')

        if browser_name == 'firefox':
            from selenium.webdriver import Firefox

            browser_binary = FirefoxBinary()

            driver = Firefox(firefox_binary=browser_binary)
            driver._is_remote = False  # Workaround for http://stackoverflow.com/a/42770761/489916
            return driver

        if browser_name == 'chrome':
            from selenium.webdriver import Chrome

            return Chrome()

        if browser_name == 'phantomjs':
            from selenium.webdriver import PhantomJS

            return PhantomJS()

        # @TODO: Add chrome
        raise RuntimeError('Unsupported/unknown browser')

    def connect(self):
        domain = self.config.get('login', 'domain')
        auth_type = self.config.get('login', 'auth_type')
        institution = self.config.get('login', 'institution')
        username = self.config.get('login', 'username')
        password = self.config.get('login', 'password')

        self.driver = self.get_driver()
        self.driver.set_window_size(1000, 800)
        self.wait = self.waiter()

        print('Opening instance {}:{}'.format(self.instance, institution))

        self.get('/mng/login?institute={}&auth={}'.format(institution, auth_type))

        if auth_type == 'SAML' and domain != '':
            print('Logging in as {}@{}'.format(username, domain))

            element = self.wait.until(EC.visibility_of_element_located((By.ID, 'org')))
            select = Select(element)
            select.select_by_value(domain)

            element = self.driver.find_element_by_id('submit')
            element.click()
            # We cannot use submit() because of
            # http://stackoverflow.com/questions/833032/submit-is-not-a-function-error-in-javascript
        else:
            print('Logging in as {}'.format(username))

        self.send_keys(By.ID, 'username', username)
        element = self.send_keys(By.ID, 'password', password)
        element.send_keys(Keys.RETURN)

        try:
            # Look for some known element on the Alma main screen
            self.wait_for(By.CSS_SELECTOR, '.logoAlma')
        except NoSuchElementException:
            raise Exception('Failed to login to Alma')

        print("login DONE")

    def get(self, url):
        return self.driver.get('https://{}.alma.exlibrisgroup.com/{}'.format(self.instance, url.lstrip('/')))


class LettersStatus(object):

    def __init__(self, table):
        self.table = table
        self.load()

    def load(self):
        self.letters = {}
        if os.path.exists('status.json'):
            with open('status.json') as f:
                data = json.load(f)
                self.letters = data['letters']

        # if self.data.get('last_pull_date') is not None:
        #     self.data['last_pull_date'] = dateutil.parser.parse(self.data['last_pull_date'])

    def save(self):

        letters = {}
        for letter in self.table.rows:
            letters[letter.filename] = {
                'checksum': letter.checksum,
                'default_checksum': letter.default_checksum,
                'modified': letter.modified,
            }

        # if self.letters.get('last_pull_date') is not None:
        #     self.letters['last_pull_date'] = self.letters['last_pull_date'].isoformat()

        with open('status.json', 'wb') as f:
            data = {'letters': letters}
            jsondump = json.dumps(data, sort_keys=True, indent=2)

            # Remove trailling spaces (https://bugs.python.org/issue16333)
            jsondump = re.sub('\s+$', '', jsondump, flags=re.MULTILINE)

            # Normalize to unix line endings
            jsondump = normalize_line_endings(jsondump)

            f.write(jsondump.encode('utf-8'))


class CodeTable(object):
    """
    Abstraction for 'Letter emails' (Code tables / tables.codeTables.codeTablesList.xml)
    """

    def __init__(self, browser):
        self.browser = browser
        self.status = LettersStatus(self)

        self.table_url = '/infra/action/pageAction.do?xmlFileName=tables.codeTables.codeTablesList.xml?operation=LOAD&pageBean.directFilter=LETTER&pageViewMode=Edit&resetPaginationContext=true'

        self.open()
        self.rows = self.parse_rows()


class TemplateTable(object):
    """
    Abstraction for 'Customize letters' (Configuration Files / configuration_setup.configuration_mng.xml)
    """

    def __init__(self, browser):
        self.browser = browser
        self.status = LettersStatus(self)
        self.open()
        self.rows = self.parse_rows()

    def open(self):

        # If we are at specific letter, press the "go back" button.
        elems = self.browser.driver.find_elements_by_css_selector('.pageTitle')
        if len(elems) != 0:
            title = elems[0].text.strip()
            if title == 'Configuration File':
                try:
                    backBtn = self.browser.driver.find_element_by_id('PAGE_BUTTONS_cbuttonback')
                    backBtn.click()
                except NoSuchElementException:
                    pass

        elems = self.browser.driver.find_elements_by_xpath('//button[@aria-label="Open Alma configuration"]')
        if len(elems) != 0:
            # Open Alma configuration
            self.browser.click(By.XPATH, '//button[@aria-label="Open Alma configuration"]')
            self.browser.click(By.XPATH, '//a[@href="#CONF_MENU5"]')
            self.browser.click(By.XPATH, '//*[text() = "Customize Letters"]')

        self.browser.wait_for(By.CSS_SELECTOR, '#TABLE_DATA_fileList')

    def parse_rows(self):
        self.browser.wait_for(By.CSS_SELECTOR, '#TABLE_DATA_fileList')

        elems = self.browser.driver.find_elements_by_css_selector('#TABLE_DATA_fileList .jsRecordContainer')
        rows = []
        sys.stdout.write('Reading table... ')
        sys.stdout.flush()
        for n, el in enumerate(elems):
            sys.stdout.write('\rReading table... {}'.format(n))
            sys.stdout.flush()


            filename = el.find_element_by_id('SELENIUM_ID_fileList_ROW_{}_COL_cfgFilefilename'.format(n)).text.replace('../', '')
            modified = el.find_element_by_id('SPAN_SELENIUM_ID_fileList_ROW_{}_COL_updateDate'.format(n)).text
            if filename not in self.status.letters:
                self.status.letters[filename] = {}
            rows.append(LetterTemplate(table=self,
                                       index=n,
                                       filename=filename,
                                       modified=modified,
                                       checksum=self.status.letters[filename].get('checksum'),
                                       default_checksum=self.status.letters[filename].get('default_checksum')
                                       ))
            self.status.letters[filename]['remote_date'] = modified
        sys.stdout.write('\rReading table... DONE\n')

        return rows


class LetterTemplate(object):

    def __init__(self, table, index, filename, modified, checksum, default_checksum):
        self.table = table

        self.index = index
        self.filename = filename
        self.modified = modified
        self.checksum = checksum
        self.default_checksum = default_checksum
        self.wait = self.table.browser.waiter()

    def scroll_into_view_and_click(self, value, by=By.ID):
        element = self.table.browser.driver.find_element(by, value)
        self.table.browser.driver.execute_script('arguments[0].scrollIntoView();', element);
        # Need to scroll a little bit more because of the fixed header
        self.table.browser.driver.execute_script('window.scroll(window.scrollX, window.scrollY-200)')
        element = self.wait.until(EC.element_to_be_clickable((by, value)))
        element.click()

    def view(self):

        try:
            # Check if we are already on the view page
            self.table.browser.driver.find_element_by_id('pageBeanfileContent')
        except NoSuchElementException:
            # Otherwise, click the link
            self.scroll_into_view_and_click('#SELENIUM_ID_fileList_ROW_{}_COL_cfgFilefilename a'.format(self.index), By.CSS_SELECTOR)

        # Locate filename and content
        element = self.table.browser.wait_for(By.ID, 'pageBeanconfigFilefilename')
        filename = element.text.replace('../', '')
        assert filename == self.filename, "%r != %r" % (filename, self.filename)

    def is_customized(self):
        updatedBy = self.table.browser.driver.find_element_by_id('SPAN_SELENIUM_ID_fileList_ROW_{}_COL_cfgFileupdatedBy'.format(self.index))
        return updatedBy.text != '-'

    def view_default(self):

        # Open "Actions" menu
        self.scroll_into_view_and_click('input_fileList_{}'.format(self.index))

        # Click "View Default" menu item
        self.scroll_into_view_and_click('ROW_ACTION_fileList_{}_c.ui.table.btn.view_default'.format(self.index))

        # Wait for new page to load
        element = self.wait.until(EC.presence_of_element_located((By.ID, 'pageBeanconfigFilefilename')))

        # Assert that filename is correct
        filename = element.text.replace('../', '')
        assert filename == self.filename, "%r != %r" % (filename, self.filename)

    def edit(self):

        el = self.table.browser.driver.find_elements_by_css_selector('#pageBeanfileContent')
        if len(el) != 0 and not el.is_enabled():
            self.table.open()

        el = self.table.browser.driver.find_elements_by_css_selector('#pageBeanfileContent')
        if len(el) == 0:

            # To avoid
            #   Exception: Message: unknown error: Element is not clickable at point (738, 544).
            #   Other element would receive the click: <span class="buttonAction roundLeft roundRight">...</span>
            self.scroll_into_view_and_click('#input_fileList_{}'.format(self.index), By.CSS_SELECTOR)

            editBtnSelector = '#ROW_ACTION_fileList_{}_c\\.ui\\.table\\.btn\\.edit a'.format(self.index)
            editBtn = self.table.browser.driver.find_elements_by_css_selector(editBtnSelector)
            if len(editBtn) != 0:
                self.scroll_into_view_and_click(editBtnSelector, By.CSS_SELECTOR)
            else:
                customizeBtnSelector = '#ROW_ACTION_LI_fileList_{} a'.format(self.index)
                self.scroll_into_view_and_click(customizeBtnSelector, By.CSS_SELECTOR)

        element = self.wait.until(EC.presence_of_element_located((By.ID, 'pageBeanconfigFilefilename')))
        filename = element.text.replace('../', '')
        txtarea = self.table.browser.driver.find_element_by_id('pageBeanfileContent')

        assert filename == self.filename, "%r != %r" % (filename, self.filename)
        assert txtarea.is_enabled()
        return txtarea

    def local_modified(self):
        content = normalize_line_endings(open(self.filename, 'rb').read().decode('utf-8'))
        current_chck = get_sha1(content)
        stored_chk = self.table.status.letters[self.filename]['checksum']

        return current_chck != stored_chk

    def remote_modified(self):
        q = self.table.browser.driver.find_elements_by_id('TABLE_DATA_fileList')
        if len(q) == 0:
            self.table.open()

        today = datetime.now().strftime('%d/%m/%Y')
        cached_modified = self.table.status.letters[self.filename].get('modified')

        # If modification date has not changed from the cached modification date,
        # no modifications have occured. If the modification date is today, we cannot
        # be sure, since there is no time information, just date.
        if os.path.exists(self.filename) and self.modified == cached_modified and self.modified != today:
            return False

        sys.stdout.write('checking... ')

        self.view()

        txtarea = self.table.browser.driver.find_element_by_id('pageBeanfileContent')
        content = normalize_line_endings(txtarea.text)

        old_sha1 = self.checksum
        new_sha1 = get_sha1(content)

        return old_sha1 != new_sha1

    def _can_continue(self, txt, msg):
        # Compare text checksum with value in status.json

        if not 'checksum' in self.table.status.letters[self.filename]:
            return True  # it's a new letter

        local_chk = self.table.status.letters[self.filename]['checksum']
        txt = normalize_line_endings(txt)
        remote_chks = [
            get_sha1(txt),
            get_sha1(txt + "\n"),
        ]

        if local_chk in remote_chks:
            return True

        print('\n' + Back.RED + Fore.WHITE + msg + Style.RESET_ALL)
        # @TODO: Show diff here?
        msg = 'Continue {}? '.format(self.filename)
        return input("%s (y/N) " % msg).lower()[:1] == 'y'

    def pull(self):
        self.view()

        if not os.path.exists(os.path.dirname(self.filename)):
            os.makedirs(os.path.dirname(self.filename))

        # Verify text checksum against local checksum
        if os.path.isfile(self.filename):
            with open(self.filename, 'rb') as f:
                local_content = f.read().decode('utf-8')

            if not self._can_continue(local_content, 'Conflict: Trying to pull in a file modified remotely in Alma, but the local file also seems to have changes (checksum does not match the value in status.json). If you continue, the local changes will be overwritten. You might want to make a backup of the file first.'):
                print('Skipping')
                self.table.open()
                return False

        txtarea = self.table.browser.driver.find_element_by_id('pageBeanfileContent')
        remote_content = normalize_line_endings(txtarea.text)

        with open(self.filename, 'wb') as f:
            f.write(remote_content.encode('utf-8'))

        self.checksum = get_sha1(remote_content)
        self.table.open()

    def pull_default(self):
        is_customized = self.is_customized()

        if is_customized:
            self.view_default()
        else:
            self.view()

        txtarea = self.table.browser.driver.find_element_by_id('pageBeanfileContent')
        content = normalize_line_endings(txtarea.text)

        # Write contents to default letter
        filename = 'defaults/' + self.filename
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        with open(filename, 'wb') as f:
            f.write(content.encode('utf-8'))
        self.default_checksum = get_sha1(content)

        if not is_customized:
            # Write contents to standard letter as well
            filename = self.filename
            if not os.path.exists(os.path.dirname(filename)):
                os.makedirs(os.path.dirname(filename))
            with open(filename, 'wb') as f:
                f.write(content.encode('utf-8'))
            self.checksum = get_sha1(content)

        # Go back
        self.table.open()

    def set_text(self, id, value):
        """
        The "normal" way to set the value of a textarea with Selenium is to use
        send_keys(), but it took > 30 seconds for some of the larger letters.
        So here's a much faster way:
        """
        value = value.replace('"', '\\"').replace('\n', '\\n')  # Did we forget to escape something? Probably
        self.table.browser.driver.execute_script('document.getElementById("' + id + '").value = "' + value + '";')

    def push(self):

        # Get new text
        local_content = open(self.filename, 'rb').read().decode('utf-8')

        # Validate XML: This will throw an xml.etree.ElementTree.ParseError on invalid XML
        try:
            ElementTree.fromstring(local_content.encode('utf-8'))
        except ElementTree.ParseError as e:
            print('\n' + Back.RED + Fore.WHITE + 'XML file contains error and will be skipped: ' + self.filename + Style.RESET_ALL)
            print(Back.RED + Fore.WHITE + ' > ' + str(e) + Style.RESET_ALL)
            return False


        # Normalize line endings
        local_content = normalize_line_endings(local_content)

        # Open the edit form and locate the textarea
        txtarea = self.edit()

        # Verify text checksum against local checksum
        if not self._can_continue(txtarea.text, 'The checksum of the remote file does not match the value in status.json. It might have been modified directly in Alma.'):
            print('Skipping')
            self.table.open()
            return False

        # Send new text to text area
        self.set_text(txtarea.get_attribute('id'), local_content)

        # Submit the form
        try:
            btn = self.table.browser.driver.find_element_by_id('PAGE_BUTTONS_cbuttonsave')
        except NoSuchElementException:
            btn = self.table.browser.driver.find_element_by_id('PAGE_BUTTONS_cbuttoncustomize')
        btn.click()

        # Wait for the table view
        element = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".typeD table"))
        )

        # Update and save status.json
        modified = self.table.browser.driver.find_element_by_id('SPAN_SELENIUM_ID_fileList_ROW_{}_COL_updateDate'.format(self.index)).text
        self.checksum = get_sha1(local_content)
        self.modified = modified
        self.table.status.save()
        return True


def pull(browser):
    """
    Pull in letters modified directly in Alma,
    letters whose remote checksum does not match the value in status.json
    Params:
        browser: Browser object
    """
    fetched = 0
    table = TemplateTable(browser)

    print('Checking all letters for changes...')
    for letter in table.rows:

        sys.stdout.write('- {:60}'.format(
            letter.filename.split('/')[-1] + ' (' + letter.modified + ')',
        ))
        sys.stdout.flush()

        if letter.remote_modified():
            old_chk = letter.checksum
            letter.pull()
            if old_chk is None:
                sys.stdout.write('fetched new letter @ {}'.format(letter.checksum[0:7]))
            else:
                sys.stdout.write('updated from {} to {}'.format(old_chk[0:7], letter.checksum[0:7]))
            fetched += 1
        else:
            sys.stdout.write('no changes')

        sys.stdout.write('\n')

    sys.stdout.write(Fore.GREEN + '{} of {} files contained new modifications\n'.format(fetched, len(table.rows)) + Style.RESET_ALL)

    # status['last_pull_date'] = datetime.now()
    table.status.save()


def pull_defaults(browser):
    """
    Pull defaults from Alma
    Params:
        browser: Browser object
    """
    fetched = 0
    table = TemplateTable(browser)

    print('Checking all letters...')
    for letter in table.rows:

        sys.stdout.write('- {:60}'.format(
            letter.filename.split('/')[-1],
        ))
        sys.stdout.flush()

        old_chk = letter.default_checksum
        letter.pull_default()
        if letter.default_checksum != old_chk:
            if old_chk is None:
                sys.stdout.write('fetched new letter @ {}'.format(letter.default_checksum[0:7]))
            else:
                sys.stdout.write('updated from {} to {}'.format(old_chk[0:7], letter.default_checksum[0:7]))
            fetched += 1
        else:
            sys.stdout.write('no changes')

        sys.stdout.write('\n')

    sys.stdout.write(Fore.GREEN + '{} of {} files contained new modifications\n'.format(fetched, len(table.rows)) + Style.RESET_ALL)

    # status['last_pull_date'] = datetime.now()
    table.status.save()


def push(browser):
    """
    Push locally modified files (letters whose local checksum does not match
    the value in status.json) to Alma, and update status.json with new checksums.
    Params:
        browser: Browser object
    """
    table = TemplateTable(browser)

    modified = []
    for letter in table.rows:
        if letter.local_modified():
            modified.append(letter)

    if len(modified) == 0:
        sys.stdout.write(Fore.GREEN + 'No files contained local modifications.' + Style.RESET_ALL + '\n')
    else:
        sys.stdout.write(Fore.GREEN + 'The following {} file(s) contains local modifications.'.format(len(modified)) + Style.RESET_ALL + '\n')
        for letter in modified:
            print(' - {}'.format(letter.filename))

        msg = 'Push updates to Alma? '
        if input("%s (y/N) " % msg).lower() != 'y':
            print('Aborting')
            return False
        for letter in modified:
            sys.stdout.write('- {:60}'.format(
                letter.filename.split('/')[-1]
            ))
            sys.stdout.flush()
            old_chk = letter.checksum

            if letter.push():
                if old_chk is None:
                    sys.stdout.write('fetched new letter @ {}'.format(letter.checksum[0:7]))
                else:
                    sys.stdout.write('updated from {} to {}'.format(old_chk[0:7], letter.checksum[0:7]))
                sys.stdout.write('\n')


def test_XML(browser, filename):
    """
    Run a "notification template" test in Alma. An XML file is uploaded and processed
    Params:
        browser: Browser object
        filename: string with the name of the XML file in test-data to use
    """
    wait = browser.waiter()

    print("Testing XML file:", filename)
    path = os.path.abspath(os.path.join("test-data", filename))
    if not os.path.isfile(path):
        print("File not found:", path)
        return

    print("full path:", path)
    browser.get(
        "/infra/action/pageAction.do?&xmlFileName=configuration.configure_notification_template.xml&pageViewMode=Edit&RenewBean=true&pageBean.backUrl=%2Fmng%2Faction%2Fmenus.do%3FmenuKey%3Dcom.exlibris.dps.adm.general.menu.advanced.general.generalHeader&pageBean.navigationBackUrl=%2Finfra%2Faction%2FpageAction.do%3FxmlFileName%3Dconfiguration_setup.configuration_mng.xml%26pageViewMode%3DEdit%26pageBean.menuKey%3Dcom.exlibris.dps.menu_general_conf_wizard%26operation%3DLOAD%26pageBean.helpId%3Dgeneral_configuration%26resetPaginationContext%3Dtrue%26showBackButton%3Dtrue&resetPaginationContext=true&showBackButton=true&pageBean.currentUrl=%26xmlFileName%3Dconfiguration.configure_notification_template.xml%26pageViewMode%3DEdit%26RenewBean%3Dtrue%26pageBean.backUrl%3D%252Fmng%252Faction%252Fmenus.do%253FmenuKey%253Dcom.exlibris.dps.adm.general.menu.advanced.general.generalHeader%26resetPaginationContext%3Dtrue%26showBackButton%3Dtrue")

    # Upload the XML
    file_field = browser.driver.find_element_by_id('pageBeannewFormFile')
    file_field.send_keys(path)
    upload_btn = browser.driver.find_element_by_id('cbuttonupload')
    upload_btn.click()

    # First wait for the upload button to be removed from DOM, indicating the
    # current page is unloaded
    wait.until(
        EC.staleness_of(upload_btn)
    )

    # Then wait for the run button to re-appear.
    # Note that we use the bottom run button, not the upper one, since the
    # upper one can be covered by stuff overflowing from the navbar if the
    # window is to narrow
    run_btn = wait.until(
        EC.element_to_be_clickable((By.ID, 'PAGE_BUTTONS_admconfigure_notification_templaterun_xsl'))
    )

    # Clicking the button right away caused the screen to hang on the spinner,
    # so we add a small sleep.
    time.sleep(1)

    run_btn.click()


import cmd


class Shell(cmd.Cmd, object):
    """
    Interactive shell for parsing commands
    """
    intro = 'Welcome to the slipsomat. Type help or ? to list commands.\n'
    prompt = "slipsomat> "
    file = None

    def __init__(self, browser):
        """
        Construct a new Shell object
        Params:
            browser: Browser object for command dispatch
        """
        super(Shell, self).__init__()
        self.browser = browser

    def emptyline(self):
        "handle empty lines"
        pass

    def do_exit(self, arg):
        "Exit the program"
        print("\nbye")
        exit()

    def do_pull(self, arg):
        "Pull in letters modified directly in Alma"
        self.execute(pull)

    def do_defaults(self, arg):
        "Pull in updates to default letters"
        self.execute(pull_defaults)

    def do_push(self, arg):
        "Push locally modified files"
        self.execute(push)

    def do_test(self, arg):
        "test filename : Run Alma 'notification template' test, using given XML file"
        self.execute(test_XML, arg)

    def complete_test(self, word, line, begin_idx, end_idx):
        "Complete test arguments"
        files = os.listdir("test-data")
        return [file for file in files if file.startswith(word)]

    # Aliases
    do_EOF = do_exit  # ctrl-d
    do_eof = do_EOF
    do_quit = do_exit

    def handle_exception(self, e):
        print("\nException:", e)
        traceback.print_exc(file=sys.stdout)

        if inquirer is None:
            print('Please "pip install inquirer" if you would like more debug options')
            sys.exit(0)
        else:
            q = inquirer.List('goto',
                              message='Now what?',
                              choices=['Restart browser', 'Debug with ipdb', 'Debug with pdb', 'Exit'],
                              )
            answers = inquirer.prompt([q])

            if answers['goto'] == 'Debug with ipdb':
                try:
                    import ipdb
                except ImportError:
                    print('Please run "pip install ipdb" to install ipdb')
                    sys.exit(1)
                ipdb.post_mortem()
                sys.exit(0)
            elif answers['goto'] == 'Debug with pdb':
                import pdb
                pdb.post_mortem()
                sys.exit(0)
            elif answers['goto'] == 'Restart browser':
                self.browser.restart()
            else:
                sys.exit(0)

    def execute(self, function, *args):
        "Executes the function, and handle exceptions"
        try:
            function(self.browser, *args)
        except Exception as e:
            self.handle_exception(e)

    def precmd(self, line):
        "hook that is executed  when input is received"
        return line.strip()


def main():
    parser = argparse.ArgumentParser()
#     parser.add_argument("-v", "--verbose", help="verbose output", action="store_true")
    parser.add_argument("-t", "--test", help="shell test, no browser", action="store_true")
    options = parser.parse_args()
    if not os.path.exists('slipsomat.cfg'):
        print('No slipsomat.cfg file found in this directory. Exiting.')
        return

    browser = Browser('slipsomat.cfg')

    if not options.test:  # test mode without driver
        browser.connect()
        atexit.register(browser.close)

    Shell(browser).cmdloop()
