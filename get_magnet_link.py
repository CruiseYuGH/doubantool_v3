import requests
import urllib.parse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from scrape_metadata import get_chinese_title_from_excel, get_season_from_excel, get_part_from_excel
import time
import os
import configparser
import sys
import shutil
import pandas as pd
import re
import random
import base64


CONFIG_FILE_PATH = 'config/config.ini'


def read_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH, encoding='utf-8')
    return config


def parse_custom_label(custom_label):
    custom_label = custom_label.lower().replace('(', ' ( ').replace(')', ' ) ')
    tokens = custom_label.split()
    parsed_label = []
    current_group = []
    stack = []

    for token in tokens:
        if token == '(':
            stack.append(current_group)
            current_group = []
        elif token == ')':
            if stack:
                group = current_group
                current_group = stack.pop()
                current_group.append(group)
        elif token in ('and', 'or', 'not'):
            current_group.append(token)
        else:
            current_group.append(
                ('is', token.strip('"')) if not token.startswith('not ') else ('not', token[4:].strip('"')))

    if current_group:
        parsed_label.append(current_group)

    return parsed_label


def evaluate_condition(title, condition):
    cond_type, cond = condition
    if cond_type == 'is':
        return cond in title
    elif cond_type == 'not':
        return cond not in title


def evaluate_expression(title, expression):
    if isinstance(expression, tuple):
        return evaluate_condition(title, expression)
    elif isinstance(expression, list):
        result = None
        i = 0
        while i < len(expression):
            if isinstance(expression[i], list):
                sub_result = evaluate_expression(title, expression[i])
                if result is None:
                    result = sub_result
                elif operator == 'and':
                    result = result and sub_result
                elif operator == 'or':
                    result = result or sub_result
                i += 1
            elif expression[i] in ('and', 'or'):
                operator = expression[i]
                i += 1
            elif expression[i] == 'not':
                i += 1
                if isinstance(expression[i], list):
                    sub_result = not evaluate_expression(title, expression[i])
                else:
                    sub_result = not evaluate_condition(title, expression[i])
                if result is None:
                    result = sub_result
                elif operator == 'and':
                    result = result and sub_result
                elif operator == 'or':
                    result = result or sub_result
                i += 1
            else:
                sub_result = evaluate_condition(title, expression[i])
                if result is None:
                    result = sub_result
                elif operator == 'and':
                    result = result and sub_result
                elif operator == 'or':
                    result = result or sub_result
                i += 1
        return result
    return False


def matches_custom_label(title, parsed_label):
    if parsed_label:
        return evaluate_expression(title, parsed_label[0])
    else:
        return False


def get_seeder_count(element):
    seeder_span = element.find_element(By.XPATH, ".//span/i[@title]")
    return int(seeder_span.get_attribute("title").replace("做种", ""))


def get_size(element):
    size_element = element.find_element(By.XPATH, ".//i[@class='size']")
    size_text = size_element.text.strip()
    return parse_size(size_text)


def parse_size(size_text):
    size_value, size_unit = size_text[:-2].strip(), size_text[-2:].strip()

    if size_unit.lower() == 'kb':
        return float(size_value) * 1024
    elif size_unit.lower() == 'mb':
        return float(size_value) * 1024 * 1024
    elif size_unit.lower() == 'gb':
        return float(size_value) * 1024 * 1024 * 1024
    elif size_unit.lower() == 'tb':
        return float(size_value) * 1024 * 1024 * 1024 * 1024
    else:
        return 0


