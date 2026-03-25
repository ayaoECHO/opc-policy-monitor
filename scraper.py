import requests
from bs4 import BeautifulSoup
import json
import datetime
import os
import re

# 目标发布源
TARGETS = {
    "成都市经信局": "https://cdjx.chengdu.gov.cn/cdjx/c115217/jsj_list.shtml",
    "成都高新区": "https://www.cdht.gov.cn/cdht/c139391/gk_list.shtml",
    "四川日报": "https://www.scdaily.cn/",
    "红星新闻": "https://www.cdsb.com/"
}

# 严格过滤关键词
CORE_DOMAINS = ["一人公司", "OPC", "人工智能", "AI", "智能体", "大模型"]
ACTION_WORDS = ["补贴", "政策", "措施", "奖励", "资助", "扶持", "申报", "征求意见"]
EXCLUDE_WORDS = ["个体工商户", "个人独资", "农业", "养殖"]

def is_target_policy(title):
    title_upper = title.upper()
    has_domain = any(dom in title_upper for dom in CORE_DOMAINS)
    has_action = any(act in title_upper for act in ACTION_WORDS)
    is_not_excluded = not any(ex in title_upper for ex in EXCLUDE_WORDS)
    return has_domain and has_action and is_not_excluded

def parse_to_markdown(paragraphs):
    """简单格式化，确保干货被识别"""
    content = ""
    for p in paragraphs:
        if re.search(r'第[一二三四五六七八九十\d]+条|万元|%|补贴|支持', p):
            content += f"- **核心干货**：{p}\n"
        else:
            content += f"{p}\n"
    return content

def run():
    db = {}
    # 1. 加载旧数据
    if os.path.exists('data.json'):
        try:
            with open('data.json', 'r', encoding='utf-8') as f:
                items = json.load(f)
                db = {item['title']: item for item in items}
        except: pass

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for site, base_url in TARGETS.items():
        print(f"正在扫描/回溯站点: {site}")
        
        for page in range(1, 6):  
            if page == 1:
                current_url = base_url
            else:
                current_url = base_url.replace(".shtml", f"_{page-1}.shtml")
            
            try:
                resp = requests.get(current_url, headers=headers, timeout=20)
                resp.encoding = 'utf-8'
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                links = soup.find_all('a', href=True)
                found_new_on_page = False
                
                for a in links:
                    title = a.get_text().strip()
                    if is_target_policy(title) and title not in db:
                        href = a['href']
                        full_url = href if href.startswith('http') else base_url.rsplit('/', 1)[0] + '/' + href
                        
                        # 抓取正文
                        detail_resp = requests.get(full_url, headers=headers, timeout=15)
                        detail_resp.encoding = 'utf-8'
                        detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
                        paragraphs = [p.get_text().strip() for p in detail_soup.find_all(['p', 'div']) if len(p.get_text().strip()) > 10]
                        
                        db[title] = {
                            "title": title,
                            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                            "source": site,
                            "urls": [full_url],
                            "content": parse_to_markdown(paragraphs)
                        }
                        found_new_on_page = True
                
                print(f"  - 第 {page} 页处理完毕")
                if not found_new_on_page and page > 1:
                    break
                    
            except Exception as e:
                print(f"  - {site} 第 {page} 页异常: {e}")
                break

    # 2. 核心改进：在保存前对所有数据进行一次深度清理
    processed_data = []
    for item in db.values():
        # 清理所有的 <br> 标签，替换为 Markdown 换行符
        if "content" in item:
            item["content"] = item["content"].replace("<br>", "  \n")
        processed_data.append(item)

    # 3. 按日期倒序排列并写入
    final_data = sorted(processed_data, key=lambda x: x.get('date', ''), reverse=True)
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)
    print("✨ 数据抓取并自动清理完成！")

if __name__ == "__main__":
    run()
