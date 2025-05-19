import os
import requests
import configparser
import re

CONFIG_FILE_PATH = 'config/config.ini'
TIMEOUT = 10  # 超时时间设置为10秒
TMDB_BASE_URL = 'https://api.themoviedb.org/3'  # 定义TMDB_BASE_URL

def read_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH, encoding='utf-8')
    return config

def get_movie_info_by_id(tmdb_id):
    try:
        config = read_config()
        TMDB_API_KEY = config['TMDB']['api_key']
        url = f"{TMDB_BASE_URL}/movie/{tmdb_id}"
        params = {
            'api_key': TMDB_API_KEY,
            'append_to_response': 'videos,trailers,images,credits,translations,keywords,release_dates',
            'language': 'zh-CN'
        }
        response = requests.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        movie_info = response.json()
        return movie_info
    except requests.RequestException:
        return None

def find_tv_show_by_imdb_id(imdb_id):
    config = read_config()
    TMDB_API_KEY = config['TMDB']['api_key']
    url = f"{TMDB_BASE_URL}/find/{imdb_id}"
    params = {
        'api_key': TMDB_API_KEY,
        'external_source': 'imdb_id'
    }
    try:
        response = requests.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if data['tv_results']:
            return imdb_id
        elif data['tv_episode_results']:
            return get_imdb_id_from_tmdb(data['tv_episode_results'][0]['show_id'])
    except requests.RequestException as e:
        print(f"TMDB请求错误.")
        return None
    except IndexError:
        print("未找到有效的电视剧集信息")
        return None

def get_imdb_id_from_tmdb(tmdb_id):
    config = read_config()
    TMDB_API_KEY = config['TMDB']['api_key']
    url = f"{TMDB_BASE_URL}/tv/{tmdb_id}/external_ids"
    params = {'api_key': TMDB_API_KEY}

    try:
        response = requests.get(url, params=params, timeout=TIMEOUT)
        data = response.json()
        return data.get('imdb_id')
    except requests.RequestException as e:
        print(f"TMDB请求错误.")
        return None

def get_tv_info_by_id(tmdb_id):
    try:
        config = read_config()
        TMDB_API_KEY = config['TMDB']['api_key']
        url = f"{TMDB_BASE_URL}/tv/{tmdb_id}"
        params = {
            'api_key': TMDB_API_KEY,
            'append_to_response': 'videos,trailers,images,credits,translations,external_ids',
            'language': 'zh-CN'
        }
        response = requests.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        tv_info = response.json()
        return tv_info
    except requests.RequestException:
        return None

def get_tv_info_by_imdb_id(imdb_id):
    imdb_id = find_tv_show_by_imdb_id(imdb_id)
    try:
        config = read_config()
        TMDB_API_KEY = config['TMDB']['api_key']
        base_url = "https://api.themoviedb.org/3"
        find_url = f"{base_url}/find/{imdb_id}"
        params = {
            'api_key': TMDB_API_KEY,
            'external_source': 'imdb_id',
        }

        response = requests.get(find_url, params=params, timeout=TIMEOUT)
        data = response.json()
        tv_results = data.get('tv_results', [])

        if tv_results:
            tv_id = tv_results[0]['id']
            return get_tv_info_by_id(tv_id)
        else:
            return None
    except requests.RequestException:
        print("Error decoding JSON response")
        return None

def get_movie_info_by_name(title, year):
    try:
        config = read_config()
        TMDB_API_KEY = config['TMDB']['api_key']
        url = f"{TMDB_BASE_URL}/search/movie"
        params = {
            'api_key': TMDB_API_KEY,
            'query': title,
            'language': 'zh-CN'
        }
        response = requests.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        search_results = response.json().get('results', [])
        for result in search_results:
            if str(result.get('release_date', '')).startswith(str(year)):
                movie_info = get_movie_info_by_id(result['id'])
                return movie_info
    except requests.RequestException:
        return None

def get_tv_info_by_name(title, year):
    try:
        config = read_config()
        TMDB_API_KEY = config['TMDB']['api_key']
        url = f"{TMDB_BASE_URL}/search/tv"
        params = {
            'api_key': TMDB_API_KEY,
            'query': title,
            'language': 'zh-CN'
        }
        response = requests.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        search_results = response.json().get('results', [])
        for result in search_results:
            if result.get('first_air_date', '').startswith(str(year)):
                tv_info = get_tv_info_by_id(result['id'])
                return tv_info
    except requests.RequestException:
        return None

def extract_chinese_info(info):
    chinese_translation = None
    for translation in info.get('translations', {}).get('translations', []):
        if translation.get('iso_639_1') == 'zh-CN':
            chinese_translation = translation.get('data', {})
            break
    return chinese_translation if chinese_translation else {}

def merge_info(default_info, chinese_info):
    merged_info = default_info
    for key, value in chinese_info.items():
        if value:
            merged_info[key] = value
    return merged_info