def priority(sorted_elements,title,element,PRIORITY_2160_60FPS,PRIORITY_2160,PRIORITY_1080_60FPS,PRIORITY_1080,pri_number):
    if ('2160' in title or '4k' in title) and ('60fps' in title or '60帧' in title):
        sorted_elements.append((element, get_seeder_count(element), PRIORITY_2160_60FPS + pri_number))
    elif '2160' in title or '4k' in title:
        sorted_elements.append((element, get_seeder_count(element), PRIORITY_2160 + pri_number))
    elif '1080' in title and ('60fps' in title or '60帧' in title):
        sorted_elements.append((element, get_seeder_count(element), PRIORITY_1080_60FPS + pri_number))
    elif '1080' in title:
        sorted_elements.append((element, get_seeder_count(element), PRIORITY_1080 + pri_number))
    else:
        sorted_elements.append((element, get_seeder_count(element), 5 + pri_number))

def get_series_number(title):
    match = re.search(r'更至(\d+)', title)
    if match:
        number = match.group(1)
        return int(number)
    else:
        return 0
def login(driver, config):
    BTN_USERNAME = config['BTNULL']['USERNAME']
    BTN_PASSWORD = config['BTNULL']['PASSWORD']
    LOGIN_URL = 'https://www.gying.si//user/login/'

    driver.get(LOGIN_URL)
    time.sleep(3)
    
    try:
        # 等待复选框容器可点击
        checkbox = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "checkbox-container"))
        )
        # 点击复选框
        checkbox.click()
        print("成功点击验证框")
        # 等待验证完成（根据实际场景调整条件）
        # 这里等待类名变化或Cookie设置，假设验证完成后页面会刷新
        time.sleep(2)  # 根据脚本中的1.2秒加载+1秒跳转，适当延长
        # 可选：验证是否跳转或Cookie存在
        verified_cookie = driver.get_cookie("browser_verified")
        if verified_cookie:
            print("验证成功，Cookie已设置")
        else:
            print("验证可能未成功，请检查流程")
        driver.refresh()
    except Exception as e:
        print("操作失败:", e)
    try:
        close_button = driver.find_element(By.XPATH, '//button[contains(text(), "不再提醒")]')
        close_button.click()
        time.sleep(3)
    except Exception as e:
        print("No pop-up window found:", e)
    # # 获取所有元素
    # all_elements = driver.find_elements(By.XPATH, "//*")

    # # 打印元素标签名、ID、文本及HTML结构
    # for idx, element in enumerate(all_elements):
    #     print(f"元素 {idx + 1}:")
    #     print(f"标签名: {element.tag_name}")
    #     print(f"ID: {element.get_attribute('id')}")
    #     print(f"文本内容: {element.text}")
    #     print(f"完整HTML: {element.get_attribute('outerHTML')}\n---")
	
    
    username_input = driver.find_element(By.NAME, "username")
    password_input = driver.find_element(By.NAME, "password")
    username_input.send_keys(BTN_USERNAME)
    password_input.send_keys(BTN_PASSWORD)

    login_button = driver.find_element(By.NAME, "button")
    login_button.click()
    time.sleep(3)

    if "登录失败" in driver.page_source:
        raise Exception("Failed to login")

    cookies = driver.get_cookies()
    
    return cookies


