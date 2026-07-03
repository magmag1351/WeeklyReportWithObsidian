import os
import json
import re
import argparse
import platform
from datetime import datetime, timedelta

def load_config(config_path="config.json"):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def resolve_paths(config):
    """OSを判定し、configから適切なパスを解決して返す。
    macOSの場合は `_mac` サフィックスのキーを優先し、
    またパス先頭の `~` をユーザーのホームディレクトリに展開する。
    """
    system = platform.system()
    
    if system == "Darwin": # macOS
        daily_note_path = config.get("daily_note_path_mac") or config.get("daily_note_path")
        output_path = config.get("output_path_mac") or config.get("output_path")
    else: # Windowsなど
        daily_note_path = config.get("daily_note_path")
        output_path = config.get("output_path")
        
    if daily_note_path:
        daily_note_path = os.path.expanduser(daily_note_path)
    if output_path:
        output_path = os.path.expanduser(output_path)
        
    return daily_note_path, output_path

def get_date_input(prompt):
    while True:
        val = input(prompt).strip()
        if not val:
            print("入力が空です。再度入力してください。")
            continue
        # ハイフンを除去して8桁の数値にする
        val_clean = val.replace("-", "")
        if len(val_clean) == 8 and val_clean.isdigit():
            try:
                dt = datetime.strptime(val_clean, "%Y%m%d")
                return dt
            except ValueError:
                pass
        print("正しい日付形式（例: 20260629 または 2026-06-29）で入力してください。")

def parse_time_field(time_str):
    """[time:: ...] の値をパースして『分』単位の整数に変換する"""
    if not time_str:
        return 0
    time_str = time_str.strip().lower()
    
    # 複合パターンのチェック (例: 1h30m, 1時間30分)
    compound_match = re.match(r'^(\d+(?:\.\d+)?)\s*(?:h|hour|時間|hr)\s*(\d+(?:\.\d+)?)\s*(?:m|min|minute|分)?$', time_str)
    if compound_match:
        hours = float(compound_match.group(1))
        minutes = float(compound_match.group(2))
        return int(hours * 60 + minutes)
        
    # 単一単位のチェック
    # 時間単位
    hour_match = re.match(r'^(\d+(?:\.\d+)?)\s*(?:h|hour|時間|hr)$', time_str)
    if hour_match:
        return int(float(hour_match.group(1)) * 60)
        
    # 分単位
    minute_match = re.match(r'^(\d+(?:\.\d+)?)\s*(?:m|min|minute|分)$', time_str)
    if minute_match:
        return int(float(minute_match.group(1)))
        
    # 単位なしの数値
    try:
        val = float(time_str)
        # 小数点があれば時間、整数なら分とみなす
        if '.' in time_str:
            return int(val * 60)
        else:
            return int(val)
    except ValueError:
        return 0

