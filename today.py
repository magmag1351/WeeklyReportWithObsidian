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

def parse_date(date_str):
    """YYYYMMDD または YYYY-MM-DD 形式の日付文字列を datetime オブジェクトに変換する"""
    date_clean = date_str.replace("-", "").strip()
    if len(date_clean) == 8 and date_clean.isdigit():
        try:
            return datetime.strptime(date_clean, "%Y%m%d")
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"無効な日付形式です: {date_str}。YYYYMMDD または YYYY-MM-DD で指定してください。")

def find_previous_note(daily_note_path, target_date, max_lookup_days=30):
    """target_date の前日から順に過去に遡り、存在するデイリーノートファイルを探索する"""
    current_date = target_date - timedelta(days=1)
    for _ in range(max_lookup_days):
        date_str = current_date.strftime("%Y-%m-%d")
        filepath = os.path.join(daily_note_path, f"{date_str}.md")
        if os.path.exists(filepath):
            return filepath, current_date
        current_date -= timedelta(days=1)
    return None, None

def clean_task_content(task_line):
    """タスクの行からチェックボックス記号やDataviewのインラインフィールドを除去し、純粋なタスク名を取得する"""
    # 1. チェックボックス表記の除去 (例: "- [ ] タスク名" や "- [x] タスク名")
    match = re.match(r"^\s*-\s*(?:\[[ xX/]\])?\s*(.*)$", task_line)
    if not match:
        content_cleaned = re.sub(r"\[[^\]]+::[^\]]+\]", "", task_line)
        return content_cleaned.strip()
    
    content = match.group(1).strip()
    
    # 2. Dataview のインラインフィールド ([key:: value]) を除去
    content_cleaned = re.sub(r"\[[^\]]+::[^\]]+\]", "", content)
    return content_cleaned.strip()

def extract_uncompleted_tasks(filepath):
    """指定されたファイルから未達成のタスク（箇条書き行）を抽出する"""
    uncompleted_tasks = []
    
    # 理由行の判定用
    reason_pattern = re.compile(r"^\s*->\s*(.*)$")
    # チェックボックス行の判定
    task_pattern = re.compile(r"^\s*-\s*\[([ xX/])\]\s*(.*)$")
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.rstrip("\r\n")
            line_clean = line_str.strip()
            
            if not line_clean or reason_pattern.match(line_clean) or line_clean.startswith("#"):
                continue
                
            task_match = task_pattern.match(line_clean)
            if task_match:
                status = task_match.group(1)
                content = task_match.group(2).strip()
                
                if status not in ("x", "X") and content:
                    content_cleaned = re.sub(r"\[time::\s*[^\]]+\]", "", content).strip()
                    content_cleaned = re.sub(r"\s+", " ", content_cleaned)
                    uncompleted_tasks.append(f"- [ ] {content_cleaned}")
                        
    return uncompleted_tasks

