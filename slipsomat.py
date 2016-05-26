# encoding=utf-8
from __future__ import print_function
# from __future__ import unicode_strings

from selenium.webdriver.support.ui import Select
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.remote.errorhandler import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import dateutil.parser
import time
import sys
import re
import getpass
import hashlib
import os.path
import platform
import json
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
    return txt.replace('\r\n', '\n').replace('\r', '\n')


def get_sha1(txt):
    m = hashlib.sha1()
    m.update(txt.encode('utf-8'))
    return m.hexdigest()


class Browser(object):
    """
    Selenium browser automation
    """

    def __init__(self):
        self.driver = None
        self.config = self.read_config()
        self.connect()
        atexit.register(self.close)

    def close(self):
        try:
            self.driver.close()
        except Exception as e:
            print("\nException closing driver:", e)

    def restart(self):
        self.close()
        self.connect()

    @staticmethod
    def read_config():
        if platform.system() == 'Windows':
            default_firefox_path = r'C:\Program Files (x86)\Mozilla Firefox\firefox.exe'
        elif platform.system() == 'Darwin':
            default_firefox_path = '/Applications/Firefox.app/Contents/MacOS/firefox-bin'
        else:
            default_firefox_path = 'firefox'

        config = ConfigParser.ConfigParser()
        config.read('config.cfg')

        if config.get('login', 'username') == '':
            raise RuntimeError('No username configured')

        if config.get('login', 'domain') == '':
            raise RuntimeError('No domain configured')

        if config.get('login', 'password') == '':
            config.set('login', 'password', getpass.getpass())

        if not config.has_section('selenium'):
            config.add_section('selenium')

        if not config.has_section('selenium'):
            config.add_section('selenium')

        if not config.has_option('selenium', 'browser') or config.get('selenium', 'browser') == '':
            config.set('selenium', 'browser', 'firefox')

        if not config.has_option('selenium', 'firefox_path') or config.get('selenium', 'firefox_path') == '':
            config.set('selenium', 'firefox_path', default_firefox_path)

        return config

    def get_driver(self):
        # Start a new browser and return the WebDriver

        browser_name = self.config.get('selenium', 'browser')

        if browser_name == 'firefox':
            from selenium.webdriver import Firefox

            browser_path = self.config.get('selenium', 'firefox_path')
            browser_binary = FirefoxBinary(browser_path)

            return Firefox(firefox_binary=browser_binary)

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
        username = self.config.get('login', 'username')
        password = self.config.get('login', 'password')
        driver = self.get_driver()

        print('Logging in to {} as {}... '.format(domain, username))
        driver.get('https://bibsys-k.alma.exlibrisgroup.com/mng/login?auth=SAML')

        try:
            element = driver.find_element_by_id("org")

            select = Select(element)
            select.select_by_value(domain)
            element.submit()

            element = driver.find_element_by_id('username')
            element.send_keys(username)

            element = driver.find_element_by_id('password')
            element.send_keys(password)

            element.submit()

        except NoSuchElementException:
            pass

        try:
            driver.find_element_by_link_text('Tasks')
        except NoSuchElementException:
            raise Exception('Failed to login to Alma')

        print("login DONE")
        self.driver = driver


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

    def __init__(self, driver):
        self.driver = driver
        self.status = LettersStatus(self)

        self.table_url = 'https://bibsys-k.alma.exlibrisgroup.com/infra/action/pageAction.do?xmlFileName=tables.codeTables.codeTablesList.xml?operation=LOAD&pageBean.directFilter=LETTER&pageViewMode=Edit&resetPaginationContext=true'

        self.open()
        self.rows = self.parse_rows()


