# pfx_download.py
#
# 'N' gameday crawler
#
# Play-by-play 데이터를 parse하기 위해 raw resource를 가져온다.
# xml 포맷의 데이터에서 원하는 JSON 영역만 추출해온다.

import os
from urllib.request import urlopen
from bs4 import BeautifulSoup
import json
import requests
import numpy as np
import pandas as pd
import datetime
import time
import regex

# custom library
import logManager
from utils import print_progress
from utils import check_url
from utils import get_args

regular_start = {
    '2008': '0329',
    '2009': '0404',
    '2010': '0327',
    '2011': '0402',
    '2012': '0407',
    '2013': '0330',
    '2014': '0329',
    '2015': '0328',
    '2016': '0401',
    '2017': '0331',
    '2018': '0324'
# '2018': '0301' # 시범경기; 임시
}

playoff_start = {
    '2008': '1008',
    '2009': '0920',
    '2010': '1005',
    '2011': '1008',
    '2012': '1008',
    '2013': '1008',
    '2014': '1019',
    '2015': '1010',
    '2016': '1021',
    '2017': '1010',
    '2018': '1010' # 시범경기; 임시
}

teams = ['LG', 'KT', 'NC', 'SK', 'WO', 'SS', 'HH', 'HT', 'LT', 'OB']


def get_game_ids(args):
    # set url prefix
    timetable_url = "http://sports.news.naver.com/kbaseball/schedule/index.nhn?month="

    # parse arguments
    mon_start = args[0]
    mon_end = args[1]
    year_start = args[2]
    year_end = args[3]

    # get game ids
    game_ids = {}

    for year in range(year_start, year_end + 1):
        year_ids = {}

        for month in range(mon_start, mon_end + 1):
            month_ids = []
            timetable = timetable_url + '{}&year={}'.format(str(month), str(year))

            table_page = urlopen(timetable).read()
            soup = BeautifulSoup(table_page, 'lxml')
            buttons = soup.findAll('span', attrs={'class': 'td_btn'})

            for btn in buttons:
                address = btn.a['href']
                game_id = address.split('gameId=')[1]
                month_ids.append(game_id)

            year_ids[month] = month_ids

        game_ids[year] = year_ids

    return game_ids


