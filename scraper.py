import requests
from bs4 import BeautifulSoup
import json
import datetime
import os
import re

# 目标站点：聚焦成都 AI & OPC 核心发布源
TARGETS = {
    "成都市经信局": "https://cdjx.chengdu.gov.cn/cdjx/c115217/jsj_list.shtml",
    "成都高新区": "https://www.cdht.gov.cn/cdht/c139391/gk_list.shtml",
    "四川日报": "https://www.scdaily.cn/",
    "红星新闻": "https://www.cdsb.com/"
}

# 严格过滤：必须同时满足（领域词）+（政策动作词）
CORE_DOMAINS = ["一人公司", "OPC", "人工智能", "AI", "大模型"]
ACTION_WORDS = ["补贴", "政策", "措施", "奖励", "资助", "扶持", "申报", "征求意见"]
EXCLUDE_WORDS = ["个体工商户", "个人独资", "农业", "房地产"]

def is_target_policy(title):
    t = title.upper()
    has_domain = any(d in t for d in CORE_DOMAINS)
    has_action = any(a in t for a in ACTION_WORDS)
    is_clean = not any(e in t for e in EXCLUDE_WORDS)
    return has_domain and has_action and is_clean

def parse_to_structured_markdown(text_list):
    """
    仿照你的手工文档，将散乱的段落重组为带标题的条文格式
    """
    structured_content = ""
    for text in text_list:
        # 识别条款序号，自动加粗作为小标题
        if re.match(r'第[一二三四五六七八九十\d]+条', text):
            structured_content += f"\n\n### {text}\n"
        elif any(kw in text for kw in ["万元", "%", "补贴", "支持"]):
            # 包含金额和比例的句子，自动标记为重点
            structured_content += f"- **核心干货**：{text}\n"
        else:
            structured_content += f"{text}\n"
    return structured_content

def run():
    db = {}
    if os.path.exists('data.json'):
        with open('data.json', 'r', encoding='utf-8') as f:
            try:
                db = {item['title']: item for item in json.load(f)}
            except: pass

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for site, url in TARGETS.items():
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            for a in soup.find_all('a', href=True):
                title = a.get_text().strip()
                if is_target_policy(title):
                    full_url = a['href'] if a['href'].startswith('http') else url.rsplit('/', 1)[0] + '/' + a['href']
                    
                    # 抓取详情并结构化
                    detail_resp = requests.get(full_url, headers=headers, timeout=15)
                    detail_resp.encoding = 'utf-8'
                    detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
                    
                    # 提取含金量高的段落
                    paragraphs = [p.get_text().strip() for p in detail_soup.find_all(['p', 'div']) 
                                 if len(p.get_text().strip()) > 10]
                    
                    new_content = parse_to_structured_markdown(paragraphs)
                    
                    if title in db:
                        # 合并新旧内容，去重并保持结构
                        db[title]['content'] = list(set(db[title]['content'].split('\n') + new_content.split('\n')))
                        db[title]['content'] = '\n'.join(db[title]['content'])
                        if full_url not in db[title]['urls']: db[title]['urls'].append(full_url)
                    else:
                        db[title] = {
                            "title": title,
                            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                            "source": site,
                            "urls": [full_url],
                            "content": new_content
                        }
        except Exception as e: print(f"{site} error: {e}")

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(list(db.values()), f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    run()