def format_minutes(minutes):
    """分を『◯時間◯分』や『◯分』といった読みやすい文字列にフォーマットする"""
    if not minutes or minutes <= 0:
        return ""
    h = int(minutes // 60)
    m = int(minutes % 60)
    if h > 0 and m > 0:
        return f"{h}時間{m}分"
    elif h > 0:
        return f"{h}時間"
    else:
        return f"{m}分"

def parse_daily_notes(daily_note_path, start_date, end_date):
    parsed_tasks = []
    
    # チェックボックス行の判定 (例: - [ ] タスク名, - [x] タスク名, - [/] タスク名)
    task_pattern = re.compile(r"^\s*-\s*\[([ xX/])\]\s*(.*)$")
    # 理由行の判定 (後方互換性・手書きの補足メモ用)
    reason_pattern = re.compile(r"^\s*->\s*(.*)$")

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        filepath = os.path.join(daily_note_path, f"{date_str}.md")
        
        if os.path.exists(filepath):
            last_task = None
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.rstrip("\r\n")
                    
                    # 理由行チェック
                    reason_match = reason_pattern.match(line_str)
                    if reason_match:
                        # 未達成タスクのみ理由を記録
                        if last_task and not last_task["is_completed"]:
                            reason_content = reason_match.group(1).strip()
                            if reason_content and reason_content not in last_task["reasons"]:
                                last_task["reasons"].append(reason_content)
                    else:
                        # チェックボックス行チェック
                        task_match = task_pattern.match(line_str)
                        if task_match:
                            status = task_match.group(1)
                            raw_content = task_match.group(2).strip()
                            
                            is_completed = status in ("x", "X")
                            
                            # カテゴリのパース [category:: ...]
                            category = "unclassified"
                            category_match = re.search(r"\[category::\s*([^\]]+)\]", raw_content)
                            if category_match:
                                cat_val = category_match.group(1).strip()
                                if cat_val in ("研", "research"):
                                    category = "research"
                                elif cat_val in ("私", "private"):
                                    category = "private"
                                    
                            # メモのパース [memo:: ...]
                            memo_content = None
                            memo_match = re.search(r"\[memo::\s*([^\]]+)\]", raw_content)
                            if memo_match:
                                memo_content = memo_match.group(1).strip()
                                
                            # 消費時間のパース [time:: ...]
                            time_value = 0
                            time_match = re.search(r"\[time::\s*([^\]]+)\]", raw_content)
                            if time_match:
                                time_value = parse_time_field(time_match.group(1))

                            # Dataview のインラインフィールド ([key:: value]) を除去した純粋なタスク名を取得
                            content = re.sub(r"\[[^\]]+::[^\]]+\]", "", raw_content).strip()
                            
                            if content: # 空行は無視
                                last_task = {
                                    "is_completed": is_completed,
                                    "category": category,
                                    "content": content,
                                    "date": date_str,
                                    "reasons": [],
                                    "time": time_value
                                }
                                if memo_content:
                                    last_task["reasons"].append(memo_content)
                                parsed_tasks.append(last_task)
                                
        current_date += timedelta(days=1)
        
    return parsed_tasks

def merge_tasks(parsed_tasks):
    # 重複マージ処理用の辞書
    # キー: (category, content)
    keys = []
    merged = {}
    
    for t in parsed_tasks:
        key = (t["category"], t["content"])
        if key not in merged:
            keys.append(key)
            merged[key] = {
                "dates": [],
                "reasons": [],
                "total_time": 0,
                "is_completed": False
            }
        # 期間中に一度でも完了（is_completed が True）していれば完了とする
        if t["is_completed"]:
            merged[key]["is_completed"] = True
            
        # 重複日付を排除して追加
        if t["date"] not in merged[key]["dates"]:
            merged[key]["dates"].append(t["date"])
        # 理由を追加 (重複排除)
        for r in t["reasons"]:
            if r not in merged[key]["reasons"]:
                merged[key]["reasons"].append(r)
        # 時間を加算
        merged[key]["total_time"] += t.get("time", 0)
                
    # 出力用の構造に整理
    tasks = {
        "completed": {
            "research": [],
            "private": [],
            "unclassified": []
        },
        "uncompleted": {
            "research": [],
            "private": [],
            "unclassified": []
        }
    }
    
    for key in keys:
        category, content = key
        m_task = merged[key]
        
        status_key = "completed" if m_task["is_completed"] else "uncompleted"
        
        # 日付は昇順でソート
        sorted_dates = sorted(m_task["dates"])
        
        tasks[status_key][category].append({
            "content": content,
            "dates": sorted_dates,
            "reasons": m_task["reasons"],
            "total_time": m_task["total_time"]
        })
        
    return tasks

def generate_summary_markdown(tasks, start_date, end_date):
    start_str = start_date.strftime("%Y/%m/%d")
    end_str = end_date.strftime("%Y/%m/%d")
    
    lines = []
    lines.append(f"# 対象期間: {start_str} 〜 {end_str}\n")
    
    def format_task_line(t):
        dates_str = ", ".join(t["dates"])
        line = f"- {t['content']} ({dates_str})"
        
        # 時間があれば出力
        if t.get("total_time", 0) > 0:
            time_str = format_minutes(t["total_time"])
            if time_str:
                line += f" (時間：{time_str})"
                
        if t["reasons"]:
            reasons_str = "、".join(t["reasons"])
            line += f" (reason：{reasons_str})" if "reason" in line else f" (理由：{reasons_str})"
        return line

    def render_category_section(title, task_list):
        lines.append(f"### {title}")
        if task_list:
            for t in task_list:
                lines.append(format_task_line(t))
        else:
            lines.append("- なし")
        lines.append("")

    # 達成セクション
    lines.append("## 達成")
    render_category_section("研究内容", tasks["completed"]["research"])
    render_category_section("私用内容", tasks["completed"]["private"])
    render_category_section("未分類", tasks["completed"]["unclassified"])
    
    # 未達成セクション
    lines.append("## 未達成")
    render_category_section("研究内容", tasks["uncompleted"]["research"])
    render_category_section("私用内容", tasks["uncompleted"]["private"])
    render_category_section("未分類", tasks["uncompleted"]["unclassified"])
    
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="週報サマリー作成プログラム")
    parser.add_argument("--this-week", action="store_true", help="今週の月曜日から金曜日までを対象にする")
    args = parser.parse_args()

    try:
        config = load_config()
    except Exception as e:
        print(f"設定ファイルの読み込みに失敗しました: {e}")
        return

    daily_note_path, output_path = resolve_paths(config)
    if not daily_note_path:
        daily_note_path = "./test_resource"
    if not output_path:
        output_path = "./output"
    
    print("--- 週報サマリー作成プログラム ---")
    
    if args.this_week:
        today = datetime.now()
        # 今週の月曜日を求める (時刻は 00:00:00)
        start_date = today - timedelta(days=today.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        # 月曜日 + 4日 = 金曜日
        end_date = start_date + timedelta(days=4)
        print(f"オプション指定: 今週の月曜日から金曜日を対象にします。")
        print(f"対象期間: {start_date.strftime('%Y-%m-%d')} 〜 {end_date.strftime('%Y-%m-%d')}")
    else:
        start_date = get_date_input("開始日付を入力してください (YYYYMMDD): ")
        end_date = get_date_input("終了日付を入力してください (YYYYMMDD): ")
        
    if start_date > end_date:
        print("エラー: 開始日付は終了日付以前である必要があります。")
        return
        
    parsed_tasks = parse_daily_notes(daily_note_path, start_date, end_date)
    tasks = merge_tasks(parsed_tasks)
    summary_content = generate_summary_markdown(tasks, start_date, end_date)
    
    # 出力ファイルパスの決定
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")
    
    if os.path.isdir(output_path):
        out_file = os.path.join(output_path, f"summary_{start_str}_{end_str}.md")
    elif output_path.endswith(".md") or output_path.endswith(".txt"):
        out_file = output_path
        parent_dir = os.path.dirname(out_file)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
    else:
        os.makedirs(output_path, exist_ok=True)
        out_file = os.path.join(output_path, f"summary_{start_str}_{end_str}.md")
        
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(summary_content)
        print(f"\nサマリーを出力しました: {out_file}")
    except Exception as e:
        print(f"サマリーファイルの出力に失敗しました: {e}")

if __name__ == "__main__":
    main()
