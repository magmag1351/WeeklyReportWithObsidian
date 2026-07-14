import os
import json
import re
import argparse
import platform
from datetime import datetime

def load_config(config_path="config.json"):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def resolve_paths(config):
    """OSを判定し、configから適切なパスを解決して返す。"""
    system = platform.system()
    
    if system == "Darwin": # macOS
        daily_note_path = config.get("daily_note_path_mac") or config.get("daily_note_path")
        output_path = config.get("output_path_mac") or config.get("output_path")
        future_tasks_path = config.get("future_tasks_path_mac") or config.get("future_tasks_path")
    else: # Windowsなど
        daily_note_path = config.get("daily_note_path")
        output_path = config.get("output_path")
        future_tasks_path = config.get("future_tasks_path")
        
    if daily_note_path:
        daily_note_path = os.path.expanduser(daily_note_path)
    if output_path:
        output_path = os.path.expanduser(output_path)
    if future_tasks_path:
        future_tasks_path = os.path.expanduser(future_tasks_path)
        
    return daily_note_path, output_path, future_tasks_path

def parse_date_input(date_str):
    """YYYYMMDD または YYYY-MM-DD 形式の日付文字列を YYYY-MM-DD 形式に標準化して返す。無効な場合は False"""
    if not date_str.strip():
        return None
    date_clean = date_str.replace("-", "").strip()
    if len(date_clean) == 8 and date_clean.isdigit():
        try:
            dt = datetime.strptime(date_clean, "%Y%m%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return False

def clean_task_content(task_line):
    """タスクの行からチェックボックス記号やDataviewのインラインフィールドを除去し、純粋なタスク名を取得する"""
    match = re.match(r"^\s*-\s*(?:\[[ xX/]\])?\s*(.*)$", task_line)
    if not match:
        content_cleaned = re.sub(r"\[[^\]]+::[^\]]+\]", "", task_line)
        return content_cleaned.strip()
    
    content = match.group(1).strip()
    content_cleaned = re.sub(r"\[[^\]]+::[^\]]+\]", "", content)
    return content_cleaned.strip()

def add_future_task(future_tasks_path, task_content, date_str, category, priority):
    """今後の予定を追加する"""
    parts = [f"- [ ] {task_content}"]
    if date_str:
        parts.append(f"[scheduled:: {date_str}]")
    if category:
        parts.append(f"[category:: {category}]")
    if priority:
        parts.append(f"[priority:: {priority}]")
    
    line = " ".join(parts) + "\n"
    
    if os.path.dirname(future_tasks_path):
        os.makedirs(os.path.dirname(future_tasks_path), exist_ok=True)
    
    with open(future_tasks_path, "a", encoding="utf-8") as f:
        f.write(line)
        
    print(f"予定を追加しました: {line.strip()}")

def list_and_copy_tasks(future_tasks_path, daily_note_path):
    """今後の予定を一覧表示し、選択されたタスクを本日のデイリーノートに転記する"""
    if not os.path.exists(future_tasks_path):
        print(f"今後の予定ファイルが見つかりません: {future_tasks_path}")
        return

    # 未完了のタスクを抽出
    tasks = []
    with open(future_tasks_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line_clean = line.strip()
            # 未完了タスク行を判定
            match = re.match(r"^\s*-\s*\[ \]\s*(.*)$", line_clean)
            if match:
                tasks.append({
                    "line_no": i,
                    "raw_line": line,
                    "content": match.group(1).strip()
                })

    if not tasks:
        print("未完了の今後の予定はありません。")
        return

    print("\n--- 今後の予定一覧 ---")
    for idx, task in enumerate(tasks):
        print(f"[{idx + 1}] {task['content']}")
    print("----------------------")

    # ユーザーに入力を求める
    try:
        selection = input("\n転記する予定の番号を指定してください（カンマ区切りで複数指定可、例: 1, 3。キャンセルは 'q'）: ").strip()
        if selection.lower() == 'q' or not selection:
            print("キャンセルしました。")
            return
        
        # 入力を数値リストに変換
        selected_indices = [int(x.strip()) - 1 for x in selection.split(",") if x.strip().isdigit()]
    except Exception as e:
        print(f"入力が正しくありません: {e}")
        return

    # 有効なインデックスのみフィルタリング
    selected_tasks = []
    for idx in selected_indices:
        if 0 <= idx < len(tasks):
            selected_tasks.append(tasks[idx])
        else:
            print(f"無効な番号はスキップします: {idx + 1}")

    if not selected_tasks:
        print("選択されたタスクはありません。")
        return

    # 本日のデイリーノートへの転記
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_filepath = os.path.join(daily_note_path, f"{today_str}.md")
    
    # デイリーノートの準備
    file_exists = os.path.exists(today_filepath)
    lines = []
    existing_task_names = set()

    if file_exists:
        with open(today_filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            line_clean = line.strip()
            if line_clean.startswith("-") and not line_clean.startswith("->"):
                cleaned = clean_task_content(line_clean)
                if cleaned:
                    existing_task_names.add(cleaned)

    # 転記用タスクの作成（scheduledプロパティを除去）
    tasks_to_insert = []
    for task in selected_tasks:
        raw_content = task["content"]
        # scheduled プロパティを除去
        content_for_today = re.sub(r"\[scheduled::\s*[^\]]+\]", "", raw_content)
        content_for_today = re.sub(r"\s+", " ", content_for_today).strip()
        
        # 重複チェック
        cleaned_name = clean_task_content(content_for_today)
        if cleaned_name not in existing_task_names:
            tasks_to_insert.append(f"- [ ] {content_for_today}")
        else:
            print(f"すでに本日のノートに存在するためスキップ: {cleaned_name}")

    if not tasks_to_insert:
        print("転記する新しいタスクはありませんでした。")
        return

    # 挿入処理
    heading_pattern = re.compile(r"^#+\s+(本日の予定|本日行うこと)\s*$")
    heading_idx = -1
    for i, line in enumerate(lines):
        if heading_pattern.match(line.strip()):
            heading_idx = i
            break

    if heading_idx != -1:
        insert_index = heading_idx + 1
        insert_lines = [t + "\n" for t in tasks_to_insert]
        lines[insert_index:insert_index] = insert_lines
        print(f"本日のノートに {len(tasks_to_insert)} 件のタスクを挿入しました。")
    else:
        insert_lines = ["# 本日の予定\n"] + [t + "\n" for t in tasks_to_insert] + ["\n"]
        lines = insert_lines + lines
        print(f"新規セクションを作成し、本日のノートに {len(tasks_to_insert)} 件のタスクを書き込みました。")

    # 本日のデイリーノート保存
    if os.path.dirname(today_filepath):
        os.makedirs(os.path.dirname(today_filepath), exist_ok=True)
    with open(today_filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # future_tasks.md の完了更新
    with open(future_tasks_path, "r", encoding="utf-8") as f:
        future_lines = f.readlines()

    for task in selected_tasks:
        idx = task["line_no"]
        raw = future_lines[idx]
        raw_clean = raw.rstrip("\r\n")
        # "- [ ]" を "- [x]" に置換し、[copied:: YYYY-MM-DD] を付与
        new_line = raw_clean.replace("- [ ]", "- [x]", 1)
        if "[copied::" not in new_line:
            new_line += f" [copied:: {today_str}]"
        future_lines[idx] = new_line + "\n"

    with open(future_tasks_path, "w", encoding="utf-8") as f:
        f.writelines(future_lines)
    
    print("予定リスト側のステータスを更新しました。")

def interactive_mode(future_tasks_path):
    """対話モードで予定を追加する"""
    print("--- 今後の予定追加（対話モード） ---")
    
    # タスク内容の入力 (必須)
    while True:
        task_content = input("タスク内容を入力してください (必須): ").strip()
        if task_content:
            break
        print("タスク内容は必須です。")

    # 予定日の入力 (任意)
    while True:
        date_input = input("予定日を入力してください (YYYY-MM-DD または YYYYMMDD、指定なしは空エンター): ").strip()
        if not date_input:
            date_str = None
            break
        formatted_date = parse_date_input(date_input)
        if formatted_date:
            date_str = formatted_date
            break
        print("無効な日付フォーマットです。")

    # カテゴリの入力 (任意)
    while True:
        cat_input = input("カテゴリを選択してください（1: 研究, 2: 私用, 空エンター: 未分類）: ").strip()
        if not cat_input:
            category = None
            break
        if cat_input == "1":
            category = "研"
            break
        elif cat_input == "2":
            category = "私"
            break
        print("1, 2 または 空エンターで指定してください。")

    # 優先度の入力 (任意)
    priority_input = input("優先度を入力してください (例: A, B, C、空エンター: 指定なし): ").strip()
    priority = priority_input if priority_input else None

    # 保存
    add_future_task(future_tasks_path, task_content, date_str, category, priority)

def main():
    parser = argparse.ArgumentParser(description="今後の予定を入力・管理するスクリプト")
    parser.add_argument("-t", "--task", type=str, help="タスク内容")
    parser.add_argument("-d", "--date", type=str, help="予定日 (YYYY-MM-DD または YYYYMMDD)")
    parser.add_argument("-c", "--category", type=str, help="カテゴリ (研/research, 私/private)")
    parser.add_argument("-p", "--priority", type=str, help="優先度 (A, B, C など)")
    parser.add_argument("-l", "--list", action="store_true", help="未完了の予定を一覧表示し、現時点で転記します")
    args = parser.parse_args()

    try:
        config = load_config()
    except Exception as e:
        print(f"設定ファイルの読み込みに失敗しました: {e}")
        return

    daily_note_path, _, future_tasks_path = resolve_paths(config)
    if not future_tasks_path:
        future_tasks_path = "./future_tasks.md"
    if not daily_note_path:
        daily_note_path = "./test_resource"

    # リスト転記モード
    if args.list:
        list_and_copy_tasks(future_tasks_path, daily_note_path)
        return

    # 通常の追加モード
    if args.task:
        # 引数ありモード
        date_str = None
        if args.date:
            formatted_date = parse_date_input(args.date)
            if not formatted_date:
                print(f"エラー: 無効な日付フォーマットです: {args.date}")
                return
            date_str = formatted_date
            
        category = args.category
        if category in ("research", "研"):
            category = "研"
        elif category in ("private", "私"):
            category = "私"
            
        add_future_task(future_tasks_path, args.task, date_str, category, args.priority)
    else:
        # 対話モード
        interactive_mode(future_tasks_path)

if __name__ == "__main__":
    main()