def search_resource(title, session_cookies, config):
    RESOURCE_SEARCH_URL = 'https://www.gying.in/s/1---1/'
    search_url = RESOURCE_SEARCH_URL + urllib.parse.quote(title)
    headers = {
        'User-Agent': config['HEADERS']['User-Agent'],
        'Accept-Language': config['HEADERS']['Accept-Language']
    }
    # target_cookies = {
    # 	'browser_verified': None,
    #     'BT_auth': None,
    #     'BT_cookietime': None,
        
    # }
    
    # for cookie in session_cookies:
    #     name = cookie.get('name')
    #     if name in target_cookies:
    #         target_cookies[name] = cookie.get('value')
    
    # # 组装成指定格式的字符串
    # #result = "; ".join([f"{k}={v}" if v else f"{k}=" for k, v in target_cookies.items()])
    # cookies_dict = {k: v for k, v in target_cookies.items()}
    # print(cookies_dict)
    cookies_dict = {cookie['name']: cookie['value'] for cookie in session_cookies}

    response = requests.get(search_url, headers=headers, cookies=cookies_dict)
    token_b64 = "ZDhhN2MwYjE0NmY2NmM5ZTMxODgyYWU5ZjM0MDZhZTc="
    try:
        token = base64.b64decode(token_b64).decode('utf-8')
    except Exception as e:
        print(f"Token解码失败: {e}")
        return None, False
    # 添加验证cookie
    cookies_dict['browser_verified'] = token
    #print(response.text)
    response = requests.get(search_url, headers=headers, cookies=cookies_dict)
    if response.status_code != 200:
        print(f"Failed to fetch search results for {title}: {response.status_code}", file=sys.stderr)
        return None, False

    soup = BeautifulSoup(response.text, 'html.parser')
    sr_lists_div = soup.find('div', class_='sr_lists')
    if sr_lists_div is None:
        print(f"No search results found for {title}", file=sys.stderr)
        return None, False

    first_result = sr_lists_div.find('a', href=True)
    if first_result is None:
        print(f"No search results found for {title}", file=sys.stderr)
        return None, False

    first_result_url = 'https://www.gying.si' + first_result['href']

    is_series = False
    text_div = sr_lists_div.find('div', class_='text')
    if text_div and '更至' in text_div.get_text():
        is_series = True

    return first_result_url, is_series
    


def get_magnet_link(driver, result_url, session_cookies, parsed_label, config):
    PRIORITY_2160_60FPS = int(config['PRIORITY']['2160_60fps'])
    PRIORITY_2160 = int(config['PRIORITY']['2160'])
    PRIORITY_1080_60FPS = int(config['PRIORITY']['1080_60fps'])
    PRIORITY_1080 = int(config['PRIORITY']['1080'])
    MIN_SIZE = float(config['PRIORITY']['min_size']) * 1024 * 1024 * 1024  # 转换为字节
    custom_label_priority = int(config['PRIORITY']['custom_label_priority'])
    min_size_priority = int(config['PRIORITY']['min_size_priority'])

    driver.get(result_url)
    time.sleep(3)

    elements = driver.find_elements(By.XPATH, "//li[@class='down-list2']")
    sorted_elements = []

    for element in elements:
        try:
            title_element = element.find_element(By.XPATH, ".//a[@class='torrent']")
            title = title_element.text.lower()
            size = get_size(element)
        except NoSuchElementException:
            continue

        if min_size_priority < custom_label_priority:
            if size >= MIN_SIZE:
                if matches_custom_label(title, parsed_label):
                    priority(sorted_elements, title, element, PRIORITY_2160_60FPS, PRIORITY_2160, PRIORITY_1080_60FPS,
                             PRIORITY_1080, 0)
                else:
                    priority(sorted_elements, title, element, PRIORITY_2160_60FPS, PRIORITY_2160, PRIORITY_1080_60FPS,
                             PRIORITY_1080, 5)
            else:
                if matches_custom_label(title, parsed_label):
                    priority(sorted_elements, title, element, PRIORITY_2160_60FPS, PRIORITY_2160, PRIORITY_1080_60FPS,
                             PRIORITY_1080, 10)
                else:
                    priority(sorted_elements,title,element,PRIORITY_2160_60FPS,PRIORITY_2160,PRIORITY_1080_60FPS,
                             PRIORITY_1080, 15)
        else:
            if matches_custom_label(title, parsed_label):
                if size >= MIN_SIZE:
                    priority(sorted_elements, title, element, PRIORITY_2160_60FPS, PRIORITY_2160, PRIORITY_1080_60FPS,
                             PRIORITY_1080, 0)
                else:
                    priority(sorted_elements, title, element, PRIORITY_2160_60FPS, PRIORITY_2160, PRIORITY_1080_60FPS,
                             PRIORITY_1080, 5)
            else:
                if size >= MIN_SIZE:
                    priority(sorted_elements, title, element, PRIORITY_2160_60FPS, PRIORITY_2160, PRIORITY_1080_60FPS,
                             PRIORITY_1080, 10)
                else:
                    priority(sorted_elements, title, element, PRIORITY_2160_60FPS, PRIORITY_2160, PRIORITY_1080_60FPS,
                             PRIORITY_1080, 15)

    if sorted_elements:
        sorted_elements.sort(key=lambda x: (x[2], -x[1]))
        best_element = sorted_elements[0][0]

        # 确保元素完全在视窗内
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", best_element)
        time.sleep(1)
        try:
            pattern = re.compile(r'^(.*?)(?:\s+\d+\.?\d*GB|\s+\d+\.?\d*GB\s+(?:新|详情))')
            # 使用正则表达式提取所需部分
            title = pattern.search(best_element.text).group(1)
            link_element = driver.find_element(By.XPATH,f"//a[@title='{title}']")
            # 获取磁力链接
            magnet_link = link_element.get_attribute('href')
        except:
            magnet_link = None
        # element_width = best_element.size['width']

        # action_chains = ActionChains(driver)
        # action_chains.move_to_element_with_offset(best_element, -element_width / 2 + 100, 0).context_click().perform()
        # time.sleep(1)

        # driver.execute_cdp_cmd('Browser.grantPermissions', {
        #     "permissions": ["clipboardReadWrite", "clipboardSanitizedWrite"],
        #     "origin": result_url
        # })
        # magnet_link = driver.execute_script("return navigator.clipboard.readText().then(text => { return text; });")
        if magnet_link and magnet_link.startswith("magnet:?"):
            return magnet_link
        else:
            # print(f"No magnet links found at {result_url}", file=sys.stderr)
            return None
    else:
        print(f"No suitable links found at {result_url}", file=sys.stderr)
        return None

