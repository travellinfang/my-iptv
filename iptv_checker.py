import requests
import re
import time
import sys
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============== 配置区 ==============
SOURCES = [
    # ── 国内综合源 ──
    {
        "name": "CCSH/IPTV",
        "url": "https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live.m3u",
    },
    {
        "name": "CCSH/IPTV 精简版",
        "url": "https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/live_lite.m3u",
    },
    {
        "name": "YanG-1989/Gather",
        "url": "https://raw.githubusercontent.com/YanG-1989/Gather/refs/heads/main/IPTV.m3u",
    },
    {
        "name": "Meroser/IPTV",
        "url": "https://raw.githubusercontent.com/Meroser/IPTV/refs/heads/main/tv/IPTV.m3u",
    },
    {
        "name": "kimwang1978/collect-tv-txt",
        "url": "https://raw.githubusercontent.com/kimwang1978/collect-tv-txt/refs/heads/main/output/tv_multicast_all.txt",
    },
    {
        "name": "HerbertHe/iptv-resources",
        "url": "https://raw.githubusercontent.com/HerbertHe/iptv-resources/refs/heads/main/iptv.m3u",
    },
    {
        "name": "BurningC4/Chinese-IPTV",
        "url": "https://raw.githubusercontent.com/BurningC4/Chinese-IPTV/refs/heads/master/iptv-cntv.m3u",
    },
    {
        "name": "Free-TV/IPTV",
        "url": "https://raw.githubusercontent.com/Free-TV/IPTV/refs/heads/master/playlist.m3u8",
    },
    {
        "name": "Moexin/IPTV",
        "url": "https://raw.githubusercontent.com/Moexin/IPTV/refs/heads/main/live.m3u",
    },
    {
        "name": "KeAnthen/DragonIPTV",
        "url": "https://raw.githubusercontent.com/KeAnthen/DragonIPTV/refs/heads/main/tv/IPTV.m3u",
    },
    {
        "name": "qwerttvv/Beijing-IPTV",
        "url": "https://raw.githubusercontent.com/qwerttvv/Beijing-IPTV/refs/heads/main/bj-unicom-iptv.m3u",
    },
    # ── 戏曲/音乐/经典剧场 ──
    {
        "name": "自定义-戏曲音乐经典",
        "url": "https://raw.githubusercontent.com/travellinfang/my-iptv/main/extra_channels.m3u",
    },
]

OUTPUT_DIR = "output"
OUTPUT_M3U = os.path.join(OUTPUT_DIR, "live_available.m3u")
OUTPUT_TXT = os.path.join(OUTPUT_DIR, "live_available.txt")
LOG_FILE = os.path.join(OUTPUT_DIR, "check_log.txt")

TIMEOUT = 8
MAX_WORKERS = 20
RETRY = 2
TOP_N = 3

LOCAL_PROXIES = [
    "https://gh-proxy.com/",
    "https://ghfast.top/",
    "https://gh.llkk.cc/",
    "https://github.moeyy.xyz/",
]

