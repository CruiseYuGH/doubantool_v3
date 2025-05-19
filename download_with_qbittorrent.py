import requests
import sys
import configparser
import os
import pandas as pd
from scrape_metadata import scrape_metadata, create_download_dir, update_series_file, get_chinese_title_from_excel
import re

CONFIG_FILE_PATH = 'config/config.ini'


def read_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH, encoding='utf-8')
    return config


def qbittorrent_login(session, config):
    QB_HOST = config['QBITTORRENT']['HOST']
    QB_PORT = config['QBITTORRENT']['PORT']
    QB_USERNAME = config['QBITTORRENT']['USERNAME']
    QB_PASSWORD = config['QBITTORRENT']['PASSWORD']

    login_data = {
        'username': QB_USERNAME,
        'password': QB_PASSWORD
    }
    headers = {
        'Referer': f'http://{QB_HOST}:{QB_PORT}/',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    response = session.post(f'http://{QB_HOST}:{QB_PORT}/api/v2/auth/login', data=login_data, headers=headers)
    if response.status_code == 200 and response.text == "Ok.":
        return True
    else:
        print(f"Failed to login to qBittorrent: {response.text}", file=sys.stderr)
        return False


def qbittorrent_download(session, magnet_link, download_dir, config):
    QB_HOST = config['QBITTORRENT']['HOST']
    QB_PORT = config['QBITTORRENT']['PORT']

    add_url = f'http://{QB_HOST}:{QB_PORT}/api/v2/torrents/add'
    add_data = {
        'urls': magnet_link,
        'savepath': download_dir
    }
    response = session.post(add_url, data=add_data)
    if response.status_code == 200:
        print(f"Successfully added magnet link to qBittorrent: {magnet_link}")
        return True
    else:
        print(f"Failed to add magnet link to qBittorrent: {response.status_code}", file=sys.stderr)
        return False


def main():
    config = read_config()
    session = requests.Session()
    if not qbittorrent_login(session, config):
        print("Exiting due to login failure.", file=sys.stderr)
        return

    MAGNET_LINKS_FILE = config['DOUBAN']['MAGNET_LINKS_FILE']
    SERIES_FILE = config['DOUBAN']['SERIES_FILE']
    excel_file = 'data/title.xlsx'

    if not os.path.exists(excel_file):
        raise FileNotFoundError(f"{excel_file} does not exist.")
    df = pd.read_excel(excel_file)

    with open(MAGNET_LINKS_FILE, 'r', encoding='utf-8') as file:
        for line in file:
            config = read_config()
            type_, title, year, imdb_id, magnet_link = line.strip().split('\t')
            chinese_title = get_chinese_title_from_excel(title, df)
            clean_title = re.sub(r'[^\w\s]', ' ', title)
            download_dir = create_download_dir(type_, clean_title, year)
            if config['TMDB'].getboolean('TMDB_ENABLED', False):
                if type_ == '剧集':
                    found_in_series = False
                    with open(SERIES_FILE, 'r', encoding='utf-8') as series_file:
                        series_info = series_file.readlines()
                        for series in series_info:
                            series_title, _, series_url, scraped = series.strip().split('\t')
                            if series_title == title:
                                found_in_series = True
                                if scraped == 'No':
                                    scrape_metadata(type_, title, year, download_dir, chinese_title,
                                                    tmdb_id=imdb_id if imdb_id != 'None' else None)
                                    update_series_file(title, 'Yes')
                                break
                    if not found_in_series:
                        scrape_metadata(type_, title, year, download_dir, chinese_title, tmdb_id=imdb_id if imdb_id != 'None' else None)
                else:
                    scrape_metadata(type_, title, year, download_dir, chinese_title, tmdb_id=imdb_id if imdb_id != 'None' else None)
            qbittorrent_download(session, magnet_link, download_dir, config)

    # 清空磁力链接文件
    with open(MAGNET_LINKS_FILE, 'w', encoding='utf-8') as file:
        file.truncate()


if __name__ == '__main__':
    main()