def check_series_status(driver, result_url):
    driver.get(result_url)
    time.sleep(3)

    torrent_elements = driver.find_elements(By.XPATH, "//li[@class='down-list2']//a[@class='torrent']")
    folder_elements = driver.find_elements(By.XPATH, "//li[@class='down-list2']//a[@class='folder']")
    if torrent_elements:
        return "torrent"
    elif folder_elements:
        return "folder"
    else:
        return None

def get_series_url(driver, result_url, parsed_label, config):
    PRIORITY_2160_60FPS = int(config['PRIORITY']['2160_60fps'])
    PRIORITY_2160 = int(config['PRIORITY']['2160'])
    PRIORITY_1080_60FPS = int(config['PRIORITY']['1080_60fps'])
    PRIORITY_1080 = int(config['PRIORITY']['1080'])

    driver.get(result_url)
    time.sleep(3)

    elements = driver.find_elements(By.XPATH, "//li[@class='down-list2']//a[@class='folder']")
    sorted_elements = []

    for element in elements:
        title = element.text.lower()
        series_num = get_series_number(title)

        if matches_custom_label(title, parsed_label):
            if ('2160' in title or '4k' in title) and ('60fps' in title or '60帧' in title):
                sorted_elements.append((element, series_num, PRIORITY_2160_60FPS))
            elif '2160' in title or '4k' in title:
                sorted_elements.append((element, series_num, PRIORITY_2160))
            elif '1080' in title and ('60fps' in title or '60帧' in title):
                sorted_elements.append((element, series_num, PRIORITY_1080_60FPS))
            elif '1080' in title:
                sorted_elements.append((element,series_num, PRIORITY_1080))
            else:
                sorted_elements.append((element, series_num, 5))
        else:
            if ('2160' in title or '4k' in title) and ('60fps' in title or '60帧' in title):
                sorted_elements.append((element, series_num, PRIORITY_2160_60FPS + 5))
            elif '2160' in title or '4k' in title:
                sorted_elements.append((element, series_num, PRIORITY_2160 + 5))
            elif '1080' in title and ('60fps' in title or '60帧' in title):
                sorted_elements.append((element, series_num, PRIORITY_1080_60FPS + 5))
            elif '1080' in title:
                sorted_elements.append((element, series_num, PRIORITY_1080 + 5))
            else:
                sorted_elements.append((element, series_num, 999))

    if sorted_elements:
        sorted_elements.sort(key=lambda x: (x[2], -x[1]))
        best_element = sorted_elements[0][0]

        # 确保元素完全在视窗内
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", best_element)
        time.sleep(1)

        element_width = best_element.size['width']

        action_chains = ActionChains(driver)
        action_chains.move_to_element_with_offset(best_element, -element_width / 2 + 100, 0).click().perform()
        time.sleep(2)

        return driver.current_url
    else:
        print(f"No suitable links found at {result_url}", file=sys.stderr)
        return None


