import requests
from bs4 import BeautifulSoup
import json
import datetime
import os
import re

# 1. 结构化目标发布源：按省份组织
TARGET_CONFIG = {
    "四川省": {
        "成都市": "https://cdjx.chengdu.gov.cn/cdjx/c115217/jsj_list.shtml",
        "天府新区": "https://www.cdtianfu.gov.cn/tfxq/c128038/gk_list.shtml",
        "高新区": "https://www.cdht.gov.cn/cdht/c139391/gk_list.shtml"
    },
    "上海市": {
        "上海市": "https://www.shanghai.gov.cn/nw4411/index.html" # 示例地址，需根据实际规律调整
    },
    "广东省": {
        "深圳市": "https://www.sz.gov.cn/cn/xxgk/zfxxgj/tzgg/index.html" # 示例地址
    }
}

# 严格过滤关键词
CORE_DOMAINS = ["一人公司", "OPC", "人工智能", "AI", "智能体", "大模型"]
ACTION_WORDS = ["补贴", "政策", "措施", "奖励", "资助", "扶持", "申报", "征求意见"]
EXCLUDE_WORDS = ["个体工商户", "农业", "养殖", "医疗器械"]

def is_target_policy(title):
    title_upper = title.upper()
    has_domain = any(dom in title_upper for dom in CORE_DOMAINS)
    has_action = any(act in title_upper for act in ACTION_WORDS)
    is_not_excluded = not any(ex in title_upper for ex in EXCLUDE_WORDS)
    return has_domain and has_action and is_not_excluded

def parse_to_markdown(paragraphs):
    content = ""
    for p in paragraphs:
        if re.search(r'第[一二三四五六七八九十\d]+条|万元|%|补贴|支持', p):
            content += f"- **核心干货**：{p}\n"
        else:
            content += f"{p}\n"
    return content

def run():
    db = {}
    # 加载旧数据，保持增量更新
    if os.path.exists('data.json'):
        try:
            with open('data.json', 'r', encoding='utf-8') as f:
                items = json.load(f)
                # 以标题作为唯一键，防止重复抓取
                db = {item['title']: item for item in items}
        except: pass

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    # 遍历省份和城市
    for province, cities in TARGET_CONFIG.items():
        for city, base_url in cities.items():
            print(f"正在扫描: {province} - {city}")
            
            # 翻页逻辑（以 3 页为例，确保覆盖近期动态）
            for page in range(1, 4):
                if page == 1:
                    current_url = base_url
                else:
                    # 注意：不同政府网站翻页规律不同，此处为通用假设，建议针对重点网站单独写适配器
                    current_url = base_url.replace(".shtml", f"_{page-1}.shtml")
                
                try:
                    resp = requests.get(current_url, headers=headers, timeout=20)
                    resp.encoding = 'utf-8'
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    
                    links = soup.find_all('a', href=True)
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
                            
                            # 存入数据库，增加地域标签
                            db[title] = {
                                "title": title,
                                "province": province,
                                "city": city,
                                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                                "source": f"{province}{city}官方发布",
                                "urls": [full_url],
                                "content": parse_to_markdown(paragraphs)
                            }
                except Exception as e:
                    print(f"  - 访问异常 {province}{city}: {e}")
                    break

    # 核心清理与排序逻辑
    processed_data = []
    for item in db.values():
        # 1. 自动清理内容中的 <br> 标签
        if "content" in item:
            item["content"] = item["content"].replace("<br>", "  \n")
        processed_data.append(item)

    # 2. 按日期倒序排列（3月25 > 3月24 > 2月）
    final_data = sorted(processed_data, key=lambda x: x.get('date', ''), reverse=True)

    # 写入文件
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)
    print(f"✨ 全国化政策库更新完成，当前共收录 {len(final_data)} 条政策。")

if __name__ == "__main__":
    run()