# ====================================
# 分组归类规则
# ====================================
GROUP_RULES = [
    # ── 央视 ──
    (["CCTV-1", "CCTV-2", "CCTV-3", "CCTV-4", "CCTV-5",
      "CCTV-6", "CCTV-7", "CCTV-8", "CCTV-9", "CCTV-10",
      "CCTV-11", "CCTV-12", "CCTV-13", "CCTV-14", "CCTV-15",
      "CCTV-16", "CCTV-17", "CCTV-5+", "CCTV", "中央"], "央视"),

    # ── 卫视 ──
    (["卫视"], "卫视"),

    # ── 戏曲 ──
    (["戏曲", "梨园", "京剧", "越剧", "豫剧", "黄梅戏",
      "秦腔", "评剧", "昆曲", "粤剧", "川剧", "河北梆子",
      "评弹", "二人转", "相声", "曲艺", "大鼓"], "戏曲"),

    # ── 经典剧场 ──
    (["怀旧", "经典剧场", "风云剧场", "第一剧场",
      "重温经典", "CHC经典"], "经典剧场"),

    # ── 电影 ──
    (["电影", "影院", "CHC", "chc"], "电影"),

    # ── 体育 ──
    (["体育", "足球", "篮球", "ESPN", "espn", "NBA", "nba",
      "英超", "西甲", "德甲", "意甲", "法甲", "欧冠", "中超"], "体育"),

    # ── 新闻 ──
    (["新闻", "资讯", "NEWS", "news"], "新闻"),

    # ── 少儿 ──
    (["少儿", "卡通", "动画", "卡酷", "炫动",
      "金鹰", "优漫", "哈哈"], "少儿"),

    # ── 音乐 ──
    (["音乐", "Music", "music", "风云音乐", "MV"], "音乐"),

    # ── 纪录片 ──
    (["纪录", "纪录片", "documentary", "Documentary"], "纪录片"),

    # ── 综合 ──
    (["综合"], "综合"),

    # ── 生活 ──
    (["生活", "都市", "民生", "公共"], "生活"),

    # ── 财经 ──
    (["财经", "经济", "股市", "财商"], "财经"),

    # ── 教育 ──
    (["教育", "科教", "文化"], "教育"),

    # ── 购物 ──
    (["购物", "家有", "好享"], "购物"),

    # ── 高清 ──
    (["高清", "HD", "hd", "4K", "4k", "超清", "蓝光"], "高清"),

    # ── IPTV ──
    (["IPTV", "iptv", "组播", "运营商"], "IPTV"),

    # ── 直播平台 ──
    (["斗鱼", "虎牙", "B站", "bilibili", "抖音", "快手",
      "YY", "直播", "熊猫"], "直播平台"),
]

# 分组输出顺序
GROUP_ORDER = [
    "央视", "卫视", "戏曲", "经典剧场", "新闻",
    "体育", "电影", "少儿", "音乐", "纪录片", "财经",
    "教育", "生活", "综合", "高清", "购物", "IPTV",
    "直播平台", "其他",
]

IS_CI = os.getenv("GITHUB_ACTIONS") is not None


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    print(f"[{now()}] {msg}")


def normalize_group(name, original_group):
    """根据频道名和原始分组自动归类"""
    check_str = f"{name} {original_group}"
    for keywords, group_name in GROUP_RULES:
        for kw in keywords:
            if kw in check_str:
                return group_name
    return "其他"


def fetch_url(url):
    """下载文件（GitHub Actions 直连，本地走代理）"""
    if IS_CI:
        try:
            r = requests.get(url, timeout=25)
            if r.status_code == 200 and len(r.text) > 50:
                r.encoding = "utf-8"
                return r.text
        except Exception:
            pass
        return None
    else:
        for proxy in LOCAL_PROXIES:
            try:
                r = requests.get(proxy + url, timeout=15)
                if r.status_code == 200 and len(r.text) > 50:
                    r.encoding = "utf-8"
                    log(f"    通过 [{proxy}] 下载成功")
                    return r.text
            except Exception:
                continue
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and len(r.text) > 50:
                r.encoding = "utf-8"
                log(f"    通过 [直连] 下载成功")
                return r.text
        except Exception:
            pass
        return None


def parse_m3u(content):
    """解析 M3U 格式"""
    lines = content.strip().split("\n")
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            name_match = re.search(r',(.+)$', line)
            name = name_match.group(1).strip() if name_match else "未知频道"
            group_match = re.search(r'group-title="([^"]*)"', line)
            group = group_match.group(1) if group_match else "未分组"
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith("#"):
                    channels.append((name, group, line, url))
                    i += 2
                    continue
        i += 1
    return channels