def get_series_magnet_links(driver, title, config):
    SERIES_FILE = config['DOUBAN']['SERIES_FILE']
    TITLE_PATH = config['DOUBAN']['TITLE_PATH']

    connection = False
    series_url = None
    if os.path.exists(SERIES_FILE):
        with open(SERIES_FILE, 'r', encoding='utf-8') as file:
            for line in file:
                if '\t' in line:
                    saved_title, year, url, label = line.strip().split('\t')
                    if saved_title == title:
                        series_url = url
                        break

    if not series_url:
        print(f"No series URL found for {title}", file=sys.stderr)
        return [], connection

    driver.get(series_url)
    time.sleep(3)

    elements = driver.find_elements(By.XPATH, "//ul[@class='down321']//i[@class='icon-content_copy copy']")
    magnet_links = []
    if elements:
        connection = True

    for element in elements:
        try:
            copy_icon = element
            action_chains = ActionChains(driver)
            action_chains.move_to_element(copy_icon).click().perform()
            time.sleep(0.1)

            driver.execute_cdp_cmd('Browser.grantPermissions', {
                "permissions": ["clipboardReadWrite", "clipboardSanitizedWrite"],
                "origin": series_url
            })
            magnet_link = driver.execute_script("return navigator.clipboard.readText().then(text => { return text; });")
            if magnet_link and magnet_link.startswith("magnet:?"):
                title_file = os.path.join(TITLE_PATH, f"{title}.txt")
                if os.path.exists(title_file):
                    with open(title_file, 'r', encoding='utf-8') as file:
                        existing_links = file.read().splitlines()
                else:
                    existing_links = []

                if magnet_link not in existing_links:
                    magnet_links.append(magnet_link)
                    with open(title_file, 'a', encoding='utf-8') as file:
                        file.write(f"{magnet_link}\n")

        except Exception as e:
            print(f"Error processing element: {e}", file=sys.stderr)

    return magnet_links, connection


def save_magnet_links(magnet_links, config):
    MAGNET_LINKS_FILE = config['DOUBAN']['MAGNET_LINKS_FILE']

    with open(MAGNET_LINKS_FILE, 'a', encoding='utf-8') as file:
        for item in magnet_links:
            file.write(f"{item}\n")


def save_downloaded_movie(title, year, type_, episode_count, config):
    DOWNLOADED_MOVIES_FILE = config['DOUBAN']['DOWNLOADED_MOVIES_FILE']

    with open(DOWNLOADED_MOVIES_FILE, 'a', encoding='utf-8') as file:
        file.write(f"{title}\t{year}\t{type_}\t{episode_count}\t否\n")


def save_series(title, year, series_url, config):
    SERIES_FILE = config['DOUBAN']['SERIES_FILE']

    with open(SERIES_FILE, 'a', encoding='utf-8') as file:
        file.write(f"{title}\t{year}\t{series_url}\tNo\n")


