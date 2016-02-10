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


def load_status():
    status = {
        'letters': {}
    }
    if os.path.exists('status.json'):
        with open('status.json') as f:
            status = json.load(f)

    # if status.get('last_pull_date') is not None:
    #     status['last_pull_date'] = dateutil.parser.parse(status['last_pull_date'])

    return status


def write_status(status):

    # if status.get('last_pull_date') is not None:
    #     status['last_pull_date'] = status['last_pull_date'].isoformat()

    with open('status.json', 'w') as f:
        json.dump(status, f, sort_keys=True, indent=2)


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


def open_letters_table(driver):

    # Open the General Configuration menu
    # driver.get('https://bibsys-k.alma.exlibrisgroup.com/infra/action/pageAction.do?xmlFileName=configuration_setup.configuration_mng.xml&pageViewMode=Edit&pageBean.menuKey=com.exlibris.dps.menu_general_conf_wizard&operation=LOAD&pageBean.helpId=general_configuration&pageBean.currentUrl=xmlFileName%3Dconfiguration_setup.configuration_mng.xml%26pageViewMode%3DEdit%26pageBean.menuKey%3Dcom.exlibris.dps.menu_general_conf_wizard%26operation%3DLOAD%26pageBean.helpId%3Dgeneral_configuration%26resetPaginationContext%3Dtrue%26showBackButton%3Dfalse&pageBean.navigationBackUrl=..%2Faction%2Fhome.do&resetPaginationContext=true&showBackButton=false')
    # Click 'Customize Letters'
    # element = driver.find_element_by_link_text('Customize Letters')
    # element.click()

    # Open 'Customize Letters'
    driver.get('https://bibsys-k.alma.exlibrisgroup.com/infra/action/pageAction.do?&xmlFileName=configuration.file_table.config_file_list.xml&pageBean.scopeText=&pageViewMode=Edit&pageBean.groupId=8&pageBean.subGroupId=13&pageBean.backUrl=%2Fmng%2Faction%2Fmenus.do%3FmenuKey%3Dcom.exlibris.dps.adm.general.menu.advanced.general.generalHeader&pageBean.navigationBackUrl=%2Finfra%2Faction%2FpageAction.do%3FxmlFileName%3Dconfiguration_setup.configuration_mng.xml%26pageViewMode%3DEdit%26pageBean.menuKey%3Dcom.exlibris.dps.menu_general_conf_wizard%26operation%3DLOAD%26pageBean.helpId%3Dgeneral_configuration%26resetPaginationContext%3Dtrue%26showBackButton%3Dtrue&resetPaginationContext=true&showBackButton=true&pageBean.currentUrl=%26xmlFileName%3Dconfiguration.file_table.config_file_list.xml%26pageBean.scopeText%3D%26pageViewMode%3DEdit%26pageBean.groupId%3D8%26pageBean.subGroupId%3D13%26pageBean.backUrl%3D%252Fmng%252Faction%252Fmenus.do%253FmenuKey%253Dcom.exlibris.dps.adm.general.menu.advanced.general.generalHeader%26resetPaginationContext%3Dtrue%26showBackButton%3Dfalse')

    # Wait for the table
    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".typeD table"))
    )

    # Loop over all rows
    elements = element.find_elements_by_css_selector('.jsRecordContainer')
    letters = []
    for n, el in enumerate(elements):
        filename = element.find_element_by_id('HREF_INPUT_SELENIUM_ID_fileList_ROW_{}_COL_cfgFilefilename'.format(n)).text.replace('../', '')
        updateDate = element.find_element_by_id('SPAN_SELENIUM_ID_fileList_ROW_{}_COL_updateDate'.format(n)).text
        row = {
            'filename': filename,
            'modified': updateDate
        }
        letters.append(row)

    return letters


