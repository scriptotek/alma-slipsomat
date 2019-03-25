# encoding=utf8
from __future__ import print_function
from textwrap import dedent
from io import StringIO
import getpass
import sys
from selenium.webdriver.support.ui import Select
from selenium.webdriver.remote.errorhandler import NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys


try:
    from configparser import ConfigParser  # Python 3
except Exception:
    from ConfigParser import ConfigParser  # Python 2


class Worker(object):
    """This class is mostly about providing helper methods to work efficiently with Selenium."""

    def __init__(self, cfg_file):
        """
        Construct a new Worker object.

        Params:
            cfg_file: Name of config file
        """
        self.driver = None
        self.config = self.read_config(cfg_file)
        self.default_timeout = int(self.config.get('selenium', 'default_timeout'))
        self.instance = self.config.get('login', 'instance')

    def waiter(self, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        return WebDriverWait(self.driver, timeout)

    def first(self, by, by_value):
        return self.driver.find_element(by, by_value)

    def all(self, by, by_value):
        return self.driver.find_elements(by, by_value)

    def wait_for(self, by, by_value, timeout=None):
        wait = self.wait if timeout is None else self.waiter(timeout)
        return wait.until(EC.visibility_of_element_located((by, by_value)))

    def wait_for_and_click(self, by, by_value, timeout=None):
        elem = self.wait_for(by, by_value, timeout)
        elem.click()

    def send_keys(self, by, by_value, text):
        element = self.wait_for(by, by_value)
        element.send_keys(text)
        return element

    def click(self, by, by_value):
        element = self.wait.until(EC.element_to_be_clickable((by, by_value)))
        element.click()
        return element

    def scroll_into_view_and_click(self, value, by=By.ID):
        element = self.driver.find_element(by, value)
        self.driver.execute_script('arguments[0].scrollIntoView();', element)
        # Need to scroll a little bit more because of the fixed header
        self.driver.execute_script('window.scroll(window.scrollX, window.scrollY-400)')
        element = self.wait.until(EC.element_to_be_clickable((by, value)))
        try:
            element.click()
        except WebDriverException:
            element.send_keys(Keys.RETURN)  # works in some edge cases

    def close(self):
        try:
            self.driver.close()
        except Exception as e:
            print("\nException closing driver:", e)

    def restart(self):
        if "config" in vars(self):  # check for test mode
            self.close()
            self._template_table = None
            self.connect()

    @staticmethod
    def read_config(cfg_file):
        config = ConfigParser()
        defaults = StringIO(dedent(
            u"""[login]
            domain=

            [selenium]
            browser=firefox
            default_timeout=20

            [window]
            width=1300
            height=800

            [screenshot]
            width=1000
            """
        ))
        config.read_file(defaults)
        config.read(cfg_file)

        if config.get('login', 'username') == '':
            raise RuntimeError('No username configured in slipsomat.cfg')

        if config.get('login', 'password') == '':
            config.set('login', 'password', getpass.getpass())

        return config

    def get_driver(self):
        # Start a new browser and return the WebDriver

        browser_name = self.config.get('selenium', 'browser')

        if browser_name == 'firefox':
            from selenium.webdriver import Firefox

            return Firefox()

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
        self.driver.set_window_size(self.config.get('window', 'width'),
                                    self.config.get('window', 'height'))
        self.wait = self.waiter()

        print('Connecting to {}:{}'.format(self.instance, institution))

        if auth_type == 'Feide' and domain != '':
            sys.stdout.write('Logging in as {}@{}...'.format(username, domain))

            self.get('/mng/login?institute={}&auth=SAML'.format(institution))

            element = self.wait.until(EC.visibility_of_element_located((By.ID, 'org_selector-selectized')))
            element.click()

            element = self.wait.until(EC.visibility_of_element_located((By.XPATH, '//div[@data-value="%s"]' % domain)))
            element.click()

            element = self.driver.find_element_by_id('selectorg_button')
            element.click()

        elif auth_type == 'SAML' and domain != '':
            sys.stdout.write('Logging in as {}@{}...'.format(username, domain))
            self.get('/mng/login?institute={}&auth={}'.format(institution, auth_type))

            element = self.wait.until(EC.visibility_of_element_located((By.ID, 'org')))
            select = Select(element)
            select.select_by_value(domain)

            element = self.driver.find_element_by_id('submit')
            element.click()
            # We cannot use submit() because of
            # http://stackoverflow.com/questions/833032/submit-is-not-a-function-error-in-javascript
        else:
            sys.stdout.write('Logging in as {}...'.format(username))
            self.get('/mng/login?institute={}&auth={}'.format(institution, auth_type))

        self.send_keys(By.ID, 'username', username)
        element = self.send_keys(By.ID, 'password', password)
        element.send_keys(Keys.RETURN)

        try:
            # Look for some known element on the Alma main screen
            self.wait_for(By.CSS_SELECTOR, '.logoAlma', 30)
        except NoSuchElementException:
            raise Exception('Failed to login to Alma')

        sys.stdout.write(' DONE\n')

    def get(self, url):
        return self.driver.get('https://{}.alma.exlibrisgroup.com/{}'.format(self.instance, url.lstrip('/')))
