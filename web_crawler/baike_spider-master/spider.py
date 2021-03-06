# encoding:utf-8
from parser1 import HtmlParser
from utils import Set, Dict
from queue import Queue
from threading import Thread, Timer
from time import sleep, time
import json, os, fire
from urllib import request

'''
label_keywords = ['病毒', '微生物', '疾病', '医学', '医学术语', '科学', '科研人员', \
            '科学百科生命科学分类', '科学百科健康医疗分类', '科学百科农业科学分类']
summary_keywords = ['菌', '病毒', '微生物', '传染病', '病原体', '肺炎', '传染', '免疫', '呼吸系统']
'''

label_keywords = ['病毒', '微生物', '疾病', '医学', '医学术语', '科学', \
            '科学百科生命科学分类', '科学百科健康医疗分类', \
                  '科学百科农业科学分类','科学百科疾病症状分类','中药']
summary_keywords = ['菌', '病毒', '微生物', '传染病', '病原体', '肺炎', '传染', \
                    '免疫', '呼吸系统',\
                    '适应症','抗生素','综合征','处方药','非处方药',\
                    '影像学','造影','医学检查','医学影像','影像医学','影像检查','医学诊断','临床','症状','综合征']


class Spider(object):
    def __init__(self, worker_num=10, chunk_size=10000, log_interval=600,
                 data_dir='data', log_dir='log'):
        self.chunk_size = chunk_size
        self.log_interval = log_interval
        self.urls = Queue()
        self.results = Queue()
        self.url_cache = Set()
        self.name_cache = Set()
        self.black_urls = Set()
        self.black_cache = Dict()
        self.chunk_num = 0
        self.parser = HtmlParser(home='https://baike.baidu.com')

        self.last = 0
        self.state = 1

        if not os.path.exists(data_dir):
            os.mkdir(data_dir)
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)
        self.data_dir = data_dir
        self.log_dir = log_dir

        self.writer = Thread(target=self._write)
        self.logger = Timer(log_interval, self._log)
        self.spiders = [Thread(target=self._scrap) for _ in range(worker_num)]


    def start(self, url):
        new_urls, new_data = self.parser.parse(url)
        self.results.put(new_data)
        self.url_cache.add(url)
        self.name_cache.add(new_data['name'])
        for url in new_urls:
            self.urls.put(url)
        
        self.logger.start()
        self.writer.start()
        for spider in self.spiders:
            spider.start()
        
    def _write(self):
        """只使用self.results
           新增功能：保存爬取页面的html源代码
        """

        while self.state:
            self.chunk_num += 1
            n = 0
            with open(os.path.join(self.data_dir, '{}.json'.format(self.chunk_num)), 'wb') as fp:
                while n < self.chunk_size:
                    if not self.results.empty():
                        result = self.results.get()
                        line = json.dumps(result, ensure_ascii=False) + '\n'
                        fp.write(line.encode('utf8'))
                        print('写入词条成功')

                        n += 1
                    else:
                        sleep(10)

    def _log(self):
        now = len(self.name_cache)
        increase = now - self.last
        self.last = now
        if increase == 0:
            self.state = 0
            print('Exit: no entities scraped in this round.')
            exit()
        else:
            with open(os.path.join(self.log_dir, 'log'), 'ab+') as fp:
                message = '新增词条数量：{}，已抓取词条数量：{}；已获取url数量：{}，缓存任务数量：{}，缓存结果数量：{}.'.format(
                    increase, now, len(self.url_cache), self.urls._qsize(), self.results._qsize(),
                ) + '\n'
                fp.write(message.encode('utf8'))
        timer = Timer(self.log_interval, self._log)
        timer.start() 

    def _scrap(self):
        while self.state:
            if not self.urls.empty():
                url = self.urls.get()
                try:
                    new_urls, new_data = self.parser.parse(url) # TODO
                except:
                    print('url爬取失败')
                    self.url_cache.remove(url)
                    # 多次请求不成功的url加入黑名单
                    if url not in self.black_cache:
                        self.black_cache[url] = 1
                    self.black_cache[url] += 1
                    if self.black_cache[url] >= 3:
                        self.black_urls.add(url)
                        print('url黑名单已更新')
                    continue
                name = new_data['name']
                if name not in self.name_cache:
                    self.name_cache.add(name)
                    # TODO:设置筛选条件
                    label_related = False
                    summary_related = False
                    for label_keyword in label_keywords:
                        if label_keyword in new_data['labels']:
                            label_related = True
                            break
                    if not new_data['labels']:  # 针对无标签但与主题有关的特殊情况，设他们为True
                        label_related = True
                    for summary_keyword in summary_keywords:
                        if summary_keyword in new_data['summary']:
                            summary_related = True
                            break
                    if label_related or summary_related:
                        self.results.put(new_data)
                        print(('获取条目：' + name).encode('GBK', 'ignore').decode('GBk'))
                    else:
                        print("\033[0;31m%s\033[0m" % ('放弃条目 ' + name + ' :分类不符').encode('GBK', 'ignore').decode('GBk'))
                for url in new_urls:
                    if url not in self.url_cache and url not in self.black_urls:
                        self.url_cache.add(url)
                        self.urls.put(url)
            else:
                sleep(10)


def main(worker_num=20,
         chunk_size=10000,
         log_interval=600,
         data_dir='data',
         log_dir='log',
         start_url= 'https://baike.baidu.com/item/%E4%B8%B4%E5%BA%8A%E5%8C%BB%E5%AD%A6/201903'):
         #微生物 'https://baike.baidu.com/item/%E5%BE%AE%E7%94%9F%E7%89%A9/147527?fr=aladdin'):
         #start_url='https://baike.baidu.com/item/2019%E6%96%B0%E5%9E%8B%E5%86%A0%E7%8A%B6%E7%97%85%E6%AF%92'):
         #start_url='https://baike.baidu.com/wikitag/taglist?tagId=76625'):


    spider = Spider(
        worker_num=worker_num,
        chunk_size=chunk_size,
        log_interval=log_interval,
        data_dir=data_dir,
        log_dir=log_dir,
    )
    spider.start(start_url)


if __name__ == '__main__':
    fire.Fire(main)
