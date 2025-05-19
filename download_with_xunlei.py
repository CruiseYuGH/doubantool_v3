import os
import time
import configparser
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from scrape_metadata import scrape_metadata, create_download_dir, update_series_file, get_chinese_title_from_excel
import pandas as pd
import logging
import re

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

CONFIG_FILE_PATH = 'config/config.ini'

def read_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH, encoding='utf-8')
    return config

def update_login_status(status, config):
    config['XUNLEI']['LOGIN_STATUS'] = status
    with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
        config.write(configfile)

def navigate_to_iframe(driver):
    try:
        iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "iframe"))
        )
        driver.switch_to.frame(iframe)
        time.sleep(2)
    except Exception:
        logging.error("Error switching to iframe.")

def wait_for_page_load(driver, retries=6):
    driver.refresh()
    for attempt in range(retries):
        navigate_to_iframe(driver)
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'小工具') or contains(text(),'个人片库')]"))
            )
            return True
        except Exception:
            driver.refresh()
    return False

def check_loading_element(driver):
    time.sleep(2)
    try:
        while True:
            try:
                loading_element = driver.find_element(By.XPATH,
                                                      "//ul[contains(@class, 'file-item')]/div[contains(@class, 'loading')]")
                driver.execute_script("arguments[0].scrollIntoView(true);", loading_element)
                time.sleep(2)  # 等待页面完全加载
            except:
                break
    except Exception as e:
        logging.error(f"Error during scrolling.")
def check_and_switch_device(driver, device_name):
    try:
        device_element = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.XPATH, "//div[@class='header-home']")
        )
        if device_element.text == device_name:
            return True
        else:
            logging.info(f"Switching device to: {device_name}")
            actions = ActionChains(driver)
            actions.move_to_element(device_element).click().perform()
            time.sleep(2)
            new_device_element = WebDriverWait(driver, 10).until(
                lambda d: d.find_element(By.XPATH, f"//span[contains(@class, 'device') and (text()='{device_name}' or text()='{device_name}(离线)')]")
            )
            actions.move_to_element(new_device_element).click().perform()
            time.sleep(3)
            return True
    except Exception:
        logging.error("Error switching device.")
        return False

def create_xunlei_dir(type_, title, year, config):
    download_path = config['XUNLEI']['XUNLEI_DOWNLOAD_PATH']
    if type_ == '电影':
        download_dir = os.path.join(download_path, '电影', f"{title} ({year})")
    elif type_ == '剧集':
        download_dir = os.path.join(download_path, '剧集', f"{title} ({year})")
    else:
        download_dir = os.path.join(download_path, type_, f"{title} ({year})")

    download_dir = download_dir.replace(os.path.sep, '/')

    return download_dir

def login_xunlei(driver, config):
    XUNLEI_USERNAME = config['XUNLEI']['USERNAME']
    XUNLEI_PASSWORD = config['XUNLEI']['PASSWORD']
    POPUP_HTML_PATH = os.path.join(os.getcwd(), 'xunlei', 'popup.html')

    driver.get(f"file:///{POPUP_HTML_PATH}")
    time.sleep(2)

    navigate_to_iframe(driver)

    try:
        login_button = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "span.button-login")
        )
        actions = ActionChains(driver)
        actions.move_to_element(login_button).click().perform()
    except Exception:
        # logging.error("Error clicking login button.")
        return

    try:
        account_login_button = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.XPATH, "//span[text()='账号密码登录']")
        )
        actions.move_to_element(account_login_button).click().perform()
    except Exception:
        # logging.error("Error clicking account login button.")
        return

    try:
        username_input = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.XPATH, "//input[@placeholder='请输入手机号/邮箱/账号']")
        )
        password_input = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.XPATH, "//input[@placeholder='请输入密码']")
        )
        username_input.send_keys(XUNLEI_USERNAME)
        password_input.send_keys(XUNLEI_PASSWORD)
    except Exception:
        # logging.error("Error entering username and password.")
        return

    try:
        agreement_checkbox = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.XPATH, "//input[@type='checkbox' and contains(@class, 'xlucommon-login-checkbox')]")
        )
        actions.move_to_element(agreement_checkbox).click().perform()
    except Exception:
        # logging.error("Error clicking agreement checkbox.")
        return

    try:
        submit_button = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "button.xlucommon-login-button")
        )
        actions.move_to_element(submit_button).click().perform()
    except Exception:
        # logging.error("Error clicking submit button.")
        return

    time.sleep(5)

    try:
        create_task_button = WebDriverWait(driver, 10).until(
            lambda d: d.find_elements(By.CLASS_NAME, 'button-create')
        )
        if create_task_button:
            logging.info("Login successful")
            update_login_status('LoggedIn', config)
        else:
            logging.info("Login failed")
    except Exception:
        logging.error("Error verifying login status.")

