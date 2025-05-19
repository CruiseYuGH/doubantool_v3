import time
import configparser
import os
from get_douban_wishlist import main as fetch_wishlist
from get_magnet_link import main as fetch_magnets
from download_with_qbittorrent import main as download_qbittorrent
from download_with_xunlei import main as download_xunlei
from create_hard_links import main as create_hardlink
import logging

CONFIG_FILE_PATH = 'config/config.ini'
# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def read_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH, encoding='utf-8')
    return config

def all_configs_present(config, downloader):
    common_params = [
        config['DOUBAN']['USER_IDS'],
        config['BTNULL']['USERNAME'],
        config['BTNULL']['PASSWORD']
    ]

    if downloader == 'qbittorrent':
        return all(common_params + [
            config['QBITTORRENT']['HOST'],
            config['QBITTORRENT']['PORT'],
            config['QBITTORRENT']['USERNAME'],
            config['QBITTORRENT']['PASSWORD']
        ])
    elif downloader == 'xunlei':
        return all(common_params + [
            config['XUNLEI']['USERNAME'],
            config['XUNLEI']['PASSWORD'],
            config['XUNLEI']['DEVICE_NAME'],
            config['XUNLEI']['XUNLEI_DOWNLOAD_PATH']
        ])

    if config['TMDB'].getboolean('TMDB_ENABLED', False):
        return all(common_params + [
            config['TMDB']['API_KEY']
        ])

    return False

def check_and_create_files():
    data_dir = 'data'
    title_dir = 'data/titles'
    files = ['wishlist.txt', 'magnet_links.txt', 'downloaded_movies.txt', 'series.txt','ignore_movies.txt']

    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    if not os.path.exists(title_dir):
        os.makedirs(title_dir)

    for file in files:
        file_path = os.path.join(data_dir, file)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                pass

def update_hosts_file(custom_host_enabled, custom_host_ip_image, custom_host_ip_api):
    hosts_file_path = "/etc/hosts"
    with open(hosts_file_path, 'r') as file:
        lines = file.readlines()

    updated_lines = []
    found_image_tmdb = False
    found_api_tmdb = False

    for line in lines:
        if 'image.tmdb.org' in line:
            found_image_tmdb = True
            if not custom_host_enabled:
                continue
            else:
                updated_lines.append(f"{custom_host_ip_image} image.tmdb.org\n")
        elif 'api.themoviedb.org' in line:
            found_api_tmdb = True
            if not custom_host_enabled:
                continue
            else:
                updated_lines.append(f"{custom_host_ip_api} api.themoviedb.org\n")
        else:
            updated_lines.append(line)

    if custom_host_enabled and not found_image_tmdb:
        updated_lines.append(f"{custom_host_ip_image} image.tmdb.org\n")
    if custom_host_enabled and not found_api_tmdb:
        updated_lines.append(f"{custom_host_ip_api} api.themoviedb.org\n")

    #with open(hosts_file_path, 'w') as file:
    #    file.writelines(updated_lines)

def main():
    check_and_create_files()
    main_count=0
    while True:
        try:
            if main_count%12==0:
                os.remove("data/ignore_movies.txt")
            config = read_config()  # 重新读取配置文件
            downloader = config['SETTINGS']['DOWNLOADER']
            if config['TMDB'].getboolean('TMDB_ENABLED', False):
                custom_host_enabled = config['TMDB'].getboolean('CUSTOM_HOST_ENABLED', False)
                custom_host_ip_image = config['TMDB'].get('CUSTOM_HOST_IP_IMAGE', '')
                custom_host_ip_api = config['TMDB'].get('CUSTOM_HOST_IP_API', '')
                update_hosts_file(custom_host_enabled, custom_host_ip_image, custom_host_ip_api)

            while not all_configs_present(config, downloader):
                print("Waiting for all configurations to be set...")
                time.sleep(10)
                config = read_config()  # 重新读取配置文件
                downloader = config['SETTINGS']['DOWNLOADER']
            create_hardlink()
            
            fetch_wishlist()
            fetch_magnets()

            if downloader == 'qbittorrent':
                download_qbittorrent()
            elif downloader == 'xunlei':
                download_xunlei()

            time.sleep(int(config['SETTINGS']['SLEEP_INTERVAL']) / 2)
            create_hardlink()

            time.sleep(int(config['SETTINGS']['SLEEP_INTERVAL']) / 2)
            main_count+=1

        except Exception as e:
            logging.error(f"An error occurred in main() loop:{e}. 等待十分钟自动重启...")
            time.sleep(600)  # 等待10分钟后重试

if __name__ == '__main__':
    main()
