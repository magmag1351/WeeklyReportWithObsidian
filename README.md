# WeeklyReportWithObsidian

Obsidian等のデイリーノート（Markdown）からタスクを読み込み、指定された期間の「達成/未達成」および「研究内容/私用内容/未分類」に整理した週報サマリーを作成するプログラムです。
また、前日の未達成タスクを本日のノートへ自動で引き継ぐ（転記する）スクリプトも含まれています。

タスク管理データは、Obsidianのプラグイン「Dataview」でも扱いやすく、かつNotion等の他ツールへの移行性も高い **Dataview形式（インラインキーバリュー形式）** に対応しています。

---

## 主な機能

- **期間指定の集計**: ターミナルで日付を直接指定するほか、オプションで「今週」を自動指定できます。
- **タスクの分類**:
  - `[category:: 研]` または `[category:: research]` を含むタスクは **研究内容**
  - `[category:: 私]` または `[category:: private]` を含むタスクは **私用内容**
  - それ以外は **未分類**
- **達成・未達成の判定**: `- [x]`（完了）または `- [X]` を **達成**、それ以外（`- [ ]` 未完了 や `- [/]` 進行中など）を **未達成** と判定します。
- **未達の理由の抽出**: タスク行内の `[memo:: 未達の理由]` または、未達成タスクの直後の行にある `-> 理由` を未達理由として抽出してサマリーに出力します。
- **重複タスクのマージ**: 複数日に出現した同一内容 of タスクは1つにマージされ、日付がカンマ区切りで併記されます。

---

## 環境構築

1. 仮想環境を作成して有効化します：
   ```bash
   python -m venv home
   source home/bin/activate  # macOS/Linuxの場合
   # home\Scripts\activate  # Windowsの場合
   ```

2. 必要なライブラリをインストールします（本プログラムは標準ライブラリのみで動作するため必須ではありませんが、リポジトリの設定に合わせる場合）：
   ```bash
   pip install -r requirements.txt
   ```

---

## 設定 (`config.json`)

プログラムの入出力先を指定します。

```json
{
    "daily_note_path": "./test_resource",
    "output_path": "./output"
}
```
- `daily_note_path`: デイリーノート（`YYYY-MM-DD.md` 形式）が保存されているディレクトリ。
- `output_path`: サマリーファイル（`summary_YYYYMMDD_YYYYMMDD.md`）の出力先ディレクトリまたはファイルパス。

---

## タスクの記述例（入力ファイル）

`YYYY-MM-DD.md`（例：`2026-06-29.md`）

```markdown
# 本日の予定
- [ ] COMSOLのキャッチアップ [category:: 研] [priority:: B]
- [x] 電気回路実験のTA [category:: 研] [priority:: A]
- [ ] Novaの予約を行う [category:: 私] [priority:: B] [memo:: レベルアップテスト後に対応する]
- [x] 7月分の予定入力 [category:: 私] [priority:: C]
- [ ] 未分類のタスク例
```

---

## 使い方

### 1. 手動で日付範囲を指定して実行
起動後、ターミナルで開始日と終了日を `YYYYMMDD` 形式で入力します。
```bash
python summarize.py
```
```text
--- 週報サマリー作成プログラム ---
開始日付を入力してください (YYYYMMDD): 20260618
終了日付を入力してください (YYYYMMDD): 20260629
```

### 2. 今週（月曜日〜金曜日）のサマリーを自動作成
`--this-week` オプションを付けて実行すると、今週の月曜日〜金曜日を自動で対象期間に設定して集計します（手動入力をスキップできます）。
```bash
python summarize.py --this-week
```

---

## 未達成タスクの翌日転記 (`today.py`)

直前のデイリーノートから未達成のタスクを抽出し、本日（または指定日）のデイリーノートの `# 本日の予定` セクションに自動で転記するプログラムです。

### 主な機能
- **自動過去探索**: 対象日（デフォルトは本日）の前日から順に過去に遡り、存在する直近のデイリーノートを自動で探索します（最大30日前まで）。
- **未達成タスクの抽出**: チェックボックスの状態が完了（`[x]`, `[X]`）以外のタスク（`[ ]`, `[/]` 等）を抽出します。
- **重複防止**: 既に本日（または対象日）のノートに同じ内容のタスクが存在する場合、重複して転記されるのを防ぎます（比較は `[category:: ...]` などのメタデータ部分を除去した純粋なタスク名で行われます）。
- **セクションの自動生成**: 対象日のノートに `# 本日の予定` または `# 本日行うこと` 見出しが存在しない場合（新規作成時など）、自動的に見出しを作成した上で転記します。

### 使い方

#### 1. 本日のデイリーノートに転記する
引数なしで実行すると、実行日の日付のデイリーノートに対して転記を行います。
```bash
python today.py
```