def check_login_status(driver, config):
    try:
        POPUP_HTML_PATH = os.path.join(os.getcwd(), 'xunlei', 'popup.html')
        driver.get(f"file:///{POPUP_HTML_PATH}")
        time.sleep(2)
        navigate_to_iframe(driver)
        login_button = driver.find_elements(By.CSS_SELECTOR, "span.button-login")
        if login_button:
            # logging.info("Login button detected, initiating login sequence")
            login_xunlei(driver, config)
    except Exception:
        logging.error("Error checking login status.")

def download_with_xunlei(driver, title, magnet_link, xunlei_dir, config):
    path_parts = [part for part in xunlei_dir.split('/') if part]

    check_login_status(driver, config)

    # if not wait_for_page_load(driver):
    #     logging.error("Failed to load page after multiple attempts")
    #     return False

    XUNLEI_DEVICE_NAME = config['XUNLEI']['DEVICE_NAME']
    if not check_and_switch_device(driver, XUNLEI_DEVICE_NAME):
        logging.error(f"Failed to switch to the correct device: {XUNLEI_DEVICE_NAME}")
        return False

    try:
        new_task_button = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "i.qh-icon-new")
        )
        actions = ActionChains(driver)
        actions.move_to_element(new_task_button).click().perform()
    except Exception:
        logging.error("Error clicking new task button.")
        return False

    try:
        magnet_input = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "textarea.textarea__inner")
        )
        actions.move_to_element(magnet_input).click().perform()
        magnet_input.send_keys(magnet_link)
    except Exception:
        logging.error("Error entering magnet link.")
        return False

    try:
        confirm_button = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "a.file-upload__button")
        )
        actions.move_to_element(confirm_button).click().perform()
    except Exception:
        logging.error("Error clicking confirm button.")
        return False
        
    try:
        WebDriverWait(driver, 30).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "div.file-frame__selector")
        )
    except Exception:
        logging.error("Error waiting for files to load.")
        return False

    try:
        time.sleep(2)
        frame_selector_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "i.qh-icon-checked"))
        )
        actions.move_to_element(frame_selector_button).click().perform()
    except Exception:
        logging.error("Error clicking frame selector button.")
        return False

    try:
        virtual_list = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.virtual-list-scroll"))
        )
        file_nodes = virtual_list.find_elements(By.XPATH, ".//div[@class='file-node']")
        if len(file_nodes) == 0:
            try:
                time.sleep(2)
                frame_selector_button = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "i.qh-icon-check"))
                )
                actions.move_to_element(frame_selector_button).click().perform()
            except Exception:
                logging.error("Error clicking frame selector button.")
                return False
        for node in file_nodes:
            size_text = node.find_element(By.XPATH, ".//p[@class='file-node__size']").text
            if 'MB' in size_text or 'GB' in size_text:
                size_value = float(size_text.replace('MB', '').replace('GB', '')) * (1 if 'MB' in size_text else 1024)
                if size_value > float(config['SETTINGS']['junk_file_size']):
                    check_icon = node.find_element(By.XPATH, ".//span[contains(@class, 'check-icon qh-icon-check')]")
                    actions.move_to_element(check_icon).click().perform()
    except Exception:
        logging.error("Error selecting large files.")
        return False

    try:
        more_options_button = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "i.qh-icon-more")
        )
        actions.move_to_element(more_options_button).click().perform()
    except Exception:
        logging.error("Error clicking more options button.")
        return False

    for part in path_parts[:-1]:
        try:
            check_loading_element(driver)
            folder_element = WebDriverWait(driver, 10).until(
                lambda d: d.find_element(By.XPATH, f"//p[contains(@class, 'history') and (text()='{part}/' or text()='{part}')]")
            )
            enter_button = folder_element.find_element(By.XPATH, "../div[contains(@class, 'enter')]")
            actions.move_to_element(enter_button).click().perform()
        except Exception:
            logging.error(f"Error entering folder {part}.")
            return False

    check_loading_element(driver)

    try:
        last_part = path_parts[-1]
        folder_element = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.XPATH, f"//p[contains(@class, 'history') and (text()='{last_part}' or text()='{last_part}/')]")
        )
        checkbox_container = folder_element.find_element(By.XPATH, "../span")
        folder_checkbox = checkbox_container.find_element(By.XPATH, ".//span[contains(@class, 'nas-remote__checkbox')]")
        actions.move_to_element(folder_checkbox).click().perform()
    except Exception:
        logging.error("Error selecting download folder.")
        return False

    try:
        confirm_download_button = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "button.button-base.primary-button")
        )
        actions.move_to_element(confirm_download_button).click().perform()
    except Exception:
        logging.error("Error confirming download folder.")
        return False

    try:
        time.sleep(2)
        start_download_button = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "div.submit-btn")
        )
        actions.move_to_element(start_download_button).click().perform()
        logging.info("Xunlei start download: " + title)
        time.sleep(5)
        return True
    except Exception:
        logging.error("Xunlei error starting download: " + title)
        return False