def parse_txt(content):
    """解析 TXT 格式"""
    lines = content.strip().split("\n")
    channels = []
    current_group = "未分组"
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",", 1)
        if len(parts) != 2:
            continue
        name = parts[0].strip()
        value = parts[1].strip()
        if value in ("#genre#", "#genre"):
            current_group = name
            continue
        if value.startswith("http"):
            extinf = f'#EXTINF:-1 group-title="{current_group}",{name}'
            channels.append((name, current_group, extinf, value))
    return channels


def parse_source(content):
    """自动判断格式并解析"""
    if content.strip().startswith("#EXTM3U") or "#EXTINF" in content[:500]:
        return parse_m3u(content)
    else:
        return parse_txt(content)


def check_url_speed(url):
    """检测 URL 可用性和速度"""
    best_time = None
    for _ in range(RETRY):
        try:
            start = time.time()
            r = requests.get(url, timeout=TIMEOUT, stream=True)
            if r.status_code == 200:
                chunk = next(r.iter_content(1024), None)
                elapsed = (time.time() - start) * 1000
                if chunk and len(chunk) > 0:
                    if best_time is None or elapsed < best_time:
                        best_time = elapsed
                    return best_time
        except Exception:
            pass
        time.sleep(0.3)
    return None


def main():
    env = "GitHub Actions" if IS_CI else "本地"
    print("=" * 65)
    print("  IPTV 多源合并 & 自动检测工具")
    print(f"  数据源: {len(SOURCES)} 个仓库")
    print(f"  运行环境: {env}")
    print(f"  每频道保留: 最快 {TOP_N} 个源")
    print("=" * 65)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── 1. 拉取所有源 ──
    all_channels = []
    source_stats = []

    for source in SOURCES:
        name = source["name"]
        url = source["url"]
        log(f"拉取 [{name}] ...")

        content = fetch_url(url)
        if content:
            parsed = parse_source(content)
            log(f"  → 解析到 {len(parsed)} 个源")
            all_channels.extend(parsed)
            source_stats.append((name, url, len(parsed), "✓"))
        else:
            log(f"  → 下载失败，跳过")
            source_stats.append((name, url, 0, "✗ 失败"))

    total_raw = len(all_channels)
    log(f"\n所有源合计: {total_raw} 个")

    if total_raw == 0:
        log("未解析到任何频道")
        sys.exit(1)

    # ── 2. 自动归类分组 ──
    log("正在自动归类分组...")
    regrouped = []
    for name, old_group, extinf, url in all_channels:
        new_group = normalize_group(name, old_group)
        new_extinf = re.sub(
            r'group-title="[^"]*"',
            f'group-title="{new_group}"',
            extinf
        )
        if 'group-title=' not in extinf:
            new_extinf = extinf.replace(
                f',{name}',
                f' group-title="{new_group}",{name}'
            )
        regrouped.append((name, new_group, new_extinf, url))

    group_count = {}
    for name, group, *_ in regrouped:
        group_count[group] = group_count.get(group, 0) + 1
    log("分组统计:")
    for g in GROUP_ORDER:
        if g in group_count:
            log(f"  {g}: {group_count[g]} 个源")
    if "其他" in group_count:
        log(f"  其他: {group_count['其他']} 个源")

    # ── 3. URL 去重 ──
    seen_urls = {}
    unique_channels = []
    for item in regrouped:
        url = item[3]
        if url not in seen_urls:
            seen_urls[url] = item
            unique_channels.append(item)
    dedup_count = total_raw - len(unique_channels)
    log(f"\nURL 去重: 去除 {dedup_count} 个重复，剩余 {len(unique_channels)} 个待检测")

    # ── 4. 多线程检测 ──
    total_urls = len(unique_channels)
    log(f"开始检测 | 线程: {MAX_WORKERS} | 超时: {TIMEOUT}s\n")

    results = []
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {}
        for name, group, extinf, url in unique_channels:
            future = executor.submit(check_url_speed, url)
            future_map[future] = (name, group, extinf, url)

        for future in as_completed(future_map):
            name, group, extinf, url = future_map[future]
            speed = future.result()
            done += 1
            status = f"✓ {speed:>6.0f}ms" if speed else "✗ 失效  "
            print(f"  [{done:>4}/{total_urls}] {status}  {name}  {url[:50]}")
            results.append((name, group, extinf, url, speed))

    # ── 5. 排序 + 每频道保留最快 TOP_N 个 ──
    available = [r for r in results if r[4] is not None]
    failed = [r for r in results if r[4] is None]

    available.sort(key=lambda x: (x[0], x[4]))

    best = []
    seen_names = {}
    for item in available:
        name = item[0]
        if name not in seen_names:
            seen_names[name] = 0
        if seen_names[name] < TOP_N:
            best.append(item)
            seen_names[name] += 1
    available = best

    def sort_key(item):
        group = item[1]
        name = item[0]
        speed = item[4]
        try:
            group_idx = GROUP_ORDER.index(group)
        except ValueError:
            group_idx = len(GROUP_ORDER)
        return (group_idx, name, speed)

    available.sort(key=sort_key)
    unique_names = set(n for n, *_ in available)

    # ── 6. 统计 ──
    print(f"\n{'=' * 65}")
    print(f"  检测完成！")
    print(f"{'=' * 65}")
    print(f"  {'数据源':35s} {'状态':8s} {'源数':>6s}")
    print(f"  {'─' * 55}")
    for sname, surl, scount, sstatus in source_stats:
        print(f"  {sname:35s} {sstatus:8s} {scount:>5d}")
    print(f"  {'─' * 55}")
    print(f"  原始合计:     {total_raw}")
    print(f"  URL 去重后:   {total_urls}")
    print(f"  可用源:       {len(available)}（每频道 {TOP_N} 个）")
    print(f"  失效源:       {len(failed)}")
    print(f"  去重后频道:   {len(unique_names)}")
    print(f"  有效率:       {len(available)}/{total_urls} = "
          f"{len(available)/max(total_urls,1)*100:.1f}%")

    print(f"\n  分组频道数:")
    final_groups = {}
    for name, group, *_ in available:
        final_groups[group] = final_groups.get(group, 0) + 1
    for g in GROUP_ORDER:
        if g in final_groups:
            print(f"    {g:12s}  {final_groups[g]:>3d} 个频道")
    print(f"{'=' * 65}")

    # ── 7. 输出文件 ──
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name, group, extinf, url, speed in available:
            f.write(f"{extinf}\n")
            f.write(f"{url}\n")
    log(f"M3U: {OUTPUT_M3U}")

    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        current_group = ""
        for name, group, extinf, url, speed in available:
            if group != current_group:
                f.write(f"\n{group},#genre#\n")
                current_group = group
            f.write(f"{name},{url}\n")
    log(f"TXT: {OUTPUT_TXT}")

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"检测时间: {datetime.now()}\n")
        f.write(f"运行环境: {env}\n")
        f.write(f"每频道保留: {TOP_N} 个源\n\n")
        f.write("── 数据源 ──\n")
        for sname, surl, scount, sstatus in source_stats:
            f.write(f"  {sstatus} {sname} ({scount} 个源)\n")
            f.write(f"     {surl}\n")
        f.write(f"\n── 分组统计 ──\n")
        for g in GROUP_ORDER:
            if g in final_groups:
                f.write(f"  {g}: {final_groups[g]} 个频道\n")
        f.write(f"\n── 统计 ──\n")
        f.write(f"  原始: {total_raw}  去重后: {total_urls}  "
                f"可用: {len(available)}  失效: {len(failed)}  "
                f"频道: {len(unique_names)}\n\n")
        f.write("── 可用源（按分组排序）──\n")
        for name, group, extinf, url, speed in available:
            f.write(f"[{group}] [{speed:>6.0f}ms] {name} | {url}\n")
        f.write("\n── 失效源 ──\n")
        for name, group, extinf, url, speed in failed:
            f.write(f"{name} | {url}\n")
    log(f"日志: {LOG_FILE}")

    log("全部完成！")


if __name__ == "__main__":
    main()