#### 2. 特定の日付を指定して転記する
`--date` (または `-d`) オプションを付けて実行すると、指定した日付のデイリーノートに対して転記を行います（日付形式は `YYYYMMDD` または `YYYY-MM-DD`）。
```bash
python today.py --date 2026-06-21
```

---

## プロパティ（属性）の追加とサマリーへの出力方法

タスクに新しいプロパティ（例：期限を示す `[due:: 2026-07-15]` など）を追加し、それを週報サマリー（`summarize.py`）に出力させたい場合は、以下の3ステップでカスタマイズを行います。

### 1. デイリーノートにプロパティを記述する
Dataview形式 `[キー:: 値]` でタスク行の末尾に追記します。
```markdown
- [ ] 英語論文の執筆開始 [category:: 研] [priority:: A] [due:: 2026-07-15]
```
※ `today.py` は、この段階で自動的に新しいプロパティも丸ごと翌日へ引き継ぐようになっています（追加の修正は不要です）。

### 2. `summarize.py` でプロパティをパースする
[summarize.py](file:///Users/magmag/Desktop/Program/git/WeeklyReportWithObsidian/summarize.py) 内の `parse_daily_notes` 関数で、新しいプロパティを正規表現で抽出します。

```python
# 例：dueプロパティをパースする処理を追加
due_date = None
due_match = re.search(r"\[due::\s*([^\]]+)\]", raw_content)
if due_match:
    due_date = due_match.group(1).strip()
```

抽出した値を、辞書 `last_task` に格納します。
```python
last_task = {
    "is_completed": is_completed,
    "category": category,
    "content": content,
    "date": date_str,
    "reasons": [],
    "due": due_date  # 格納する
}
```

### 3. `summarize.py` でデータを引き継ぎ、サマリーに出力する

#### マージ処理への追加 (`merge_tasks` 関数)
集計時にデータが消えないよう、マージ処理部分でプロパティを引き継ぎます。
```python
# merge_tasks 関数内
for t in parsed_tasks:
    key = (t["is_completed"], t["category"], t["content"])
    if key not in merged:
        keys.append(key)
        merged[key] = {
            "dates": [],
            "reasons": [],
            "due": t.get("due")  # 引き継ぐ
        }
```
辞書配列へのアペンド部分にも追加します。
```python
tasks[status_key][category].append({
    "content": content,
    "dates": sorted_dates,
    "reasons": merged[key]["reasons"],
    "due": merged[key]["due"]  # 追加
})
```

#### サマリー出力フォーマットへの追加 (`generate_summary_markdown` 関数)
`format_task_line` 内で、サマリーにどう出力するかを定義します。
```python
# generate_summary_markdown 関数内
def format_task_line(t):
    dates_str = ", ".join(t["dates"])
    line = f"- {t['content']} ({dates_str})"
    if t.get("due"):
        line += f" [期限：{t['due']}]"  # 期限があれば出力に加える
    if t["reasons"]:
        reasons_str = "、".join(t["reasons"])
        line += f" (理由：{reasons_str})"
    return line
```

---

## タスクの消費時間の管理 (`[time:: ...]`)

タスクごとに費やした時間を記録・集計するために、Dataview形式 `[time:: 値]` を追加できます。

### 1. タスクへの記述方法
デイリーノートのタスク行の末尾に、`[time:: 値]` を追記します。

- **単位なし（分または時間）**:
  - 整数で記述した場合、自動的に「分」として扱われます。(例: `[time:: 90]` -> 90分)
  - 小数点で記述した場合、自動的に「時間」として扱われます。(例: `[time:: 1.5]` -> 1.5時間 = 90分)
- **単位付き (h, m など)**:
  - 分単位: `[time:: 90m]`、`[time:: 90分]`
  - 時間単位: `[time:: 1.5h]`、`[time:: 1.5時間]`
  - 複合: `[time:: 1h30m]`、`[time:: 1時間30分]`

### 2. 週報サマリー（Weekly Report）への出力
`summarize.py` を実行すると、指定期間中にそのタスクに費やした時間が合算され、週報サマリーに `(時間：◯時間◯分)` の形式で出力されます。
- 例: `- Obsidianから週次まとめ資料を作成するプログラムの作成 (2026-06-20, 2026-06-21) (時間：1時間30分) (理由：バグ修正が必要)`

### 3. 翌日への引き継ぎ時の自動リセット
未達成タスクを `today.py` で翌日のノートに引き継ぐ際、誤った二重カウントを防ぐため、**前日の消費時間 `[time:: ...]` は自動的に取り除かれた状態で転記されます。** 翌日のノートには、その日に新たに費やした時間を記録してください。