def download_relay(args, lm=None):
    # return True or False
    relay_url = 'http://m.sports.naver.com/ajax/baseball/gamecenter/kbo/relayText.nhn'
    record_url = 'http://m.sports.naver.com/ajax/baseball/gamecenter/kbo/record.nhn'

    game_ids = get_game_ids(args)
    if (game_ids is None) or (len(game_ids) == 0):
        print('no game ids')
        print('args: {}'.format(args))
        if lm is not None:
            lm.log('no game ids')
            lm.log('args: {}'.format(args))
        return False

    if lm is not None:
        lm.resetLogHandler()
        lm.setLogPath(os.getcwd())
        lm.setLogFileName('relay_download_log.txt')
        lm.cleanLog()
        lm.createLogHandler()
        lm.log('---- Relay Text Download Log ----')

    if not os.path.isdir('pbp_data'):
        os.mkdir('pbp_data')
    os.chdir('pbp_data')
    # path: pbp_data

    print("##################################################")
    print("######        DOWNLOAD RELAY DATA          #######")
    print("##################################################")

    for year in game_ids.keys():
        start1 = time.time()
        print(" Year {}".format(year))
        if len(game_ids[year]) == 0:
            print('month id is empty')
            print('args: {}'.format(args))
            if lm is not None:
                lm.log('month id is empty')
                lm.log('args : {}'.format(args))
            return False

        if not os.path.isdir(str(year)):
            os.mkdir(str(year))
        os.chdir(str(year))
        # path: pbp_data/year

        for month in game_ids[year].keys():
            start2 = time.time()
            print("  Month {}".format(month))
            if len(game_ids[year][month]) == 0:
                print('month id is empty')
                print('args: {}'.format(args))
                if lm is not None:
                    lm.log('month id is empty')
                    lm.log('args : {}'.format(args))
                return False

            if not os.path.isdir(str(month)):
                os.mkdir(str(month))
            os.chdir(str(month))
            # path: pbp_data/year/month

            # download
            done = 0
            skipped = 0
            for game_id in game_ids[year][month]:
                if (int(game_id[:4]) < 2008) or (int(game_id[:4]) > datetime.datetime.now().year):
                    skipped += 1
                    continue
                if int(game_id[4:8]) < int(regular_start[game_id[:4]]):
                    skipped += 1
                    continue
                if int(game_id[4:8]) >= int(playoff_start[game_id[:4]]):
                    skipped += 1
                    continue
                if game_id[8:10] not in teams:
                    skipped += 1
                    continue

                if not check_url(relay_url):
                    skipped += 1
                    if lm is not None:
                        lm.log('URL error : {}'.format(relay_url))
                    continue

                if (int(game_id[:4]) == datetime.datetime.now().year) &\
                   (int(game_id[4:6]) == datetime.datetime.now().month) &\
                   (int(game_id[6:8]) == datetime.datetime.now().day):
                        # do nothing
                       done = done
                elif (os.path.isfile(game_id + '_relay.json')) and \
                        (os.path.getsize(game_id + '_relay.json') > 0):
                    done += 1
                    if lm is not None:
                        lm.log('File Duplicate : {}'.format(game_id))
                    continue

                params = {
                    'gameId': game_id,
                    'half': '1'
                }

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                  'Chrome/59.0.3071.115 Safari/537.36',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Host': 'm.sports.naver.com',
                    'Referer': 'http://m.sports.naver.com/baseball/gamecenter/kbo/index.nhn?&gameId='
                               + game_id
                               + '&tab=relay'
                }

                res = requests.get(relay_url, params=params, headers=headers)

                if res is not None:
                    txt = {}
                    js = res.json()

                    last_inning = js['currentInning']

                    if last_inning is None:
                        skipped + + 1
                        lm.log('Gameday not found : {}'.format(game_id))
                        continue

                    txt['relayList'] = {}
                    for i in range(len(js['relayList'])):
                        txt['relayList'][js['relayList'][i]['no']] = js['relayList'][i]
                    txt['homeTeamLineUp'] = js['homeTeamLineUp']
                    txt['awayTeamLineUp'] = js['awayTeamLineUp']

                    res.close()

                    for inn in range(2, last_inning + 1):
                        params = {
                            'gameId': game_id,
                            'half': str(inn)
                        }

                        res = requests.get(relay_url, params=params, headers=headers)
                        if res is not None:
                            js = res.json()
                            for i in range(len(js['relayList'])):
                                txt['relayList'][js['relayList'][i]['no']] = js['relayList'][i]
                        else:
                            skipped += 1
                            if lm is not None:
                                lm.log('Cannot get response : {}'.format(game_id))

                        res.close()

                    # get referee
                    params = {
                        'gameId': game_id
                    }

                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, '
                                      'like Gecko) Chrome/59.0.3071.115 Safari/537.36',
                        'X-Requested-With': 'XMLHttpRequest',
                        'Host': 'm.sports.naver.com',
                        'Referer': 'http://m.sports.naver.com/baseball/gamecenter/kbo/index.nhn?gameId='
                                   + game_id
                                   + '&tab=record'
                    }

                    res = requests.get(record_url, params=params, headers=headers)

                    p = regex.compile('(?<=\"etcRecords\":\[)[\\\.\{\}\"0-9:\s\(\)\,\ba-z가-힣\{\}]+')
                    result = p.findall(res.text)
                    if len(result) == 0:
                        txt['referee'] = ''
                    else:
                        txt['referee'] = result[0].split('{')[-1].split('":"')[1].split(' ')[0]

                    p = regex.compile('stadiumName: \'\w+\'')
                    result = p.findall(res.text)
                    if len(result) == 0:
                        txt['stadium'] = ''
                    else:
                        txt['stadium'] = result[0].split('\'')[1]

                    res.close()

                    fp = open(game_id + '_relay.json', 'w', newline='\n')
                    json.dump(txt, fp, ensure_ascii=False, sort_keys=False, indent=4)
                    fp.close()

                    done += 1
                else:
                    skipped += 1
                    if lm is not None:
                        lm.log('Cannot get response : {}'.format(game_id))

                print_progress('    Downloading: ', len(game_ids[year][month]), done, skipped)

            # download done
            print_progress('    Downloading: ', len(game_ids[year][month]), done, skipped)
            print('\n        Downloaded {} files'.format(done))
            print('        (Skipped {} files)'.format(skipped))
            end2 = time.time()
            print('            -- elapsed {:.3f} sec for month {}'.format(end2 - start2, month))

            os.chdir('..')
            # path: pbp_data/year
        end1 = time.time()
        print('   -- elapsed {:.3f} sec for year {}'.format(end1 - start1, year))
        # months done
        os.chdir('..')
        # path: pbp_data/
    # years done
    os.chdir('..')
    # path: root
    return True


