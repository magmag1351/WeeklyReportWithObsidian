import os
import json
import re
import argparse
from datetime import datetime, timedelta

def load_config(config_path="config.json"):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

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

def parse_daily_notes(daily_note_path, start_date, end_date):
    parsed_tasks = []
    
    # 箇条書き行の判定 (インデント付きのハイフンリストも考慮)
    list_pattern = re.compile(r"^\s*-\s*(.*)$")
    # 理由行の判定
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
                            if reason_content:
                                last_task["reasons"].append(reason_content)
                    else:
                        # リストアイテムチェック
                        list_match = list_pattern.match(line_str)
                        if list_match:
                            content = list_match.group(1).strip()
                            
                            # 完了マーカーのチェック
                            is_completed = False
                            if content.startswith("~~"):
                                is_completed = True
                                content = content[2:].strip()
                                
                            # カテゴリのチェック
                            category = "unclassified"
                            if content.startswith("【研】"):
                                category = "research"
                                content = content[3:].strip()
                            elif content.startswith("【私】"):
                                category = "private"
                                content = content[3:].strip()
                                
                            # 末尾の~~を除去
                            content = content.rstrip("~").strip()
                            
                            if content: # 空行は無視
                                last_task = {
                                    "is_completed": is_completed,
                                    "category": category,
                                    "content": content,
                                    "date": date_str,
                                    "reasons": []
                                }
                                parsed_tasks.append(last_task)
                                
        current_date += timedelta(days=1)
        
    return parsed_tasks

def merge_tasks(parsed_tasks):
    # 重複マージ処理用の辞書
    # キー: (is_completed, category, content)
    keys = []
    merged = {}
    
    for t in parsed_tasks:
        key = (t["is_completed"], t["category"], t["content"])
        if key not in merged:
            keys.append(key)
            merged[key] = {
                "dates": [],
                "reasons": []
            }
        # 重複日付を排除して追加
        if t["date"] not in merged[key]["dates"]:
            merged[key]["dates"].append(t["date"])
        # 理由を追加 (重複排除)
        for r in t["reasons"]:
            if r not in merged[key]["reasons"]:
                merged[key]["reasons"].append(r)
                
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
    
    # 期間内に達成されたタスクの集合を作成 (カテゴリと内容のペア)
    completed_set = set(
        (category, content) for (is_completed, category, content) in keys if is_completed
    )
    
    for key in keys:
        is_completed, category, content = key
        
        # 期間内に達成済みのタスクが未達成リストにもある場合は、未達成側では無視する
        if not is_completed and (category, content) in completed_set:
            continue
            
        status_key = "completed" if is_completed else "uncompleted"
        
        # 日付は昇順でソート
        sorted_dates = sorted(merged[key]["dates"])
        
        tasks[status_key][category].append({
            "content": content,
            "dates": sorted_dates,
            "reasons": merged[key]["reasons"]
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
        if t["reasons"]:
            reasons_str = "、".join(t["reasons"])
            line += f" (理由：{reasons_str})"
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

    daily_note_path = config.get("daily_note_path", "./test_resource")
    output_path = config.get("output_path", "./output")
    
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
