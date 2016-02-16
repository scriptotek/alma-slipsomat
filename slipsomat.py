#encoding=utf-8
from __future__ import print_function
# from __future__ import unicode_strings

from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.remote.errorhandler import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import dateutil.parser
import time
import sys
import getpass
import hashlib
import os.path
import json
import ConfigParser
from datetime import datetime
import colorama
from colorama import Fore, Back, Style

import argparse

colorama.init()


def get_sha1(txt):
    m = hashlib.sha1()
    m.update(txt.encode('utf-8'))
    return m.hexdigest()


def login():

    config = ConfigParser.RawConfigParser()
    config.read('config.cfg')

    domain = config.get('login', 'domain')
    username = config.get('login', 'username')
    password = config.get('login', 'password')
    firefox_path = config.get('selenium', 'firefox_path')

    if username == '':
        raise Exception('No username configured')

    if domain == '':
        raise Exception('No domain configured')

    if password == '':
        password = getpass.getpass()

    binary = FirefoxBinary(firefox_path)
    driver = webdriver.Firefox(firefox_binary=binary)

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

    return driver


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
                'modified': letter.modified
            }

        # if self.letters.get('last_pull_date') is not None:
        #     self.letters['last_pull_date'] = self.letters['last_pull_date'].isoformat()

        with open('status.json', 'w') as f:
            data = {'letters': letters}
            json.dump(data, f, sort_keys=True, indent=2)


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
                               checksum=self.status.letters[filename].get('checksum')
                        ))
            self.status.letters[filename]['remote_date'] = modified
        sys.stdout.write('\rReading table... DONE\n')

        return rows


class LetterTemplate(object):

    def __init__(self, table, index, filename, modified, checksum):
        self.table = table

        self.index = index
        self.filename = filename
        self.modified = modified
        self.checksum = checksum

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
        assert filename == self.filename, "%r != %r" % (filename, self.filename)


    def local_modified(self):
        content = open(self.filename, 'rb').read().decode('utf-8')
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
        content = txtarea.text

        old_sha1 = self.checksum
        new_sha1 = get_sha1(content)

        return old_sha1 != new_sha1

    def pull(self):
        self.view()

        txtarea = self.table.driver.find_element_by_id('pageBeanfileContent')
        content = txtarea.text

        with open(self.filename, 'wb') as f:
            f.write(content.encode('utf-8'))

        self.checksum = get_sha1(content)
        self.table.open()


    def push(self):

        # Get new text
        content = open(self.filename, 'rb').read().decode('utf-8')

        # Open the edit form and locate the textarea
        self.edit()
        txtarea = self.table.driver.find_element_by_id('pageBeanfileContent')

        # Verify text checksum against local checksum
        remote_chk = get_sha1(txtarea.text)
        local_chk = self.table.status.letters[self.filename]['checksum']
        if local_chk != remote_chk:
            print(Back.RED + Fore.WHITE + 'Remote checksum does not match local. The remote file might have been modified by someone else.' + Style.RESET_ALL)
            msg = 'Continue {}? '.format(self.filename)
            if raw_input("%s (y/N) " % msg).lower() != 'y':
                print('Aborting')
                self.table.open()
                return False

        # Send new text to text area
        txtarea.clear()
        txtarea.send_keys(content)

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


def pull():
    fetched = 0

    sys.stdout.write('Logging in... ')
    sys.stdout.flush()
    driver = login()
    sys.stdout.write('DONE\n')
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
    driver.close()



def push():
    sys.stdout.write('Logging in... ')
    sys.stdout.flush()
    driver = login()
    sys.stdout.write('DONE\n')
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
        if raw_input("%s (y/N) " % msg).lower() != 'y':
            print('Aborting')
            return False
        for letter in modified:
            sys.stdout.write('- {:60}'.format(
                letter.filename.split('/')[-1]
            ))
            sys.stdout.flush()
            old_chk = letter.checksum

            letter.push()
            sys.stdout.write('updated from {} to {}'.format(old_chk[0:7], letter.checksum[0:7]))

    driver.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Slipsomat.')
    parser.add_argument('command', metavar='push|pull', nargs=1,
                       help='The command to run')
    # parser.add_argument('filename', nargs='?',
    #                    help='Filename to push')

    args = parser.parse_args()
    cmd = args.command[0]

    if cmd == 'pull':
        pull()
    elif cmd == 'push':
        push()
