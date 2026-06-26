import requests
import re
import time
import sys
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============== 配置区 ==============
SOURCES = [
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
    # 继续添加 ↓
    # {
    #     "name": "备注名",
    #     "url": "https://raw.githubusercontent.com/xxx/xxx/refs/heads/main/xxx.m3u",
    # },
]

OUTPUT_DIR = "output"
OUTPUT_M3U = os.path.join(OUTPUT_DIR, "live_available.m3u")
OUTPUT_TXT = os.path.join(OUTPUT_DIR, "live_available.txt")
LOG_FILE = os.path.join(OUTPUT_DIR, "check_log.txt")

TIMEOUT = 6
MAX_WORKERS = 25
RETRY = 2
TOP_N = 1
GITHUB_PROXIES = [
    "",
    "https://gh-proxy.com/",
    "https://mirror.ghproxy.com/",
    "https://ghfast.top/",
]
# ====================================


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    print(f"[{now()}] {msg}")


def fetch_url(url):
    for proxy in GITHUB_PROXIES:
        try:
            r = requests.get(proxy + url, timeout=25)
            if r.status_code == 200 and len(r.text) > 50:
                r.encoding = "utf-8"
                return r.text
        except Exception:
            continue
    return None


def parse_m3u(content):
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
    if content.strip().startswith("#EXTM3U") or "#EXTINF" in content[:500]:
        return parse_m3u(content)
    else:
        return parse_txt(content)


def check_url_speed(url):
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
    print("=" * 65)
    print("  IPTV 多源合并 & 自动检测工具")
    print(f"  数据源: {len(SOURCES)} 个仓库")
    print(f"  运行环境: {'GitHub Actions' if os.getenv('GITHUB_ACTIONS') else '本地'}")
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

    # ── 2. URL 去重 ──
    seen_urls = {}
    unique_channels = []
    for item in all_channels:
        url = item[3]
        if url not in seen_urls:
            seen_urls[url] = item
            unique_channels.append(item)
    dedup_count = total_raw - len(unique_channels)
    log(f"URL 去重: 去除 {dedup_count} 个重复，剩余 {len(unique_channels)} 个待检测")

    # ── 3. 多线程检测 ──
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

    # ── 4. 排序 + 频道去重 ──
    available = [r for r in results if r[4] is not None]
    failed = [r for r in results if r[4] is None]

    available.sort(key=lambda x: (x[0], x[4]))

    if TOP_N > 0:
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

    available.sort(key=lambda x: (x[1], x[0], x[4]))

    unique_names = set(n for n, *_ in available)

    # ── 5. 统计 ──
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
    print(f"  可用:         {len(available)}")
    print(f"  失效:         {len(failed)}")
    print(f"  去重后频道:   {len(unique_names)}")
    print(f"  有效率:       {len(available)}/{total_urls} = "
          f"{len(available)/max(total_urls,1)*100:.1f}%")
    print(f"  每频道保留:   最快 {TOP_N} 个源")
    print(f"{'=' * 65}")

    # ── 6. 输出文件 ──
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
        f.write(f"检测时间: {datetime.now()}\n\n")
        f.write("── 数据源 ──\n")
        for sname, surl, scount, sstatus in source_stats:
            f.write(f"  {sstatus} {sname} ({scount} 个源)\n")
            f.write(f"     {surl}\n")
        f.write(f"\n── 统计 ──\n")
        f.write(f"  原始: {total_raw}  去重后: {total_urls}  "
                f"可用: {len(available)}  失效: {len(failed)}  "
                f"频道: {len(unique_names)}\n\n")
        f.write("── 可用源（按速度排序）──\n")
        for name, group, extinf, url, speed in available:
            f.write(f"[{speed:>6.0f}ms] {name} | {url}\n")
        f.write("\n── 失效源 ──\n")
        for name, group, extinf, url, speed in failed:
            f.write(f"{name} | {url}\n")
    log(f"日志: {LOG_FILE}")

    log("全部完成！")


if __name__ == "__main__":
    main()
