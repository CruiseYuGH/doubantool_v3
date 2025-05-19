import os
import configparser
import logging
from natsort import natsorted
import pandas as pd
from scrape_metadata import get_chinese_title_from_excel, get_season_from_excel, get_part_from_excel
import shutil
import re

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# 配置文件路径
CONFIG_FILE_PATH = 'config/config.ini'
config = configparser.ConfigParser()
config.read(CONFIG_FILE_PATH, encoding='utf-8')


def read_config():
    config.read(CONFIG_FILE_PATH, encoding='utf-8')
    return config


def update_directory_timestamp(directory_path):
    current_time = None  # 将时间设置为当前时间
    os.utime(directory_path, times=current_time)


def create_hard_links():
    config = read_config()
    DOWNLOAD_PATH = config['DOUBAN']['DOWNLOAD_PATH']
    HARDLINK_PATH = config['DOUBAN']['HARDLINK_PATH']
    DOWNLOADED_MOVIES_FILE = config['DOUBAN']['DOWNLOADED_MOVIES_FILE']
    SERIES_FILE = config['DOUBAN']['SERIES_FILE']
    excel_file = 'data/title.xlsx'

    if not os.path.exists(excel_file):
        raise FileNotFoundError(f"{excel_file} does not exist.")
    df = pd.read_excel(excel_file)

    # 读取downloaded_movies.txt文件
    with open(DOWNLOADED_MOVIES_FILE, 'r', encoding='utf-8') as file:
        downloaded_movies = [line.strip().split('\t') for line in file.readlines()]

    for movie in downloaded_movies:
        title, year, type_, episode_count, hard_link_status = movie
        clean_title = re.sub(r'[^\w\s]', ' ', title)

        if hard_link_status == '否':
            chinese_title = get_chinese_title_from_excel(title, df)
            source_dir = os.path.join(DOWNLOAD_PATH, type_, f"{clean_title} ({year})")
            hardlink_parent_dir = HARDLINK_PATH

            if not os.path.exists(source_dir):
                continue

            # 检查源目录中的视频文件
            video_files = []
            source_files = []
            for root, _, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    source_files.append((root, file))
                    if file.endswith(('.mp4', '.mkv')) and os.path.getsize(file_path) > float(config['SETTINGS']['junk_file_size']) * 1024 * 1024:
                        video_files.append((root, file))

            if type_ == '电影' and len(video_files) == 1:
                target_dir = os.path.join(HARDLINK_PATH, type_, f"{chinese_title} ({year})")
                temp_dir = os.path.join(target_dir, 'temp')

                if not os.path.exists(target_dir):
                    os.makedirs(target_dir, exist_ok=True)

                # 创建临时文件夹
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)

                video_file = video_files[0]
                video_filename = os.path.basename(video_file[1])

                # 创建刮削信息文件的硬链接
                for root, file in source_files:
                    if file.endswith(('.jpg', '.nfo')):
                        temp_link_path = os.path.join(temp_dir, file)
                        os.link(os.path.join(root, file), temp_link_path)
                        shutil.move(temp_link_path, os.path.join(target_dir, file))

                # 创建视频文件的硬链接
                temp_video_link_path = os.path.join(temp_dir, f"{chinese_title} ({year}){os.path.splitext(video_filename)[1]}")
                os.link(os.path.join(video_file[0], video_file[1]), temp_video_link_path)
                shutil.move(temp_video_link_path, os.path.join(target_dir, f"{chinese_title} ({year}){os.path.splitext(video_filename)[1]}"))

                # 删除临时文件夹
                shutil.rmtree(temp_dir)
                
                update_directory_timestamp(hardlink_parent_dir)

                # 更新硬链接状态
                update_hard_link_status(title, year, type_, episode_count, '是')
                shutil.rmtree(source_dir)

            elif type_ == '剧集' and len(video_files) == int(episode_count):
                target_dir = os.path.join(HARDLINK_PATH, type_, f"{chinese_title}")
                season = get_season_from_excel(title, df)
                part = get_part_from_excel(title, df)

                if season == "Null":
                    season = "Season 1"

                season_num = int(season.split()[-1])
                temp_dir = os.path.join(target_dir, 'temp')

                if not os.path.exists(target_dir):
                    os.makedirs(target_dir, exist_ok=True)

                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)

                if part == "Null":
                    episode_dir = os.path.join(target_dir, f"{season}")
                else:
                    episode_dir = os.path.join(target_dir, f"{season}", f"{part}")

                if not os.path.exists(episode_dir):
                    os.makedirs(episode_dir, exist_ok=True)

                # 检查是否有未创建硬链接的文件
                existing_inodes = {os.stat(os.path.join(root, file)).st_ino for root, _, files in os.walk(target_dir)
                                   for file in files}

                new_files = [(root, file) for root, file in source_files if
                             os.stat(os.path.join(root, file)).st_ino not in existing_inodes]

                if not new_files:
                    shutil.rmtree(temp_dir)
                    update_hard_link_status(title, year, type_, episode_count, '是')
                    continue

                # 创建刮削信息文件的硬链接
                for root, file in new_files:
                    if file.endswith(('.jpg', '.nfo')):
                        temp_link_path = os.path.join(temp_dir, file)
                        os.link(os.path.join(root, file), temp_link_path)
                        shutil.move(temp_link_path, os.path.join(target_dir, file))

                existing_video_files = [(episode_dir, f) for f in os.listdir(episode_dir) if
                                        f.endswith(('.mp4', '.mkv'))]
                new_video_files = [(root, file) for root, file in new_files if
                                   file.endswith(('.mp4', '.mkv')) and os.path.getsize(
                                       os.path.join(root, file)) > float(config['SETTINGS']['junk_file_size']) * 1024 * 1024]

                if new_video_files:
                    if existing_video_files:
                        existing_video_files = natsorted(existing_video_files, key=lambda x: x[1])
                        video_files = natsorted(video_files, key=lambda x: x[1])

                        existing_video_inodes = [os.stat(os.path.join(video_file[0], video_file[1])).st_ino for
                                                 video_file in existing_video_files]
                        video_inodes = [os.stat(os.path.join(video_file[0], video_file[1])).st_ino for video_file in
                                        video_files]

                        if existing_video_inodes == video_inodes[:len(existing_video_inodes)]:
                            start_idx = len(existing_video_files) + 1
                            new_video_files = natsorted(new_video_files, key=lambda x: x[1])
                            for idx, video_file in enumerate(new_video_files, start=start_idx):
                                temp_link_path = os.path.join(temp_dir, f"{chinese_title} - S{season_num:02d}E{idx:02d}{os.path.splitext(video_file[1])[1]}")
                                os.link(os.path.join(video_file[0], video_file[1]), temp_link_path)
                                shutil.move(temp_link_path, os.path.join(episode_dir, f"{chinese_title} - S{season_num:02d}E{idx:02d}{os.path.splitext(video_file[1])[1]}"))
                            update_directory_timestamp(hardlink_parent_dir)
                        else:
                            for file in os.listdir(episode_dir):
                                os.remove(os.path.join(episode_dir, file))
                            for idx, video_file in enumerate(video_files, start=1):
                                temp_link_path = os.path.join(temp_dir, f"{chinese_title} - S{season_num:02d}E{idx:02d}{os.path.splitext(video_file[1])[1]}")
                                os.link(os.path.join(video_file[0], video_file[1]), temp_link_path)
                                shutil.move(temp_link_path, os.path.join(episode_dir, f"{chinese_title} - S{season_num:02d}E{idx:02d}{os.path.splitext(video_file[1])[1]}"))
                            update_directory_timestamp(hardlink_parent_dir)
                    else:
                        new_video_files = natsorted(new_video_files, key=lambda x: x[1])
                        for idx, video_file in enumerate(new_video_files, start=1):
                            temp_link_path = os.path.join(temp_dir, f"{chinese_title} - S{season_num:02d}E{idx:02d}{os.path.splitext(video_file[1])[1]}")
                            os.link(os.path.join(video_file[0], video_file[1]), temp_link_path)
                            shutil.move(temp_link_path, os.path.join(episode_dir, f"{chinese_title} - S{season_num:02d}E{idx:02d}{os.path.splitext(video_file[1])[1]}"))
                        update_directory_timestamp(hardlink_parent_dir)

                # 删除临时文件夹
                shutil.rmtree(temp_dir)
                update_hard_link_status(title, year, type_, episode_count, '是')
                shutil.rmtree(source_dir)

    # 处理series.txt文件中的剧集
    with open(SERIES_FILE, 'r', encoding='utf-8') as file:
        series_items = [line.strip().split('\t') for line in file.readlines()]

    for series_item in series_items:
        title, year, url, scraped = series_item
        clean_title = re.sub(r'[^\w\s]', ' ', title)
        chinese_title = get_chinese_title_from_excel(title, df)
        season = get_season_from_excel(title, df)
        part = get_part_from_excel(title, df)

        source_dir = os.path.join(DOWNLOAD_PATH, '剧集', f"{clean_title} ({year})")
        target_dir = os.path.join(HARDLINK_PATH, "剧集", f"{chinese_title}")
        hardlink_parent_dir = HARDLINK_PATH

        if season == "Null":
            season = "Season 1"

        season_num = int(season.split()[-1])
        temp_dir = os.path.join(target_dir, 'temp')

        if part == "Null":
            episode_dir = os.path.join(target_dir, f"{season}")
        else:
            episode_dir = os.path.join(target_dir, f"{season}", f"{part}")

        if not os.path.exists(source_dir):
            continue

        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        # 创建临时文件夹
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        if not os.path.exists(episode_dir):
            os.makedirs(episode_dir, exist_ok=True)

        source_files = []
        video_files = []
        for root, _, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                source_files.append((root, file))
                if file.endswith(('.mp4', '.mkv')) and os.path.getsize(file_path) > float(config['SETTINGS']['junk_file_size']) * 1024 * 1024:
                    video_files.append((root, file))

        # 检查是否有未创建硬链接的文件
        existing_inodes = {os.stat(os.path.join(root, file)).st_ino for root, _, files in os.walk(target_dir) for file
                           in files}

        new_files = [(root, file) for root, file in source_files if
                     os.stat(os.path.join(root, file)).st_ino not in existing_inodes]

        if not new_files:
            shutil.rmtree(temp_dir)
            continue

        # 创建刮削信息文件的硬链接
        for root, file in new_files:
            if file.endswith(('.jpg', '.nfo')):
                temp_link_path = os.path.join(temp_dir, file)
                os.link(os.path.join(root, file), temp_link_path)
                shutil.move(temp_link_path, os.path.join(target_dir, file))

        existing_video_files = [(episode_dir, f) for f in os.listdir(episode_dir) if
                                f.endswith(('.mp4', '.mkv'))]
        new_video_files = [(root, file) for root, file in new_files if
                           file.endswith(('.mp4', '.mkv')) and os.path.getsize(
                               os.path.join(root, file)) > float(config['SETTINGS']['junk_file_size']) * 1024 * 1024]

        if new_video_files:
            if existing_video_files:
                existing_video_files = natsorted(existing_video_files, key=lambda x: x[1])
                video_files = natsorted(video_files, key=lambda x: x[1])

                existing_video_inodes = [os.stat(os.path.join(video_file[0], video_file[1])).st_ino for video_file in
                                         existing_video_files]
                video_inodes = [os.stat(os.path.join(video_file[0], video_file[1])).st_ino for video_file in
                                video_files]

                if existing_video_inodes == video_inodes[:len(existing_video_inodes)]:
                    start_idx = len(existing_video_files) + 1
                    new_video_files = natsorted(new_video_files, key=lambda x: x[1])
                    for idx, video_file in enumerate(new_video_files, start=start_idx):
                        temp_link_path = os.path.join(temp_dir, f"{chinese_title} - S{season_num:02d}E{idx:02d}{os.path.splitext(video_file[1])[1]}")
                        os.link(os.path.join(video_file[0], video_file[1]), temp_link_path)
                        shutil.move(temp_link_path, os.path.join(episode_dir, f"{chinese_title} - S{season_num:02d}E{idx:02d}{os.path.splitext(video_file[1])[1]}"))
                    update_directory_timestamp(hardlink_parent_dir)
                else:
                    for file in os.listdir(episode_dir):
                        os.remove(os.path.join(episode_dir, file))
                    for idx, video_file in enumerate(video_files, start=1):
                        temp_link_path = os.path.join(temp_dir, f"{chinese_title} - S{season_num:02d}E{idx:02d}{os.path.splitext(video_file[1])[1]}")
                        os.link(os.path.join(video_file[0], video_file[1]), temp_link_path)
                        shutil.move(temp_link_path, os.path.join(episode_dir, f"{chinese_title} - S{season_num:02d}E{idx:02d}{os.path.splitext(video_file[1])[1]}"))
                    update_directory_timestamp(hardlink_parent_dir)
            else:
                new_video_files = natsorted(new_video_files, key=lambda x: x[1])
                for idx, video_file in enumerate(new_video_files, start=1):
                    temp_link_path = os.path.join(temp_dir, f"{chinese_title} - S{season_num:02d}E{idx:02d}{os.path.splitext(video_file[1])[1]}")
                    os.link(os.path.join(video_file[0], video_file[1]), temp_link_path)
                    shutil.move(temp_link_path, os.path.join(episode_dir, f"{chinese_title} - S{season_num:02d}E{idx:02d}{os.path.splitext(video_file[1])[1]}"))
                update_directory_timestamp(hardlink_parent_dir)

        # 删除临时文件夹
        shutil.rmtree(temp_dir)


def update_hard_link_status(title, year, type_, episode_count, status):
    config = read_config()
    DOWNLOADED_MOVIES_FILE = config['DOUBAN']['DOWNLOADED_MOVIES_FILE']
    with open(DOWNLOADED_MOVIES_FILE, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    with open(DOWNLOADED_MOVIES_FILE, 'w', encoding='utf-8') as file:
        for line in lines:
            if line.startswith(f"{title}\t{year}\t{type_}"):
                file.write(f"{title}\t{year}\t{type_}\t{episode_count}\t{status}\n")
            else:
                file.write(line)


def main():
    create_hard_links()


if __name__ == '__main__':
    main()