def download_pfx(args, lm=None):
    # return True or False
    pfx_url = 'http://m.sports.naver.com/ajax/baseball/gamecenter/kbo/pitches.nhn'

    game_ids = get_game_ids(args)
    if (game_ids is None) or (len(game_ids) == 0):
        print('no game ids')
        print('args: {}'.format(args))
        if lm is not None:
            lm.log('no game ids')
            lm.log('args: {}'.format(args))
        return False

    if lm is not None:
        lm.resetLogHandler()
        lm.setLogPath(os.getcwd())
        lm.setLogFileName('pfx_download_log.txt')
        lm.cleanLog()
        lm.createLogHandler()
        lm.log('---- Pitch Data Download Log ----')

    if not os.path.isdir('pbp_data'):
        os.mkdir('pbp_data')
    os.chdir('pbp_data')
    # path: pbp_data

    print("##################################################")
    print("######          DOWNLOAD PFX DATA          #######")
    print("##################################################")

    for year in game_ids.keys():
        print(" Year {}".format(year))
        if len(game_ids[year]) == 0:
            print('month id is empty')
            print('args: {}'.format(args))
            if lm is not None:
                lm.log('month id is empty')
                lm.log('args : {}'.format(args))
            return False

        if not os.path.isdir(str(year)):
            os.mkdir(str(year))
        os.chdir(str(year))
        # path: pbp_data/year

        for month in game_ids[year].keys():
            print("  Month {}".format(month))
            if len(game_ids[year][month]) == 0:
                print('month id is empty')
                print('args: {}'.format(args))
                if lm is not None:
                    lm.log('month id is empty')
                    lm.log('args : {}'.format(args))
                return False

            if not os.path.isdir(str(month)):
                os.mkdir(str(month))
            os.chdir(str(month))
            # path: pbp_data/year/month

            # download
            done = 0
            skipped = 0
            for game_id in game_ids[year][month]:
                if (int(game_id[:4]) < 2008) or (int(game_id[:4]) > datetime.datetime.now().year):
                    skipped += 1
                    continue
                if int(game_id[4:8]) < int(regular_start[game_id[:4]]):
                    skipped += 1
                    continue
                if int(game_id[4:8]) >= int(playoff_start[game_id[:4]]):
                    skipped += 1
                    continue

                if not check_url(pfx_url):
                    skipped += 1
                    if lm is not None:
                        lm.log('URL error : {}'.format(pfx_url))
                    continue

                if (os.path.isfile(game_id + '_pfx.json')) and \
                        (os.path.getsize(game_id + '_pfx.json') > 0):
                    done += 1
                    if lm is not None:
                        lm.log('File Duplicate : {}'.format(game_id))
                    continue

                params = {
                    'gameId': game_id
                }

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                  'Chrome/59.0.3071.115 Safari/537.36',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Host': 'm.sports.naver.com',
                    'Referer': 'http://m.sports.naver.com/baseball/gamecenter/kbo/index.nhn?&gameId='
                               + game_id
                               + '&tab=relay'
                }

                res = requests.get(pfx_url, params=params, headers=headers)

                if res is not None:
                    # load json structure
                    js = res.json()
                    if js is None:
                        lm.log('PFX data missing : {}'.format(game_id))
                        skipped += 1
                        continue
                    elif len(js) == 0:
                        lm.log('PFX data missing : {}'.format(game_id))
                        skipped += 1
                        continue

                    # json to pandas dataframe
                    df = pd.read_json(json.dumps(js))

                    # calculate pitch location(px, pz)
                    t = -df['vy0'] - np.sqrt(df['vy0'] * df['vy0'] - 2 * df['ay'] * (df['y0'] - df['crossPlateY']))
                    t /= df['ay']
                    xp = df['x0'] + df['vx0'] * t + df['ax'] * t * t * 0.5
                    zp = df['z0'] + df['vz0'] * t + df['az'] * t * t * 0.5
                    df['plateX'] = np.round(xp, 5)
                    df['plateZ'] = np.round(zp, 5)

                    # calculate pitch movement(pfx_x, pfx_z)
                    t40 = -df['vy0'] - np.sqrt(df['vy0'] * df['vy0'] - 2 * df['ay'] * (df['y0'] - 40))
                    t40 /= df['ay']
                    x40 = df['x0'] + df['vx0'] * t40 + 0.5 * df['ax'] * t40 * t40
                    vx40 = df['vx0'] + df['ax'] * t40
                    z40 = df['z0'] + df['vz0'] * t40 + 0.5 * df['az'] * t40 * t40
                    vz40 = df['vz0'] + df['az'] * t40
                    th = t - t40
                    x_no_air = x40 + vx40 * th
                    z_no_air = z40 + vz40 * th - 0.5 * 32.174 * th * th
                    df['pfx_x2'] = np.round((xp - x_no_air) * 12, 5)
                    df['pfx_z2'] = np.round((zp - z_no_air) * 12, 5)

                    # load back to json structure
                    dfjsstr = df.to_json(orient='records', force_ascii=False)
                    dfjs = json.loads(dfjsstr)

                    # dump to json file
                    fp = open(game_id + '_pfx.json', 'w', newline='\n')
                    json.dump(dfjs, fp, ensure_ascii=False, sort_keys=False, indent=4)
                    fp.close()
                    done += 1
                else:
                    skipped += 1
                    if lm is not None:
                        lm.log('Cannot get response : {}'.format(game_id))

                print_progress('    Downloading: ', len(game_ids[year][month]), done, skipped)

            # download done
            print('        Downloaded {} files'.format(done))
            print('        (Skipped {} files)'.format(skipped))

            os.chdir('..')
            # path: pbp_data/year
        # months done
        os.chdir('..')
        # path: pbp_data/
    # years done
    os.chdir('..')
    # path: root
    return True


if __name__ == '__main__':
    args = []  # m_start, m_end, y_start, y_end
    options = []  # onlyConvert, onlyDownload
    get_args(args, options)

    if options[1] is True:
        relaylm = logManager.LogManager()
        rc = download_relay(args, relaylm)
        if rc is False:
            print('Error')
            exit(1)
        relaylm.killLogManager()

    if options[2] is True:
        pfxlm = logManager.LogManager()
        rc = download_pfx(args, pfxlm)
        if rc is False:
            print('Error')
            exit(1)
        pfxlm.killLogManager()
