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
        return task_line.strip()
    
    content = match.group(1).strip()
    
    # 2. Dataview のインラインフィールド ([key:: value]) を除去
    # 括弧で囲まれた部分（[key:: value]）を空文字列に置換
    content_cleaned = re.sub(r"\[[^\]]+::[^\]]+\]", "", content)
    return content_cleaned.strip()

def extract_uncompleted_tasks(filepath):
    """指定されたファイルから未達成のタスク（箇条書き行）を抽出する"""
    uncompleted_tasks = []
    
    # 理由行の判定用 (転記から除外するため、念のため残す)
    reason_pattern = re.compile(r"^\s*->\s*(.*)$")
    # チェックボックス行の判定 (例: - [ ] タスク名, - [x] タスク名, - [/] タスク名)
    task_pattern = re.compile(r"^\s*-\s*\[([ xX/])\]\s*(.*)$")
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.rstrip("\r\n")
            line_clean = line_str.strip()
            
            # 空行や理由行、ヘッダー行は無視
            if not line_clean or reason_pattern.match(line_clean) or line_clean.startswith("#"):
                continue
                
            # チェックボックス行の判定
            task_match = task_pattern.match(line_clean)
            if task_match:
                status = task_match.group(1)
                content = task_match.group(2).strip()
                
                # 完了（x, X）以外のものを未達成として抽出する
                if status not in ("x", "X") and content:
                    # [time:: ...] プロパティを除去して転記する (翌日に時間を引き継がないため)
                    content_cleaned = re.sub(r"\[time::\s*[^\]]+\]", "", content).strip()
                    # 連続するスペースや余分なスペースをトリム
                    content_cleaned = re.sub(r"\s+", " ", content_cleaned)
                    uncompleted_tasks.append(f"- [ ] {content_cleaned}")
                        
    return uncompleted_tasks

def write_tasks_to_today(filepath, new_tasks):
    """本日（ターゲット日）のノートファイルにタスクを書き込む。重複はスキップする。"""
    file_exists = os.path.exists(filepath)

    if not new_tasks:
        if not file_exists:
            # 転記するタスクが0件だが、本日のノートが存在しない場合は最低限のテンプレートを作成
            print("転記する未達成タスクはありませんが、本日のノートを新規テンプレートで作成します。")
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("# 本日の予定\n\n")
            return True
        else:
            print("転記する未達成タスクはなく、本日のノートは既に存在します。")
            return False

    lines = []
    existing_task_names = set()
    
    if file_exists:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # 既存タスクの抽出（重複チェック用）
        for line in lines:
            line_clean = line.strip()
            # 箇条書き行であるかつ理由行でない場合
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
            # タスクはあるがすべて重複していた（通常はあり得ないが、ファイルが存在しない場合）
            # 最低限のテンプレートを作成
            print("転記するタスクはありませんが、本日のノートを新規テンプレートで作成します。")
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("# 本日の予定\n\n")
            return True
        else:
            print("すべてのタスクが既に本日のノートに存在するため、転記をスキップします。")
            return False
            
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
        
    return True


def main():
    parser = argparse.ArgumentParser(description="直前の未達成タスクを本日のデイリーノートに転記するプログラム")
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

    daily_note_path = config.get("daily_note_path", "./test_resource")
    
    print(f"対象日付: {target_date_str}")
    
    # 1. 直前のデイリーノートを探索
    prev_filepath, prev_date = find_previous_note(daily_note_path, target_date)
    if not prev_filepath:
        print(f"エラー: 直前（過去30日以内）のデイリーノートが見つかりませんでした。")
        return
        
    prev_date_str = prev_date.strftime("%Y-%m-%d")
    print(f"直前のノートを発見: {os.path.basename(prev_filepath)} ({prev_date_str})")
    
    # 2. 未達成タスクを抽出
    uncompleted_tasks = extract_uncompleted_tasks(prev_filepath)
    print(f"未達成タスク抽出数: {len(uncompleted_tasks)} 件")
    for t in uncompleted_tasks:
        print(f"  {t}")
        
    # 3. 本日のデイリーノートへ転記
    today_filepath = os.path.join(daily_note_path, f"{target_date_str}.md")
    write_tasks_to_today(today_filepath, uncompleted_tasks)

if __name__ == "__main__":
    main()