def save_images(images, download_dir):
    proxies = {
        "http": "http://192.168.100.175:7890",  # HTTP代理
        "https": "http://192.168.100.175:7890"  # HTTPS代理
    }
    for image_type, url in images.items():
        if url:
            try:
                img_data = requests.get(f"https://image.tmdb.org/t/p/original{url}",proxies=proxies,  timeout=TIMEOUT).content
                with open(os.path.join(download_dir, f"{image_type}.jpg"), 'wb') as handler:
                    handler.write(img_data)
                # print(f"Successfully saved {image_type}.jpg")
            except requests.RequestException as e:
                print(f"Failed to download {image_type} image.")

def get_chinese_title_from_excel(full_title, df):
    title = df.loc[df['Full Title'] == full_title, 'Title']
    if title.empty:
        raise ValueError(f"Full title '{full_title}' chinese title not found in the Excel file.")
    title = title.iloc[0]
    cleaned_title = re.sub(r'[^\w\s]', ' ', title)
    return cleaned_title

def get_season_from_excel(full_title, df):
    season = df.loc[df['Full Title'] == full_title, 'Season']
    if season.empty:
        raise ValueError(f"Full title '{full_title}' season not found in the Excel file.")
    season = season.iloc[0]
    return season

def get_part_from_excel(full_title, df):
    part = df.loc[df['Full Title'] == full_title, 'Part']
    if part.empty:
        raise ValueError(f"Full title '{full_title}' part not found in the Excel file.")
    part = part.iloc[0]
    return part

def create_download_dir(type_, title, year):
    config = read_config()
    download_path = config['DOUBAN']['download_path']
    if type_ == '电影':
        download_dir = os.path.join(download_path, '电影', f"{title} ({year})")
    elif type_ == '剧集':
        download_dir = os.path.join(download_path, '剧集', f"{title} ({year})")
    else:
        download_dir = os.path.join(download_path, type_, f"{title} ({year})")

    download_dir = download_dir.replace(os.path.sep, '/')

    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    return download_dir