def get_file_from_table(driver, n, row, status):
    today = datetime.now().strftime('%d/%m/%Y')

    if row['filename'] not in status['letters']:
        status['letters'][row['filename']] = {}

    remote_date = status['letters'][row['filename']].get('remote_date')

    if os.path.exists(row['filename']) and row['modified'] == remote_date and row['modified'] != today:
        sys.stdout.write('no changes')
        return False

    # driver.get('https://bibsys-k.alma.exlibrisgroup.com/infra/action/pageAction.do?&xmlFileName=configuration.file_table.config_file_list.xml&pageBean.scopeText=&pageViewMode=Edit&pageBean.groupId=8&pageBean.subGroupId=13&pageBean.backUrl=%2Fmng%2Faction%2Fmenus.do%3FmenuKey%3Dcom.exlibris.dps.adm.general.menu.advanced.general.generalHeader&pageBean.navigationBackUrl=%2Finfra%2Faction%2FpageAction.do%3FxmlFileName%3Dconfiguration_setup.configuration_mng.xml%26pageViewMode%3DEdit%26pageBean.menuKey%3Dcom.exlibris.dps.menu_general_conf_wizard%26operation%3DLOAD%26pageBean.helpId%3Dgeneral_configuration%26resetPaginationContext%3Dtrue%26showBackButton%3Dtrue&resetPaginationContext=true&showBackButton=true&pageBean.currentUrl=%26xmlFileName%3Dconfiguration.file_table.config_file_list.xml%26pageBean.scopeText%3D%26pageViewMode%3DEdit%26pageBean.groupId%3D8%26pageBean.subGroupId%3D13%26pageBean.backUrl%3D%252Fmng%252Faction%252Fmenus.do%253FmenuKey%253Dcom.exlibris.dps.adm.general.menu.advanced.general.generalHeader%26resetPaginationContext%3Dtrue%26showBackButton%3Dtrue')

    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".typeD table"))
    )

    # Click Customize
    links = [x for x in element.find_elements_by_css_selector('td a') if x.text.find('.xsl') != -1]
    try:
        links[n].click()
    except IndexError:
        return False  # We've reached the end of the list

    # Locate filename and content
    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'pageBeanconfigFilefilename'))
    )
    filename = element.get_attribute('value').replace('../', '')
    element = driver.find_element_by_id('pageBeanfileContent')
    content = element.text

    element = driver.find_element_by_id('PAGE_BUTTONS_cbuttonback')
    element.click()

    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".typeD table"))
    )

    old_sha1 = status['letters'][row['filename']].get('checksum')
    new_sha1 = get_sha1(content)

    status['letters'][row['filename']]['checksum'] = new_sha1

    if old_sha1 == new_sha1:
        sys.stdout.write('no changes')
        return False
    else:
        with open(filename, 'wb') as f:
            f.write(content.encode('utf-8'))
        sys.stdout.write('updated from {} to {}'.format(old_sha1[:8], new_sha1[:8]))
        return True



def push_file_from_table(driver, n, filename, status):

    content = open(filename, 'rb').read().decode('utf-8')

    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".typeD table"))
    )

    # Click Customize
    btn = element.find_elements_by_css_selector('#ROW_ACTION_fileList_{}_span input'.format(n))[0]
    btn.click()

    # Wait
    txtarea = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'pageBeanfileContent'))
    )

    form_filename = driver.find_element_by_id('pageBeanconfigFilefilename').text.replace('../', '')

    # Verify filename
    if filename != form_filename:
        raise Exception('Filename did not match. {} != {}'.format(filename, form_filename))

    # Verify checksum
    remote_chk = get_sha1(txtarea.text)
    local_chk = status['letters'][filename]['checksum']

    if local_chk != remote_chk:
        print(Back.RED + Fore.WHITE + 'Remote checksum does not match local. The remote file might have been modified by someone else.' + Style.RESET_ALL)
        msg = 'Continue {}? '.format(row['filename'])
        if raw_input("%s (y/N) " % msg).lower() != 'y':
            print('Aborting')
            return False

    # Update
    txtarea.clear()
    txtarea.send_keys(content)

    btn = driver.find_element_by_id('PAGE_BUTTONS_cbuttoncustomize')
    # btn.click()

    status['letters'][filename]['checksum'] = get_sha1(content)

    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".typeD table"))
    )

    # @TODO: Update status['letters'][filename]['remote_date']

    return True


def pull():
    fetched = 0

    status = load_status()
    print('Preparing Alma')
    driver = login()
    rows = open_letters_table(driver)

    print('Checking all letters for changes...')
    for n, row in enumerate(rows):

        sys.stdout.write('- {:60}'.format(
            row['filename'].split('/')[-1] + ' (' + row['modified'] + ')',
        ))
        sys.stdout.flush()

        if get_file_from_table(driver, n, row, status):
            fetched += 1

        sys.stdout.write('\n')
        if row['filename'] not in status['letters']:
            status['letters'][row['filename']] = {}
        status['letters'][row['filename']]['remote_date'] = row['modified']

    sys.stdout.write(Fore.GREEN + '{} of {} files contained new modifications\n'.format(fetched, len(rows)) + Style.RESET_ALL)

    # status['last_pull_date'] = datetime.now()
    write_status(status)
    driver.close()


def push(filename):
    # Upload files modified since last pull/push
    status = load_status()

    if not os.path.exists(filename):
        print(Back.RED + Fore.WHITE + 'File does not exist locally' + Style.RESET_ALL)
        sys.exit(0)

    driver = login()
    rows = open_letters_table(driver)

    m = -1

    for n, row in enumerate(rows):
        if row['filename'] == filename:
            m = n
            break

    if m == -1:
        print(Back.RED + Fore.WHITE + 'File does not exist in Alma' + Style.RESET_ALL)
        sys.exit(0)

    push_file_from_table(m, filename, status)

    write_status(status)
    driver.close()

parser = argparse.ArgumentParser(description='Slipsomat.')
parser.add_argument('command', metavar='push|pull', nargs=1,
                   help='The command to run')
parser.add_argument('filename', nargs='?',
                   help='Filename to push')

args = parser.parse_args()
cmd = args.command[0]

if cmd == 'pull':
    pull()
elif cmd == 'push':
    push(args.filename)