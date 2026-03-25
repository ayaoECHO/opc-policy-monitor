import requests
from bs4 import BeautifulSoup
import json
import datetime
import os
import re
import time

# 1. 配置全维度采集矩阵：官方权威 + 媒体解读 + 核心城市
TARGET_CONFIG = {
    "中央/全国": {
        "中国政府网": "https://www.gov.cn/zhengce/zuixin.htm",
        "工信部": "https://www.miit.gov.cn/xwfb/zcjd/index.html",
        "人民网AI": "http://ai.people.com.cn/"
    },
    "四川大本营": {
        "官方-省经信厅": "https://jxt.sc.gov.cn/scjxt/ggtz/zt_list.shtml",
        "官方-成都市经信局": "https://cdjx.chengdu.gov.cn/cdjx/c115217/jsj_list.shtml",
        "媒体-四川发布": "https://www.sc.gov.cn/11354/11355/11371/scfb.shtml",
        "媒体-四川日报": "https://www.scdaily.cn/",
        "媒体-红星新闻": "https://www.cdsb.com/",
        "媒体-川观新闻": "https://www.scdaily.cn/"
    },
    "全国性核心媒体": {
        "财联社": "https://www.cls.cn/searchPage?keyword=人工智能政策",
        "界面新闻": "https://www.jiemian.com/lists/63.html",
        "36氪科技": "https://36kr.com/information/technology",
        "腾讯科技": "https://new.qq.com/ch/tech/",
        "新浪财经": "https://finance.sina.com.cn/stock/it/"
    },
    "重点城市官网": {
        "北京": "https://jxj.beijing.gov.cn/jxdt/zwxx/",
        "上海": "https://sheitc.sh.gov.cn/zcwj/index.html",
        "深圳": "http://gxj.sz.gov.cn/xxgk/xxgkml/zcfghcjjd/zcfg/",
        "杭州": "https://jxj.hangzhou.gov.cn/col/col1228963/index.html",
        "广州": "http://gxj.gz.gov.cn/gkmlpt/mindex",
        "苏州": "https://gxj.suzhou.gov.cn/szgxj/zcfg/nav.shtml"
    }
}

# 2. 关键词过滤逻辑
CORE_DOMAINS = ["一人公司", "OPC", "人工智能", "AI", "智能体", "大模型", "数字化转型", "算力"]
ACTION_WORDS = ["补贴", "政策", "措施", "奖励", "资助", "扶持", "申报", "解读", "实施细则", "征求意见"]
EXCLUDE_WORDS = ["个体工商户", "农业", "养殖", "医疗器械", "房地产"]

def is_target_policy(title):
    title_upper = title.upper()
    has_domain = any(dom in title_upper for dom in CORE_DOMAINS)
    has_action = any(act in title_upper for act in ACTION_WORDS)
    is_not_excluded = not any(ex in title_upper for ex in EXCLUDE_WORDS)
    return (has_domain and has_action) and is_not_excluded

def parse_to_markdown(paragraphs):
    """提取干货并转为简单Markdown"""
    content = ""
    for p in paragraphs:
        if re.search(r'第[一二三四五六七八九十\d]+条|万元|%|补贴|支持|奖励', p):
            content += f"- **关键信息**：{p}\n\n"
        else:
            content += f"{p}\n\n"
    return content

def run():
    db = {}
    # 加载旧数据
    if os.path.exists('data.json'):
        try:
            with open('data.json', 'r', encoding='utf-8') as f:
                items = json.load(f)
                db = {item['title']: item for item in items}
        except: pass

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    for category, sites in TARGET_CONFIG.items():
        for site_name, base_url in sites.items():
            print(f"📡 正在巡检: [{category}] {site_name}")
            
            # 默认回溯 3 页，确保抓取到近一个月的动态
            for page in range(1, 4):
                try:
                    current_url = base_url
                    if page > 1:
                        # 尝试适配常见的翻页规律
                        if ".shtml" in base_url: current_url = base_url.replace(".shtml", f"_{page-1}.shtml")
                        elif "index.html" in base_url: current_url = base_url.replace("index.html", f"index_{page-1}.html")
                    
                    resp = requests.get(current_url, headers=headers, timeout=20)
                    resp.encoding = 'utf-8'
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    
                    links = soup.find_all('a', href=True)
                    found_on_page = 0
                    
                    for a in links:
                        title = a.get_text().strip()
                        # 排除掉太短的标题和已经存在的数据
                        if len(title) > 12 and is_target_policy(title) and title not in db:
                            href = a['href']
                            full_url = href if href.startswith('http') else base_url.rsplit('/', 1)[0] + '/' + href
                            
                            # 抓取详情
                            time.sleep(0.5) # 稍微停顿，防止被封
                            detail_resp = requests.get(full_url, headers=headers, timeout=15)
                            detail_resp.encoding = 'utf-8'
                            d_soup = BeautifulSoup(detail_resp.text, 'html.parser')
                            
                            # 提取正文内容
                            paragraphs = [p.get_text().strip() for p in d_soup.find_all(['p', 'td']) if len(p.get_text().strip()) > 15]
                            
                            # 判断归属省份
                            province = "全国"
                            for p_name in ["四川", "北京", "上海", "广东", "浙江", "江苏", "深圳"]:
                                if p_name in category or p_name in site_name or p_name in title:
                                    province = p_name
                                    break

                            db[title] = {
                                "title": title,
                                "province": province,
                                "city": site_name,
                                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                                "source": f"{site_name}({category})",
                                "urls": [full_url],
                                "content": parse_to_markdown(paragraphs)
                            }
                            found_on_page += 1
                    
                    if found_on_page == 0 and page > 1: break # 这一页没新货就跳过后面
                    
                except Exception as e:
                    print(f"  ⚠️ 访问 {site_name} 异常: {e}")
                    break

    # 3. 最终数据清洗与排序
    processed_data = []
    for item in db.values():
        # 统一清理 <br> 标签，确保 Markdown 渲染整洁
        if "content" in item:
            item["content"] = item["content"].replace("<br>", "  \n")
            # 顺便清理一下可能残留的 HTML 标签
            item["content"] = re.sub(r'<[^>]+>', '', item["content"])
        processed_data.append(item)

    # 按日期倒序排列
    final_data = sorted(processed_data, key=lambda x: x.get('date', ''), reverse=True)

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)
    
    print(f"✅ 任务完成！当前库内共计 {len(final_data)} 条政策/解读。")

if __name__ == "__main__":
    run()