def scrape_metadata(type_, title, year, download_dir, chinese_title, tmdb_id=None):
    movie_info = None

    if type_ == '电影':
        if tmdb_id and tmdb_id != 'Unknown':
            movie_info = get_movie_info_by_id(tmdb_id)
        if not movie_info:
            movie_info = get_movie_info_by_name(title, year)
        if movie_info:
            chinese_info = extract_chinese_info(movie_info)
            movie_info = merge_info(movie_info, chinese_info)
            with open(os.path.join(download_dir, f"{chinese_title} ({year}).nfo"), 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="utf-8"?>\n')
                f.write('<movie>\n')
                f.write('  <dateadded>{}</dateadded>\n'.format(
                    movie_info.get('release_date', '')))
                f.write('  <tmdbid>{}</tmdbid>\n'.format(
                    movie_info.get('id', '')))
                f.write('  <uniqueid type="tmdb" default="false">{}</uniqueid>\n'.format(
                    movie_info.get('id', '')))
                f.write('  <imdbid>{}</imdbid>\n'.format(
                    movie_info.get('imdb_id', '')))
                f.write('  <uniqueid type="imdb" default="true">{}</uniqueid>\n'.format(
                    movie_info.get('imdb_id', '')))
                f.write('  <plot><![CDATA[{}]]></plot>\n'.format(
                    movie_info.get('overview', '')))
                f.write('  <outline><![CDATA[{}]]></outline>\n'.format(
                    movie_info.get('overview', '')))
                if 'crew' in movie_info.get('credits', {}):
                    director = next((crew for crew in movie_info['credits']['crew'] if crew['job'] == 'Director'), None)
                    if director:
                        f.write('  <director tmdbid="{}">{}</director>\n'.format(director['id'], director['name']))
                if 'cast' in movie_info.get('credits', {}):
                    for idx, cast in enumerate(movie_info['credits']['cast']):
                        f.write('  <actor>\n')
                        f.write('    <name>{}</name>\n'.format(cast['name']))
                        f.write('    <type>Actor</type>\n')
                        f.write('    <role>{}</role>\n'.format(cast['character']))
                        f.write('    <order>{}</order>\n'.format(idx))
                        f.write('    <tmdbid>{}</tmdbid>\n'.format(cast['id']))
                        if 'profile_path' in cast:
                            f.write('    <thumb>https://image.tmdb.org/t/p/h632{}</thumb>\n'.format(cast['profile_path']))
                            f.write('    <profile>https://www.themoviedb.org/person/{}/{}\n'.format(cast['id'], cast['name']))
                        f.write('  </actor>\n')
                f.write('  <genre>{}</genre>\n'.format(
                    ', '.join([genre['name'] for genre in movie_info.get('genres', [])])))
                f.write('  <rating>{}</rating>\n'.format(
                    movie_info.get('vote_average', '')))
                f.write('  <title>{}</title>\n'.format(
                    movie_info.get('title', '')))
                f.write('  <originaltitle>{}</originaltitle>\n'.format(
                    movie_info.get('original_title', '')))
                f.write('  <premiered>{}</premiered>\n'.format(
                    movie_info.get('release_date', '')))
                f.write('  <year>{}</year>\n'.format(
                    movie_info.get('release_date', '').split('-')[0]))
                f.write('</movie>\n')
            images = {
                'poster': movie_info.get('poster_path', ''),
                'backdrop': movie_info.get('backdrop_path', '')
            }
            save_images(images, download_dir)
        else:
            print(f"Error fetching movie details for {title}.")
    elif type_ == '剧集':
        tv_info = None
        if tmdb_id and tmdb_id != 'Unknown':
            tv_info = get_tv_info_by_imdb_id(tmdb_id)
        if not tv_info:
            tv_info = get_tv_info_by_name(title, year)
        if tv_info:
            chinese_info = extract_chinese_info(tv_info)
            tv_info = merge_info(tv_info, chinese_info)
            with open(os.path.join(download_dir, "tvshow.nfo"), 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="utf-8"?>\n')
                f.write('<tvshow>\n')
                f.write('  <dateadded>{}</dateadded>\n'.format(
                    tv_info.get('first_air_date', '')))
                f.write('  <tmdbid>{}</tmdbid>\n'.format(
                    tv_info.get('id', '')))
                f.write('  <imdbid>{}</imdbid>\n'.format(
                    tv_info.get('imdb_id', '')))
                f.write('  <uniqueid type="tmdb" default="false">{}</uniqueid>\n'.format(
                    tv_info.get('id', '')))
                f.write('  <uniqueid type="imdb" default="true">{}</uniqueid>\n'.format(
                    tv_info.get('imdb_id', '')))
                f.write('  <title>{}</title>\n'.format(
                    tv_info.get('name', '')))
                f.write('  <originaltitle>{}</originaltitle>\n'.format(
                    tv_info.get('original_name', '')))
                f.write('  <year>{}</year>\n'.format(
                    tv_info.get('first_air_date', '').split('-')[0]))
                f.write('  <plot><![CDATA[{}]]></plot>\n'.format(tv_info.get('overview', '')))
                f.write('  <outline><![CDATA[{}]]></outline>\n'.format(
                    tv_info.get('overview', '')))
                f.write('  <rating>{}</rating>\n'.format(tv_info.get('vote_average', '')))
                f.write('  <votes>{}</votes>\n'.format(tv_info.get('vote_count', '')))
                f.write('  <genre>{}</genre>\n'.format(
                    ', '.join([genre['name'] for genre in tv_info.get('genres', [])])))
                f.write('  <studio>{}</studio>\n'.format(
                    ', '.join([network['name'] for network in tv_info.get('networks', [])])))
                f.write('  <status>{}</status>\n'.format(tv_info.get('status', '')))
                f.write('  <premiered>{}</premiered>\n'.format(tv_info.get('first_air_date', '')))
                if 'crew' in tv_info.get('credits', {}):
                    director = next((crew for crew in tv_info['credits']['crew'] if crew['job'] == 'Director'), None)
                    if director:
                        f.write('  <director tmdbid="{}">{}</director>\n'.format(director['id'], director['name']))
                if 'cast' in tv_info.get('credits', {}):
                    for idx, cast in enumerate(tv_info['credits']['cast']):
                        f.write('  <actor>\n')
                        f.write('    <name>{}</name>\n'.format(cast['name']))
                        f.write('    <type>Actor</type>\n')
                        f.write('    <role>{}</role>\n'.format(cast['character']))
                        f.write('    <order>{}</order>\n'.format(idx))
                        f.write('    <tmdbid>{}</tmdbid>\n'.format(cast['id']))
                        if 'profile_path' in cast:
                            f.write('    <thumb>https://image.tmdb.org/t/p/h632{}</thumb>\n'.format(cast['profile_path']))
                            f.write('    <profile>https://www.themoviedb.org/person/{}/{}\n'.format(cast['id'], cast['name']))
                        f.write('  </actor>\n')
                f.write('</tvshow>\n')
            images = {
                'poster': tv_info.get('poster_path', ''),
                'backdrop': tv_info.get('backdrop_path', '')
            }
            save_images(images, download_dir)
        else:
            print(f"Error fetching TV show details for {title}.")

def update_series_file(title, new_status):
    config = read_config()
    series_file = config['DOUBAN']['series_file']
    if os.path.exists(series_file):
        with open(series_file, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        with open(series_file, 'w', encoding='utf-8') as file:
            for line in lines:
                if '\t' in line:
                    saved_title, year, series_url, status = line.strip().split('\t')
                    if saved_title == title:
                        file.write(f"{saved_title}\t{year}\t{series_url}\t{new_status}\n")
                    else:
                        file.write(line)