def extract_due_future_tasks(future_tasks_path, target_date):
    """future_tasks_path から予定日が target_date 以前の未完了タスクを抽出する"""
    if not os.path.exists(future_tasks_path):
        return []
    
    due_tasks = []
    # ターゲット日の日付部分のみを取得して比較
    target_date_only = datetime(target_date.year, target_date.month, target_date.day)
    
    with open(future_tasks_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line_clean = line.strip()
            # 未完了のタスクのみ対象 (- [ ])
            match = re.match(r"^\s*-\s*\[ \]\s*(.*)$", line_clean)
            if match:
                raw_content = match.group(1).strip()
                # 予定日 [scheduled:: YYYY-MM-DD] をパース
                scheduled_match = re.search(r"\[scheduled::\s*([^\]]+)\]", raw_content)
                if scheduled_match:
                    scheduled_date_str = scheduled_match.group(1).strip()
                    try:
                        # 比較用に datetime にパース
                        scheduled_date = datetime.strptime(scheduled_date_str, "%Y-%m-%d")
                        scheduled_date_only = datetime(scheduled_date.year, scheduled_date.month, scheduled_date.day)
                        
                        # 予定日がターゲット日以前のものを対象とする
                        if scheduled_date_only <= target_date_only:
                            # scheduled プロパティを除去して転記用にする
                            content_cleaned = re.sub(r"\[scheduled::\s*[^\]]+\]", "", raw_content)
                            content_cleaned = re.sub(r"\s+", " ", content_cleaned).strip()
                            due_tasks.append({
                                "line_no": i,
                                "content": content_cleaned,
                                "raw_content": raw_content
                            })
                    except ValueError:
                        # 日付フォーマットが正しくない場合はスキップ
                        pass
    return due_tasks

def mark_future_tasks_completed(future_tasks_path, completed_task_line_indices, target_date_str):
    """指定された行のタスクを完了（- [x]）に変更し、copiedプロパティを追加する"""
    if not os.path.exists(future_tasks_path) or not completed_task_line_indices:
        return
    
    with open(future_tasks_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for idx in completed_task_line_indices:
        raw = lines[idx]
        raw_clean = raw.rstrip("\r\n")
        new_line = raw_clean.replace("- [ ]", "- [x]", 1)
        if "[copied::" not in new_line:
            new_line += f" [copied:: {target_date_str}]"
        lines[idx] = new_line + "\n"
        
    with open(future_tasks_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

def write_tasks_to_today(filepath, new_tasks):
    """本日（ターゲット日）のノートファイルにタスクを書き込む。重複はスキップする。
    戻り値: (success_bool, inserted_tasks_list)
    """
    file_exists = os.path.exists(filepath)

    if not new_tasks:
        if not file_exists:
            print("転記する未達成タスクはありませんが、本日のノートを新規テンプレートで作成します。")
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("# 本日の予定\n\n")
            return True, []
        else:
            print("転記する未達成タスクはなく、本日のノートは既に存在します。")
            return False, []

    lines = []
    existing_task_names = set()
    
    if file_exists:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # 既存タスクの抽出（重複チェック用）
        for line in lines:
            line_clean = line.strip()
            if line_clean.startswith("-") and not line_clean.startswith("->"):
                cleaned = clean_task_content(line_clean)
                if cleaned:
                    existing_task_names.add(cleaned)
    
    # 重複していないタスクのみをフィルタリング
    tasks_to_insert = []
    for task in new_tasks:
        cleaned = clean_task_content(task)
        if cleaned not in existing_task_names:
            tasks_to_insert.append(task)
        else:
            print(f"重複スキップ: {task}")
            
    if not tasks_to_insert:
        if not file_exists:
            print("転記するタスクはありませんが、本日のノートを新規テンプレートで作成します。")
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("# 本日の予定\n\n")
            return True, []
        else:
            print("すべてのタスクが既に本日のノートに存在するため、転記をスキップします。")
            return False, []
            
    # `# 本日の予定` または `# 本日行うこと` 見出しを検索
    heading_pattern = re.compile(r"^#+\s+(本日の予定|本日行うこと)\s*$")
    heading_idx = -1
    for i, line in enumerate(lines):
        if heading_pattern.match(line.strip()):
            heading_idx = i
            break
            
    if heading_idx != -1:
        insert_index = heading_idx + 1
        insert_lines = [task + "\n" for task in tasks_to_insert]
        lines[insert_index:insert_index] = insert_lines
        print(f"既存のノートに {len(tasks_to_insert)} 件のタスクを挿入しました。")
    else:
        insert_lines = ["# 本日の予定\n"] + [task + "\n" for task in tasks_to_insert] + ["\n"]
        lines = insert_lines + lines
        print(f"新規セクションを作成し、{len(tasks_to_insert)} 件のタスクを書き込みました。")
        
    # ファイルへの書き込み
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)
        
    return True, tasks_to_insert


def main():
    parser = argparse.ArgumentParser(description="直前の未達成タスクおよび将来の予定を本日のデイリーノートに転記するプログラム")
    parser.add_argument(
        "--date", "-d",
        type=parse_date,
        default=datetime.now(),
        help="対象とする日付 (形式: YYYYMMDD または YYYY-MM-DD)。指定がない場合は実行日の日付。"
    )
    args = parser.parse_args()
    
    target_date = args.date
    target_date_str = target_date.strftime("%Y-%m-%d")
    
    try:
        config = load_config()
    except Exception as e:
        print(f"設定ファイルの読み込みに失敗しました: {e}")
        return

    daily_note_path, _, future_tasks_path = resolve_paths(config)
    if not daily_note_path:
        daily_note_path = "./test_resource"
    if not future_tasks_path:
        future_tasks_path = "./future_tasks.md"
    
    print(f"対象日付: {target_date_str}")
    
    # 1. 直前のデイリーノートを探索
    prev_filepath, prev_date = find_previous_note(daily_note_path, target_date)
    uncompleted_tasks = []
    if prev_filepath:
        prev_date_str = prev_date.strftime("%Y-%m-%d")
        print(f"直前のノートを発見: {os.path.basename(prev_filepath)} ({prev_date_str})")
        # 2. 未達成タスクを抽出
        uncompleted_tasks = extract_uncompleted_tasks(prev_filepath)
        print(f"前日からの未達成タスク抽出数: {len(uncompleted_tasks)} 件")
        for t in uncompleted_tasks:
            print(f"  {t}")
    else:
        print(f"情報: 直前（過去30日以内）のデイリーノートが見つかりませんでした。")
        
    # 2.5 今後の予定 (future_tasks.md) から本日以前が予定日のタスクを抽出
    due_future_tasks = []
    if os.path.exists(future_tasks_path):
        due_future_tasks = extract_due_future_tasks(future_tasks_path, target_date)
        print(f"今後の予定（予定日到来分）抽出数: {len(due_future_tasks)} 件")
        for t in due_future_tasks:
            print(f"  - [ ] {t['content']}")
            
    # タスクの合算
    future_tasks_formatted = [f"- [ ] {t['content']}" for t in due_future_tasks]
    all_tasks = uncompleted_tasks + future_tasks_formatted
    
    # 3. 本日のデイリーノートへ転記
    today_filepath = os.path.join(daily_note_path, f"{target_date_str}.md")
    success, inserted_tasks = write_tasks_to_today(today_filepath, all_tasks)
    
    # 4. 実際に転記された今後の予定のステータスを更新
    if success and due_future_tasks:
        inserted_cleaned = {clean_task_content(t) for t in inserted_tasks}
        completed_line_indices = []
        
        for t in due_future_tasks:
            cleaned_future = clean_task_content(t['content'])
            if cleaned_future in inserted_cleaned:
                completed_line_indices.append(t['line_no'])
                
        if completed_line_indices:
            mark_future_tasks_completed(future_tasks_path, completed_line_indices, target_date_str)
            print(f"今後の予定リストの {len(completed_line_indices)} 件のステータスを更新しました。")

if __name__ == "__main__":
    main()