def remove_series(title, config):
    SERIES_FILE = config['DOUBAN']['SERIES_FILE']

    if os.path.exists(SERIES_FILE):
        with open(SERIES_FILE, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        with open(SERIES_FILE, 'w', encoding='utf-8') as file:
            for line in lines:
                if line.strip().split('\t')[0] != title:
                    file.write(line)


def main():
    config = read_config()

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1920x1080')
    options.add_argument('--remote-debugging-port=9222')
    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)
    # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    paser_custom_label = parse_custom_label(config['PRIORITY']['CUSTOM_LABEL'])

    magnet_links = []

    with open(config['DOUBAN']['WISHLIST_FILE'], 'r', encoding='utf-8') as file:
        wishlist = [line.strip() for line in file]

    downloaded_movies = set()
    if os.path.exists(config['DOUBAN']['DOWNLOADED_MOVIES_FILE']):
        with open(config['DOUBAN']['DOWNLOADED_MOVIES_FILE'], 'r', encoding='utf-8') as file:
            for line in file:
                downloaded_movies.add(line.strip().split('\t')[0])
                
    IGNORE_MOVIES_FILE = config['DOUBAN']['IGNORE_MOVIES_FILE']
    if os.path.exists(config['DOUBAN']['IGNORE_MOVIES_FILE']):
        with open(config['DOUBAN']['IGNORE_MOVIES_FILE'], 'r', encoding='utf-8') as file:
            for line in file:
                downloaded_movies.add(line.strip())

    series_list = set()
    if os.path.exists(config['DOUBAN']['SERIES_FILE']):
        with open(config['DOUBAN']['SERIES_FILE'], 'r', encoding='utf-8') as file:
            for line in file:
                if '\t' in line:
                    saved_title, _, _, _ = line.strip().split('\t')
                    series_list.add(saved_title)

    if all(item.split('\t')[0] in downloaded_movies for item in wishlist):
        print("没有新增想看影视")
    else:
        session_cookies = login(driver, config)
        for item in wishlist:
            title, type_, year, imdb_id, episode_count = item.split("\t")
            if title in downloaded_movies:
                continue
            result_url, is_series = search_resource(f"{title} ({year})", session_cookies, config)
            if result_url:
                if type_ == "剧集":
                    series_status = check_series_status(driver,result_url)

                    if series_status == "torrent":
                        if title not in series_list:
                            magnet_link = get_magnet_link(driver, result_url, session_cookies, paser_custom_label,
                                                          config)
                            if magnet_link:
                                print(f"Magnet link for {title}: {magnet_link}")
                                magnet_links.append(f"{type_}\t{title}\t{year}\t{imdb_id}\t{magnet_link}")
                                save_downloaded_movie(title, year, type_, episode_count, config)

                        else:
                            excel_file = 'data/title.xlsx'
                            df = pd.read_excel(excel_file)
                            clean_title = re.sub(r'[^\w\s]', ' ', title)
                            chinese_title = get_chinese_title_from_excel(title, df)
                            season = get_season_from_excel(title, df)
                            part = get_part_from_excel(title, df)
                            DOWNLOAD_PATH = config['DOUBAN']['DOWNLOAD_PATH']
                            source_dir = os.path.join(DOWNLOAD_PATH, type_, f"{clean_title} ({year})")
                            target_dir = os.path.join(DOWNLOAD_PATH, "硬链接", type_, f"{chinese_title}")
                            if season == "Null":
                                season = "Season 1"

                            if part == "Null":
                                episode_dir = os.path.join(target_dir, f"{season}")
                            else:
                                episode_dir = os.path.join(target_dir, f"{season}", f"{part}")

                            if os.path.exists(source_dir):
                                video_files = []
                                for root, _, files in os.walk(source_dir):
                                    for file in files:
                                        file_path = os.path.join(root, file)
                                        if file.endswith(('.mp4', '.mkv')) and os.path.getsize(file_path) > float(
                                                config['SETTINGS']['junk_file_size']) * 1024 * 1024:
                                            video_files.append((root, file))

                                if (len(video_files)) != int(episode_count):
                                    magnet_link = get_magnet_link(driver, result_url, session_cookies, paser_custom_label, config)
                                    if magnet_link:
                                        shutil.rmtree(source_dir)
                                        if os.path.exists(episode_dir):
                                            shutil.rmtree(episode_dir)
                                        print(f"Magnet link for {title}: {magnet_link}")
                                        magnet_links.append(f"{type_}\t{title}\t{year}\t{imdb_id}\t{magnet_link}")
                                        remove_series(title, config)
                                        save_downloaded_movie(title, year, type_, episode_count, config)
                                        title_file = os.path.join(config['DOUBAN']['TITLE_PATH'], f"{title}.txt")
                                        if os.path.exists(title_file):
                                            os.remove(title_file)
                                else:
                                    remove_series(title, config)
                                    save_downloaded_movie(title, year, type_, episode_count, config)
                                    title_file = os.path.join(config['DOUBAN']['TITLE_PATH'], f"{title}.txt")
                                    if os.path.exists(title_file):
                                        os.remove(title_file)

                            else:
                                magnet_link = get_magnet_link(driver, result_url, session_cookies, paser_custom_label, config)
                                if magnet_link:
                                    if os.path.exists(episode_dir):
                                        shutil.rmtree(episode_dir)
                                    print(f"Magnet link for {title}: {magnet_link}")
                                    magnet_links.append(f"{type_}\t{title}\t{year}\t{imdb_id}\t{magnet_link}")
                                    remove_series(title, config)
                                    save_downloaded_movie(title, year, type_, episode_count, config)
                                    title_file = os.path.join(config['DOUBAN']['TITLE_PATH'], f"{title}.txt")
                                    if os.path.exists(title_file):
                                        os.remove(title_file)

                    elif series_status == "folder":
                        if title not in series_list:
                            with open(os.path.join(config['DOUBAN']['TITLE_PATH'], f"{title}.txt"), 'w', encoding='utf-8') as file:
                                file.write('')
                            series_url = get_series_url(driver, result_url, paser_custom_label, config)
                            if series_url:
                                save_series(title, year, series_url, config)
                        magnet_links_series, connection = get_series_magnet_links(driver, title, config)
                        if magnet_links_series:
                            for magnet_link in magnet_links_series:
                                print(f"Magnet link for {title}: {magnet_link}")
                                magnet_links.append(f"{type_}\t{title}\t{year}\t{imdb_id}\t{magnet_link}")
                        if not is_series and connection:
                            remove_series(title, config)
                            save_downloaded_movie(title, year, type_, episode_count, config)
                            title_file = os.path.join(config['DOUBAN']['TITLE_PATH'], f"{title}.txt")
                            if os.path.exists(title_file):
                                os.remove(title_file)

                    else:
                        print(f"No suitable links found for {title}", file=sys.stderr)
                        with open(IGNORE_MOVIES_FILE, 'a', encoding='utf-8') as file:
                            file.write(f"{title}\n")
                        ####

                else:
                    magnet_link = get_magnet_link(driver, result_url, session_cookies, paser_custom_label, config)
                    if magnet_link:
                        print(f"Magnet link for {title}: {magnet_link}")
                        magnet_links.append(f"{type_}\t{title}\t{year}\t{imdb_id}\t{magnet_link}")
                        save_downloaded_movie(title, year, type_, episode_count, config)
                    else:
                        print(f"No suitable links found for {title}", file=sys.stderr)
                        with open(IGNORE_MOVIES_FILE, 'a', encoding='utf-8') as file:
                            file.write(f"{title}\n")
                        ####
            else:
                print(f"Failed to search for {title}", file=sys.stderr)
                with open(IGNORE_MOVIES_FILE, 'a', encoding='utf-8') as file:
                            file.write(f"{title}\n")
                ####

    save_magnet_links(magnet_links, config)
    driver.quit()


if __name__ == '__main__':
    main()