def main():
    config = read_config()

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1920x1080')
    USER_DATA_DIR = os.path.join(os.getcwd(), 'data', 'user_data')
    options.add_argument(f'--user-data-dir={USER_DATA_DIR}')
    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)
    # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    if config['XUNLEI']['LOGIN_STATUS'] == 'NotLoggedIn':
        login_xunlei(driver, config)

    excel_file = 'data/title.xlsx'
    if not os.path.exists(excel_file):
        raise FileNotFoundError(f"{excel_file} does not exist.")
    df = pd.read_excel(excel_file)

    downloaded = []

    with open(config['DOUBAN']['MAGNET_LINKS_FILE'], 'r', encoding='utf-8') as file:
        for line in file:
            config = read_config()
            type_, title, year, imdb_id, magnet_link = line.strip().split('\t')
            chinese_title = get_chinese_title_from_excel(title, df)
            clean_title = re.sub(r'[^\w\s]', ' ', title)
            download_dir = create_download_dir(type_, clean_title, year)
            xunlei_dir = create_xunlei_dir(type_, clean_title, year, config)
            if download_with_xunlei(driver, chinese_title, magnet_link, xunlei_dir, config):
                downloaded.append(magnet_link)
                if config['TMDB'].getboolean('TMDB_ENABLED', False):
                    if type_ == '剧集':
                        found_in_series = False
                        with open(config['DOUBAN']['SERIES_FILE'], 'r', encoding='utf-8') as series_file:
                            series_info = series_file.readlines()
                            for series in series_info:
                                series_title, _, series_url, scraped = series.strip().split('\t')
                                if series_title == title:
                                    found_in_series = True
                                    if scraped == 'No':
                                        scrape_metadata(type_, title, year, download_dir, chinese_title, tmdb_id=imdb_id if imdb_id != 'None' else None)
                                        update_series_file(title, 'Yes')
                                    break
                        if not found_in_series:
                            scrape_metadata(type_, title, year, download_dir, chinese_title, tmdb_id=imdb_id if imdb_id != 'None' else None)
                    else:
                        scrape_metadata(type_, title, year, download_dir, chinese_title, tmdb_id=imdb_id if imdb_id != 'None' else None)

    # 更新磁力链接文件
    with open(config['DOUBAN']['MAGNET_LINKS_FILE'], 'r', encoding='utf-8') as file:
        lines = file.readlines()
    with open(config['DOUBAN']['MAGNET_LINKS_FILE'], 'w', encoding='utf-8') as file:
        for line in lines:
            if line.strip().split('\t')[-1] not in downloaded:
                file.write(line)

    driver.quit()

if __name__ == '__main__':
    main()
