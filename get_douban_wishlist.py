import requests
import xml.etree.ElementTree as ET
import configparser
import os
from bs4 import BeautifulSoup
import pandas as pd
import re

CONFIG_FILE_PATH = 'config/config.ini'

def read_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH, encoding='utf-8')
    return config

def get_wishlist_url(user_id):
    return f'https://www.douban.com/feed/people/{user_id}/interests'

def get_movie_info(movie_url, headers):
    response = requests.get(movie_url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        # 获取年份
        year_tag = soup.find('span', class_='year')
        year = year_tag.text.strip('()') if year_tag else 'Unknown'
        # 获取标题
        title_tag = soup.find('span', property='v:itemreviewed')
        title = title_tag.text.strip() if title_tag else 'Unknown'
        # 获取类型
        type_ = 'Unknown'
        recommendations_div = soup.find('div', id='recommendations')
        if recommendations_div:
            h2_tag = recommendations_div.find('h2')
            if h2_tag:
                if '电影' in h2_tag.get_text():
                    type_ = '电影'
                elif '剧集' in h2_tag.get_text():
                    type_ = '剧集'
        # 获取IMDB ID
        imdb_tag = soup.find('span', string='IMDb:')
        imdb_id = imdb_tag.next_sibling.strip() if imdb_tag else 'Unknown'
        # 获取集数
        episode_count = '1'  # 默认集数为1
        if type_ == '剧集':
            episode_tag = soup.find('span', string='集数:')
            if episode_tag:
                episode_count = episode_tag.next_sibling.strip()
        return title, type_, year, imdb_id, episode_count
    return 'Unknown', 'Unknown', 'Unknown', 'Unknown', '1'

def get_wishlist(user_id, headers):
    response = requests.get(get_wishlist_url(user_id), headers=headers)
    #print(response)
    if response.status_code == 200:
        wishlist = []
        title_mapping = {}
        root = ET.fromstring(response.content)
        for item in root.findall('./channel/item'):
            title = item.find('title').text
            if '想看' in title:
                title = title.replace('想看', '').strip()
                link = item.find('link').text
                full_title, type_, year, imdb_id, episode_count = get_movie_info(link, headers)
                if full_title != 'Unknown':
                    wishlist.append(f"{full_title}\t{type_}\t{year}\t{imdb_id}\t{episode_count}")
                    title_mapping[full_title] = title
        return wishlist, title_mapping
    else:
        print('Failed to retrieve wishlist')
        return [], {}

def load_existing_wishlist(wishlist_file):
    existing_wishlist = set()
    if os.path.exists(wishlist_file):
        with open(wishlist_file, 'r', encoding='utf-8') as f:
            for line in f:
                existing_wishlist.add(line.strip())
    return existing_wishlist

def save_wishlist(wishlist, existing_wishlist, wishlist_file):
    with open(wishlist_file, 'a', encoding='utf-8') as f:
        for item in wishlist:
            if item not in existing_wishlist:
                f.write(item + '\n')

def load_existing_excel(excel_file):
    if os.path.exists(excel_file):
        df = pd.read_excel(excel_file)
        return dict(zip(df['Full Title'], df['Title']))
    return {}

def chinese_to_arabic(chinese_num):
    chinese_digits = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    num = 0
    unit = 1

    if '十' in chinese_num:
        parts = chinese_num.split('十')
        if parts[0] == '':
            num += 10
        else:
            num += chinese_digits[parts[0]] * 10
        if len(parts) > 1 and parts[1] != '':
            num += chinese_digits[parts[1]]
    else:
        for char in chinese_num:
            num += chinese_digits[char] * unit

    return num

def save_to_excel(title_mapping, existing_title_mapping, excel_file):
    new_entries = {full_title: title for full_title, title in title_mapping.items() if
                   full_title not in existing_title_mapping}

    if new_entries:
        # 创建一个新的DataFrame，包括处理后的Title、Season和Part列
        data = []
        for full_title, title in new_entries.items():
            season_match = re.search(r'第?([零一二三四五六七八九十\d]+)季', title)
            part_match = re.search(r'Part[.\s]*(\d+)', title, re.IGNORECASE)

            if season_match:
                season_num = season_match.group(1)
                if not season_num.isdigit():
                    season_num = chinese_to_arabic(season_num)
                season = f"Season {season_num}"
                cleaned_title = re.sub(r'第?[零一二三四五六七八九十\d]+季', '', title).strip()
            else:
                season = "Null"
                cleaned_title = title

            if part_match:
                part_num = part_match.group(1)
                part = f"Part {part_num}"
                cleaned_title = re.sub(r'Part[.\s]*\d+', '', cleaned_title, flags=re.IGNORECASE).strip()
            else:
                part = "Null"

            # 替换标点符号为空格
            cleaned_title = re.sub(r'[^\w\s]', ' ', cleaned_title)

            data.append([full_title, cleaned_title, season, part])

        df = pd.DataFrame(data, columns=['Full Title', 'Title', 'Season', 'Part'])

        if os.path.exists(excel_file):
            df_existing = pd.read_excel(excel_file)
            df = pd.concat([df_existing, df], ignore_index=True)

        df.to_excel(excel_file, index=False)

def main():
    config = read_config()
    DOUBAN_USER_IDS = config['DOUBAN']['user_ids'].split(',')
    WISHLIST_FILE = config['DOUBAN']['wishlist_file']
    HEADERS = {'User-Agent': config['HEADERS']['User-Agent']}
    EXCEL_FILE = 'data/title.xlsx'

    all_wishlist = []
    all_title_mapping = {}
    for user_id in DOUBAN_USER_IDS:
        wishlist, title_mapping = get_wishlist(user_id.strip(), HEADERS)
        all_wishlist.extend(wishlist)
        all_title_mapping.update(title_mapping)
    if all_wishlist:
        existing_wishlist = load_existing_wishlist(WISHLIST_FILE)
        save_wishlist(all_wishlist, existing_wishlist, WISHLIST_FILE)

        existing_title_mapping = load_existing_excel(EXCEL_FILE)
        save_to_excel(all_title_mapping, existing_title_mapping, EXCEL_FILE)

        print('Successfully checked Douban wishlist.')
    else:
        print('No items in wishlist.')

if __name__ == '__main__':
    main()