class TemplateTable(object):
    """
    Abstraction for 'Customize letters' (Configuration Files / configuration_setup.configuration_mng.xml)
    """

    def __init__(self, driver):
        self.driver = driver
        self.status = LettersStatus(self)

        # self.table_url = 'https://bibsys-k.alma.exlibrisgroup.com/infra/action/pageAction.do?xmlFileName=configuration.file_table.config_file_list.xml&pageViewMode=Edit&pageBean.groupId=8&pageBean.subGroupId=13&resetPaginationContext=true'
        self.table_url = 'https://bibsys-k.alma.exlibrisgroup.com/infra/action/pageAction.do?&xmlFileName=configuration.file_table.config_file_list.xml&pageBean.scopeText=&pageViewMode=Edit&pageBean.groupId=8&pageBean.subGroupId=13&pageBean.backUrl=%2Fmng%2Faction%2Fmenus.do%3FmenuKey%3Dcom.exlibris.dps.adm.general.menu.advanced.general.generalHeader&pageBean.navigationBackUrl=%2Finfra%2Faction%2FpageAction.do%3FxmlFileName%3Dconfiguration_setup.configuration_mng.xml%26pageViewMode%3DEdit%26pageBean.menuKey%3Dcom.exlibris.dps.menu_general_conf_wizard%26operation%3DLOAD%26pageBean.helpId%3Dgeneral_configuration%26resetPaginationContext%3Dtrue%26showBackButton%3Dfalse&resetPaginationContext=true&showBackButton=true&pageBean.currentUrl=%26xmlFileName%3Dconfiguration.file_table.config_file_list.xml%26pageBean.scopeText%3D%26pageViewMode%3DEdit%26pageBean.groupId%3D8%26pageBean.subGroupId%3D13%26pageBean.backUrl%3D%252Fmng%252Faction%252Fmenus.do%253FmenuKey%253Dcom.exlibris.dps.adm.general.menu.advanced.general.generalHeader%26resetPaginationContext%3Dtrue%26showBackButton%3Dtrue'

        self.open()
        self.rows = self.parse_rows()

    def open(self):
        # Open the General Configuration menu
        # driver.get('https://bibsys-k.alma.exlibrisgroup.com/infra/action/pageAction.do?xmlFileName=configuration_setup.configuration_mng.xml&pageViewMode=Edit&pageBean.menuKey=com.exlibris.dps.menu_general_conf_wizard&operation=LOAD&pageBean.helpId=general_configuration&pageBean.currentUrl=xmlFileName%3Dconfiguration_setup.configuration_mng.xml%26pageViewMode%3DEdit%26pageBean.menuKey%3Dcom.exlibris.dps.menu_general_conf_wizard%26operation%3DLOAD%26pageBean.helpId%3Dgeneral_configuration%26resetPaginationContext%3Dtrue%26showBackButton%3Dfalse&pageBean.navigationBackUrl=..%2Faction%2Fhome.do&resetPaginationContext=true&showBackButton=false')
        # Click 'Customize Letters'
        # element = driver.find_element_by_link_text('Customize Letters')
        # element.click()

        # Open 'Customize Letters'
        self.driver.get(self.table_url)

        # Wait for the table
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, 'TABLE_DATA_fileList'))
        )

    def parse_rows(self):
        elems = self.driver.find_elements_by_css_selector('#TABLE_DATA_fileList .jsRecordContainer')
        rows = []
        sys.stdout.write('Reading table... ')
        sys.stdout.flush()
        for n, el in enumerate(elems):
            sys.stdout.write('\rReading table... {}'.format(n))
            sys.stdout.flush()

            filename = el.find_element_by_id('HREF_INPUT_SELENIUM_ID_fileList_ROW_{}_COL_cfgFilefilename'.format(n)).text.replace('../', '')
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

    def view(self):

        try:
            self.table.driver.find_element_by_id('pageBeanfileContent')
        except NoSuchElementException:
            viewLink = self.table.driver.find_elements_by_css_selector('#SELENIUM_ID_fileList_ROW_{}_COL_cfgFilefilename a'.format(self.index))[0]
            viewLink.click()

        # Locate filename and content
        element = WebDriverWait(self.table.driver, 10).until(
            EC.presence_of_element_located((By.ID, 'pageBeanconfigFilefilename'))
        )
        filename = element.get_attribute('value').replace('../', '')
        assert filename == self.filename, "%r != %r" % (filename, self.filename)

    def is_customized(self):
        try:
            actionMenu = self.table.driver.find_element_by_id('ROW_ACTION_LI_fileList_{}'.format(self.index))
            actionLink = actionMenu.find_element_by_id('input_fileList_{}'.format(self.index))
        except NoSuchElementException:
            return False
        return True

    def view_default(self):
        actionMenu = self.table.driver.find_element_by_id('ROW_ACTION_LI_fileList_{}'.format(self.index))
        actionLink = actionMenu.find_element_by_id('input_fileList_{}'.format(self.index))
        if actionMenu:
            actionMenu.click()
            viewDefaultBtn = actionMenu.find_element_by_id('ROW_ACTION_fileList_{}_c.ui.table.btn.view_default'.format(self.index))
            viewDefaultBtn.click()

        # Locate filename and content
        element = WebDriverWait(self.table.driver, 10).until(
            EC.presence_of_element_located((By.ID, 'pageBeanconfigFilefilename'))
        )

        filename = element.get_attribute('value').replace('../', '')
        assert filename == self.filename, "%r != %r" % (filename, self.filename)

    def edit(self):

        el = self.table.driver.find_elements_by_css_selector('#pageBeanfileContent')
        if len(el) != 0 and not el.is_enabled():
            self.table.open()

        el = self.table.driver.find_elements_by_css_selector('#pageBeanfileContent')
        if len(el) == 0:

            actionBtn = self.table.driver.find_elements_by_css_selector('#input_fileList_{}'.format(self.index))
            if len(actionBtn) != 0:
                actionBtn[0].click()

            editBtn = self.table.driver.find_elements_by_css_selector('#ROW_ACTION_fileList_{}_c\\.ui\\.table\\.btn\\.edit input'.format(self.index))
            if len(editBtn) != 0:
                editBtn[0].click()
            else:
                customizeBtn = self.table.driver.find_elements_by_css_selector('#ROW_ACTION_LI_fileList_{} input'.format(self.index))
                customizeBtn[0].click()

        element = WebDriverWait(self.table.driver, 10).until(
            EC.presence_of_element_located((By.ID, 'pageBeanconfigFilefilename'))
        )
        filename = element.get_attribute('value').replace('../', '')
        txtarea = self.table.driver.find_element_by_id('pageBeanfileContent')

        assert filename == self.filename, "%r != %r" % (filename, self.filename)
        assert txtarea.is_enabled()
        return txtarea

    def local_modified(self):
        content = normalize_line_endings(open(self.filename, 'rb').read().decode('utf-8'))
        current_chck = get_sha1(content)
        stored_chk = self.table.status.letters[self.filename]['checksum']

        return current_chck != stored_chk

    def remote_modified(self):
        q = self.table.driver.find_elements_by_id('TABLE_DATA_fileList')
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

        txtarea = self.table.driver.find_element_by_id('pageBeanfileContent')
        content = normalize_line_endings(txtarea.text)

        old_sha1 = self.checksum
        new_sha1 = get_sha1(content)

        return old_sha1 != new_sha1

    def pull(self):
        self.view()

        txtarea = self.table.driver.find_element_by_id('pageBeanfileContent')
        content = normalize_line_endings(txtarea.text)

        with open(self.filename, 'wb') as f:
            f.write(content.encode('utf-8'))

        self.checksum = get_sha1(content)
        self.table.open()

    def pull_default(self):
        if self.is_customized():
            self.view_default()
        else:
            self.view()

        txtarea = self.table.driver.find_element_by_id('pageBeanfileContent')
        content = normalize_line_endings(txtarea.text)

        with open('defaults/' + self.filename, 'wb') as f:
            f.write(content.encode('utf-8'))

        self.default_checksum = get_sha1(content)

        # Go back
        self.table.open()

    def set_text(self, id, value):
        """
        The "normal" way to set the value of a textarea with Selenium is to use
        send_keys(), but it took > 30 seconds for some of the larger letters.
        So here's a much faster way:
        """
        value = value.replace('"', '\\"').replace('\n', '\\n')  # Did we forget to escape something? Probably
        self.table.driver.execute_script('document.getElementById("' + id + '").value = "' + value + '";')

    def push(self):

        # Get new text
        content = open(self.filename, 'rb').read().decode('utf-8')

        # Validate XML: This will throw an xml.etree.ElementTree.ParseErro on invalid XML
        ElementTree.fromstring(content.encode('utf-8'))

        # Normalize line endings
        content = normalize_line_endings(content)

        # Open the edit form and locate the textarea
        txtarea = self.edit()

        # Verify text checksum against local checksum
        remote_chk = get_sha1(normalize_line_endings(txtarea.text))
        local_chk = self.table.status.letters[self.filename]['checksum']
        if local_chk != remote_chk:
            print('\n' + Back.RED + Fore.WHITE + 'Remote checksum does not match local. The remote file might have been modified by someone else.' + Style.RESET_ALL)
            msg = 'Continue {}? '.format(self.filename)
            if input("%s (y/N) " % msg).lower() != 'y':
                print('Skipping')
                self.table.open()
                return False

        # Send new text to text area
        self.set_text(txtarea.get_attribute('id'), content)

        # Submit the form
        try:
            btn = self.table.driver.find_element_by_id('PAGE_BUTTONS_cbuttonsave')
        except NoSuchElementException:
            btn = self.table.driver.find_element_by_id('PAGE_BUTTONS_cbuttoncustomize')
        btn.click()

        # Wait for the table view
        element = WebDriverWait(self.table.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".typeD table"))
        )

        # Update and save status.json
        modified = self.table.driver.find_element_by_id('SPAN_SELENIUM_ID_fileList_ROW_{}_COL_updateDate'.format(self.index)).text
        self.checksum = get_sha1(content)
        self.modified = modified
        self.table.status.save()
        return True


