from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
import configparser
import os
import random
import json

app = Flask(__name__)
CONFIG_FILE_PATH = 'config/config.ini'


def generate_random_headers():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36'
    ]
    accept_languages = [
        'en-US,en;q=0.9',
        'zh-CN,zh;q=0.9',
        'fr-FR,fr;q=0.9',
        'de-DE,de;q=0.9'
    ]
    return {
        'User-Agent': random.choice(user_agents),
        'Accept-Language': random.choice(accept_languages)
    }


@app.route('/', methods=['GET', 'POST'])
def index():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH, encoding='utf-8')

    if request.method == 'POST':
        config['SETTINGS']['DOWNLOADER'] = request.form['downloader']
        config['DOUBAN']['USER_IDS'] = ','.join(filter(None, request.form.getlist('user_id')))
        config['BTNULL']['USERNAME'] = request.form['btnull_username']
        config['BTNULL']['PASSWORD'] = request.form['btnull_password']
        config['QBITTORRENT']['HOST'] = request.form['qb_host']
        config['QBITTORRENT']['PORT'] = request.form['qb_port']
        config['QBITTORRENT']['USERNAME'] = request.form['qb_username']
        config['QBITTORRENT']['PASSWORD'] = request.form['qb_password']
        config['XUNLEI']['USERNAME'] = request.form['xunlei_username']
        config['XUNLEI']['PASSWORD'] = request.form['xunlei_password']
        config['XUNLEI']['DEVICE_NAME'] = request.form['xunlei_device_name']
        config['XUNLEI']['XUNLEI_DOWNLOAD_PATH'] = request.form['xunlei_download_path']
        config['SETTINGS']['SLEEP_INTERVAL'] = str(int(request.form['sleep_interval']) * 3600)
        config['SETTINGS']['JUNK_FILE_SIZE'] = request.form['junk_file_size']

        config['PRIORITY']['2160_60fps'] = request.form['priority_2160_60fps']
        config['PRIORITY']['2160'] = request.form['priority_2160']
        config['PRIORITY']['1080_60fps'] = request.form['priority_1080_60fps']
        config['PRIORITY']['1080'] = request.form['priority_1080']
        config['PRIORITY']['CUSTOM_LABEL'] = request.form['custom_label']
        config['PRIORITY']['MIN_SIZE'] = request.form['priority_min_size']
        config['PRIORITY']['CUSTOM_LABEL_PRIORITY'] = '1' if request.form['highest_priority'] == 'custom_label' else '2'
        config['PRIORITY']['MIN_SIZE_PRIORITY'] = '2' if request.form['highest_priority'] == 'custom_label' else '1'

        config['TMDB']['API_KEY'] = request.form['tmdb_api_key']
        config['TMDB']['CUSTOM_HOST_ENABLED'] = 'true' if 'custom_host_enabled' in request.form else 'false'
        config['TMDB']['CUSTOM_HOST_IP_IMAGE'] = request.form['custom_host_ip_image']
        config['TMDB']['CUSTOM_HOST_IP_API'] = request.form['custom_host_ip_api']
        config['TMDB']['TMDB_ENABLED'] = 'true' if 'tmdb_enabled' in request.form else 'false'

        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        return redirect(url_for('index'))

    douban_user_ids = config['DOUBAN']['USER_IDS'].split(',') if config['DOUBAN']['USER_IDS'] else ['']
    sleep_interval_hours = int(config['SETTINGS']['SLEEP_INTERVAL']) // 3600
    return render_template('index.html', config=config, douban_user_ids=douban_user_ids, enumerate=enumerate, sleep_interval_hours=sleep_interval_hours, int=int)


@app.route('/xunlei_setup')
def xunlei_setup():
    return render_template('xunlei_setup.html')


@app.route('/xunlei/popup')
def serve_popup():
    return send_from_directory('xunlei', 'popup.html')


@app.route('/xunlei/ps.js')
def serve_ps_js():
    return send_from_directory('xunlei', 'ps.js')


if __name__ == '__main__':
    # Initialize config file
    if not os.path.exists(CONFIG_FILE_PATH):
        config = configparser.ConfigParser()
        config['DOUBAN'] = {
            'USER_IDS': '',
            'WISHLIST_FILE': 'data/wishlist.txt',
            'MAGNET_LINKS_FILE': 'data/magnet_links.txt',
            'DOWNLOADED_MOVIES_FILE': 'data/downloaded_movies.txt',
            'SERIES_FILE': 'data/series.txt',
            'TITLE_PATH': 'data/titles',
            'DOWNLOAD_PATH': '/downloads'
        }
        config['BTNULL'] = {'USERNAME': '', 'PASSWORD': ''}
        config['QBITTORRENT'] = {'HOST': '', 'PORT': '', 'USERNAME': '', 'PASSWORD': ''}
        config['SETTINGS'] = {'SLEEP_INTERVAL': '3600', 'DOWNLOADER': 'qbittorrent', 'JUNK_FILE_SIZE': '200'}
        config['PRIORITY'] = {
            '2160_60fps': '1',
            '2160': '2',
            '1080_60fps': '3',
            '1080': '4',
            'CUSTOM_LABEL': '',
            'MIN_SIZE': '0',
            'CUSTOM_LABEL_PRIORITY': '1',
            'MIN_SIZE_PRIORITY': '2'
        }
        config['HEADERS'] = generate_random_headers()
        config['TMDB'] = {
            'API_KEY': '',
            'CUSTOM_HOST_ENABLED': 'false',
            'CUSTOM_HOST_IP_IMAGE': '',
            'CUSTOM_HOST_IP_API': '',
            'TMDB_ENABLED': 'false'
        }
        config['XUNLEI'] = {'USERNAME': '', 'PASSWORD': '', 'DEVICE_NAME': '', 'LOGIN_STATUS': 'NotLoggedIn', 'XUNLEI_DOWNLOAD_PATH': ''}

        os.makedirs('config', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        os.makedirs('data/titles', exist_ok=True)
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as configfile:
            config.write(configfile)

    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