def pull(driver):
    """
    Pull in letters modified directly in Alma,
    letters whose remote checksum does not match the value in status.json
    Params:
        driver: selenium webdriver object
    """
    fetched = 0
    table = TemplateTable(driver)

    print('Checking all letters for changes...')
    for letter in table.rows:

        sys.stdout.write('- {:60}'.format(
            letter.filename.split('/')[-1] + ' (' + letter.modified + ')',
        ))
        sys.stdout.flush()

        if letter.remote_modified():
            old_chk = letter.checksum
            letter.pull()
            sys.stdout.write('updated from {} to {}'.format(old_chk[0:7], letter.checksum[0:7]))
            fetched += 1
        else:
            sys.stdout.write('no changes')

        sys.stdout.write('\n')

    sys.stdout.write(Fore.GREEN + '{} of {} files contained new modifications\n'.format(fetched, len(table.rows)) + Style.RESET_ALL)

    # status['last_pull_date'] = datetime.now()
    table.status.save()


def pull_defaults(driver):
    """
    Pull defaults from Alma
    Params:
        driver: selenium webdriver object
    """
    fetched = 0
    table = TemplateTable(driver)

    print('Checking all letters...')
    for letter in table.rows:

        sys.stdout.write('- {:60}'.format(
            letter.filename.split('/')[-1],
        ))
        sys.stdout.flush()

        old_chk = letter.default_checksum
        letter.pull_default()
        if letter.default_checksum != old_chk:
            sys.stdout.write('updated from {} to {}'.format(old_chk[0:7] if old_chk else '(none)', letter.default_checksum[0:7]))
            fetched += 1
        else:
            sys.stdout.write('no changes')

        sys.stdout.write('\n')

    sys.stdout.write(Fore.GREEN + '{} of {} files contained new modifications\n'.format(fetched, len(table.rows)) + Style.RESET_ALL)

    # status['last_pull_date'] = datetime.now()
    table.status.save()


def push(driver):
    """
    Push locally modified files (letters whose local checksum does not match
    the value in status.json) to Alma, and update status.json with new checksums.
    Params:
        driver: selenium webdriver object
    """
    table = TemplateTable(driver)

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
                sys.stdout.write('updated from {} to {}'.format(old_chk[0:7], letter.checksum[0:7]))
                sys.stdout.write('\n')


import cmd


class Shell(cmd.Cmd):
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
        super().__init__()
        self.browser = browser

    def emptyline(self):
        pass

    def can_exit(self):
        return True

    def do_exit(self, arg):
        "Exit the program"
        exit()

    def do_quit(self, arg):
        "Exit the program"
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

    def execute(self, command):
        "Executes  the command, and handle exceptions"
        try:
            command(self.browser.driver)
        except Exception as e:
            print("\nException:", e)
            input("Press enter to restart browser:")
            browser.restart()

    def precmd(self, line):
        "hook that is executed  when input is received"
        return line.lower().strip()

if __name__ == '__main__':
    browser = Browser()
#     browser = None
    Shell(browser).cmdloop()
