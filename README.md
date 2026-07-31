# 🐾 ねこのひげ（neko_no_hige）

**痛み × 気圧 × 服薬リマインダー** を1つにまとめた Django Web アプリ。
天候（特に気圧の変化）と体調の痛みの関係を記録・可視化し、服薬を猫がやさしくリマインドします。

---

## 📌 特徴（Features）

- **痛み記録**：部位・痛みの種類・レベル(1〜3)・メモを記録（ユーザーごとに分離）
- **気圧の可視化（見える化）**：DBに蓄積した気圧を時系列グラフ化（Chart.js）し、痛みとの相関を見る
- **天気痛リスク予報（痛み予報）**：過去の実測気圧＋**未来10日間の予報気圧**を1本の折れ線で表示し、気圧の**6時間の急降下（Δ）**から天気痛リスク（低/中/高）を判定。色帯・日次タイムライン・猫アドバイスで提示（詳細は後述）
- **服薬リマインダー**：設定時刻に次の服薬を猫の吹き出しで通知（ユーザーごとに分離）
- **天気アドバイス**：今日の気温（最高/最低/寒暖差）に応じた猫のひとことアドバイス
- **ユーザー認証**：ログイン／新規登録／**ログアウト**、**ログイン状態維持(14日)**
- **アクセス制御**：未ログインはログイン画面へ。URL直打ちでは中身を閲覧不可

### 設計上の重要な意思決定
| データ | 扱い | 理由 |
|---|---|---|
| **気圧** | DBに蓄積（時系列） | 「変化」が痛みに効くため、推移を残す |
| **気温・天気** | 最新をAPI表示（蓄積しない） | 「今」が大事なため、Open-Meteoから都度取得 |
| **天気痛リスク** | **気圧の変化率（Δ6h）で判定** | 天気痛の主因は絶対気圧ではなく「急降下」。判定関数は1箇所（`weather_sync.classify_pain_risk`）に集約し、**見える化と痛み予報で同一基準**を共有 |

→ 気温を2箇所から出さないため、表示の不整合は構造的に発生しない設計。
→ リスク判定も単一の関数に集約したため、ページ間で「危険」の定義がズレない設計。

---

## 🛠 技術スタック（Tech Stack）

| 項目 | 内容 |
|---|---|
| 言語 | Python 3.13 |
| フレームワーク | Django 5.2 |
| DB | SQLite3 |
| グラフ | Chart.js v4.4.1（痛み予報は annotation プラグインで急降下ゾーンを描画） |
| 天気API | Open-Meteo API（APIキー不要／気圧 surface_pressure・予報 forecast_days 対応） |
| 開発環境 | Visual Studio 2022 + PowerShell |
| 仮想環境 | `.venv` |
| フォント | Meiryo UI |

### 主な依存パッケージ（requirements.txt）
```
Django==5.2.14        # フレームワーク本体
asgiref==3.11.1       # Django ASGI サポート
sqlparse==0.5.5       # Django のSQL整形
tzdata==2026.2        # タイムゾーン（Asia/Tokyo）
requests==2.34.2      # Open-Meteo API 呼び出し
certifi / charset-normalizer / idna / urllib3   # requests 依存
openpyxl==3.1.5 / et_xmlfile==2.0.0             # Excel入出力（用途要確認）
```

---

## 📂 ディレクトリ構成（要点）

```
neko_no_hige/
├─ config/                 # プロジェクト設定
│  ├─ settings.py          # TEMPLATES DIRS=[BASE_DIR/"templates"], APP_DIRS=True
│  └─ urls.py              # accounts/(auth.urls) を include。views は import しない
├─ tracker/                # メインアプリ
│  ├─ views.py             # home / charts / pain_* / weather_risk / signup 等（全て user 絞り込み）
│  ├─ urls.py              # from . import views / app_name='tracker'（weather-risk/ を含む）
│  ├─ models.py            # PainRecord / WeatherRecord(is_forecast) / ReminderSetting / UserLocation 他
│  ├─ admin.py
│  ├─ migrations/
│  │  └─ 0003_painrecord_user_remindersetting_user_and_more.py  # Lv3 user FK 追加
│  └─ services/
│     ├─ reminder.py       # get_next_reminder(now, user) → 次の服薬情報 dict（is_active=True かつ当該ユーザーのみ）
│     ├─ advice.py         # build_temperature_advice(max,min) → 猫アドバイス（home が依存・必須）
│     └─ weather_sync.py   # 気象データの非同期取得・更新（実測/予報を is_forecast で保存）＋ 天気痛リスク判定ロジック
├─ templates/              # ← テンプレートはプロジェクト直下（tracker/templates ではない）
│  ├─ registration/
│  │  ├─ login.html        # ログイン画面（オレンジ猫テイスト）
│  │  └─ signup.html       # 新規登録画面
│  └─ tracker/
│     ├─ home.html         # 猫リマインダー吹き出し＋左下ログアウト（メニューに痛み予報を含む）
│     ├─ charts.html       # 気圧の時系列グラフ（見える化。痛み予報と同一のΔリスクで色帯表示）
│     ├─ weather_risk.html # ★天気痛リスク予報（実測＋10日予報の気圧・リスク帯・日次タイムライン）
│     ├─ pain_create.html
│     ├─ pain_edit.html
│     └─ pain_history.html
├─ db.sqlite3              # ← .gitignore 済み（GitHubに上げない）
├─ .venv/
└─ manage.py
```

> ⚠️ **テンプレートの置き場所はプロジェクト直下 `templates/`**。
> `tracker/templates/tracker/` の同名ファイルは settings の優先順位で**死蔵**になるため使わない（重複フォルダは整理済み）。

---

## 🌦 天気痛リスク予報（痛み予報 / weather_risk）

気圧の「変化」から天気痛リスクを予報する画面。URL `/weather-risk/`（`tracker:weather_risk`）。全ページのナビから遷移可能。

### 画面表示
- **気圧の推移グラフ（Chart.js）**：過去48時間の**実測**（実線）＋未来**10日間**の**予報**（点線）を1本の折れ線で連結。境界に「現在」ライン。
- **Y軸は自動フィット**：データの最小〜最大に上下2hPaの余白を付けて拡大表示（**最低10hPa幅を確保**し微小ノイズは誇張しない）。数hPaの起伏もはっきり見える。
- **急降下ゾーン**：6時間で気圧が大きく下がる区間を色帯で強調（中=橙／高=赤）。
- **今後10日間のリスク予報**：1日ごとの**11点タイムライン**（各日＝その日の**最悪6時間降下**で判定）。
- **現在のリスク**＋**猫のひとことアドバイス**（ルールベース、LLM不要）。
- ヘッダーは全ページ共通の全幅ナビバーで、スクロールしても残る**上部固定（`position: sticky`）**。

### リスク判定ロジック（単一の真実：`services/weather_sync.py`）
**絶対気圧ではなく「6時間先との気圧差 Δ（＝下降幅）」**で区分する。天気痛の主因が急降下であるため。

| リスク | 条件（6時間差 Δ） |
|---|---|
| 🔴 高リスク | Δ ≤ **-4** hPa |
| 🟠 中リスク | **-4** < Δ ≤ **-2** hPa |
| 🟢 低リスク | Δ > **-2** hPa または上昇 |

- 閾値は `weather_sync.py` の `DROP_HIGH_HPA(-4.0)` / `DROP_MID_HPA(-2.0)` の**1箇所で調整**（`RISK_WINDOW_H=6`）。
- 主な関数：
  - `classify_pain_risk(Δ)` → `"high"/"mid"/"low"`
  - `build_risk_timeline(series, step_h, horizon_h)` → 各スロットの最悪6h降下でリスク配列を生成
  - `current_pain_risk(series)` → 「今」のリスク
  - `build_advice(timeline)` → 猫アドバイス文

### 実測と予報の分離（`WeatherRecord.is_forecast`）
- `is_forecast` で **実測(False)** と **予報(True)** を区別して保存。
- `weather_sync._do_sync()` が Open-Meteo から取得し、過去〜現在=実測／未来=予報で振り分け（`update_or_create` で重複増殖を防止）。
- 予報の保存範囲は `FORECAST_BUFFER_H=240`（**10日**）。取得は `forecast_days=11`（今日＋10日）で、「今」から**丸10日先まで**確実にカバー（`forecast_days` は今日0時起点のため +1 が必要）。
- ⚠️ 気象予報は7〜10日を超えると的中率が急落するため、後半日は「参考程度」。

### 見える化（charts）との整合
- **見える化ページも同じ `classify_pain_risk`（Δ降下ベース）を流用**し、日ごとのリスクを色帯で表示（`views.charts` が各日の**最悪6h降下**から算出）。
- 旧「**1010hPa 以下＝警戒帯**」（絶対値基準）は**廃止**し、**中立の参考線**に格下げ。これにより2ページで「危険」の定義が一致。
- 見える化の猫アイコンは「**記録した痛み**（実績）」、色帯は「**予測リスク**」と役割を明確化し、予測 vs 実績を見比べられる。

---

## 🗄 データベース構造（主要テーブル）

| テーブル | 主要カラム | 備考 |
|---|---|---|
| `tracker_painrecord` | **user(FK)**, recorded_at, level(1=痛くない/2=ちょっと痛い/3=すごく痛い), body_part, pain_type, memo(140字) | 痛み記録。**Lv3でuser FK追加（null許可で既存救済→backfill済）** |
| `tracker_weatherrecord` | observed_at(unique), weather_code(0晴/1晴のち曇/2曇/3雨, default=2), temperature_c, pressure_hpa, **is_forecast(bool)** | 気圧を痛み突合の中核に活用。**`is_forecast` で実測(False)/予報(True)を分離**（痛み予報の10日先予報に使用） |
| `tracker_remindersetting` | **user(FK)**, reminder_time, medicine_name, is_active(default=True) | 服薬リマインダー設定。**Lv3でuser FK追加** |
| `tracker_userlocation` | （pk=1固定の単一レコード運用） | 現在地。当面全員共有 |
| `tracker_medicationrecord` | taken_at, name | **デッドコード**（ビューから未参照） |
| `auth_user` | username, password(ハッシュ), is_superuser 他 | ユーザー（パスワードはPBKDF2でハッシュ化） |
| `django_session` | session_key, session_data, expire_date | ログインセッション |

---

## 🔐 認証（Authentication）

| 種類 | 作成方法 | 権限 |
|---|---|---|
| スーパーユーザー | `python manage.py createsuperuser` | 全権限・`/admin/` 利用可 |
| 一般ユーザー | `/signup/` の登録フォーム（`UserCreationForm`） | アプリ機能のみ |

- ログイン：`/accounts/login/`（`django.contrib.auth` の `auth.urls`）
- 新規登録：`/signup/`（`tracker.views.signup`）
- ログアウト：`/accounts/logout/`（**Django 5.x 仕様で POST 必須**。home画面左下にCSRF付き`<form>`で配置）
- パスワードは平文では保存されず、`auth_user.password` にハッシュ値として格納される。

### アクセス制御
- 全ビューに `@login_required` を適用。未ログインは `LOGIN_URL` へリダイレクト。
- URL直打ちでは他ユーザーの中身を閲覧不可。

### ログイン状態維持（実値）
```python
SESSION_COOKIE_AGE = 1209600            # 14日間（=Djangoデフォルト。意図して維持と明示）
SESSION_EXPIRE_AT_BROWSER_CLOSE = False # ブラウザを閉じても維持
```

### settings.py の認証設定（実値）
```python
LOGIN_URL          = 'login'            # 未ログイン時の遷移先
LOGIN_REDIRECT_URL = 'tracker:home'     # ログイン成功後
LOGOUT_REDIRECT_URL = 'login'           # ログアウト後
```

> ⚠️ **`AUTH_PASSWORD_VALIDATORS = []`（空）**。パスワード強度チェックが無効なため、短い/単純なパスワードでも登録できる。発表会のデモ用途では許容だが、本番化する場合は標準バリデータを有効化すること。

### URL名前空間の注意
- ログインへのリンク → `{% url 'login' %}`（名前空間なし）
- サインアップ → `{% url 'tracker:signup' %}`（`app_name='tracker'`）
- ログアウト → `{% url 'logout' %}`（名前空間なし・POSTフォーム）
- 痛み予報 → `{% url 'tracker:weather_risk' %}`（`/weather-risk/`）

---

## 🚀 セットアップ手順

```powershell
# 1. リポジトリ取得
git clone https://github.com/rebelnaoto7/neko_no_hige.git
cd neko_no_hige

# 2. 仮想環境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. 依存パッケージ
pip install -r requirements.txt

# 4. マイグレーション
python manage.py migrate

# 5. 管理者アカウント作成
python manage.py createsuperuser

# 6. 起動
python manage.py runserver
```

ブラウザ：
- アプリ：`http://127.0.0.1:8000/`
- 痛み予報：`http://127.0.0.1:8000/weather-risk/`
- 新規登録：`http://127.0.0.1:8000/signup/`
- 管理画面：`http://127.0.0.1:8000/admin/`

> 💡 **予報データの反映**：痛み予報の気圧同期は home / 見える化を開いたときに走る（`sync_weather_async`）。設定変更後（予報日数など）は一度これらのページを開いて再同期すると、10日先までの予報がDBに埋まる。

---

## ⚠️ 開発時の注意（事故防止ルール）

1. **テンプレートはエディタ（VS2022）で編集**。チャット直貼りは `{% url %}`/`{% static %}` タグ破損の原因。
2. **既存の日本語ファイルは全置換禁止・手動最小編集**（PowerShellの `Get-Content` は日本語が文字化けするが、ディスク上はUTF-8で正常。文字化けを基に全置換すると破壊する）。
3. **CSS/HTMLコメント内に `{% %}` を書かない**。Djangoが解釈して `TemplateSyntaxError`。無視されるのは `{# #}` のみ。
4. ビューの `path` は **`tracker/urls.py`** に書く（`config/urls.py` は views を import していないため `NameError`）。
5. **天気痛リスクの閾値を変えるときは `weather_sync.py` の `DROP_HIGH_HPA`/`DROP_MID_HPA` の1箇所だけ**を編集する（見える化・痛み予報の両方に効く。表示側の文言・色帯は追従して更新すること）。
6. migrate前は必ずDBバックアップ：
   ```powershell
   Copy-Item .\db.sqlite3 ".\db_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sqlite3"
   ```

---

## 🗺 ロードマップ

| Lv | 内容 | 状態 |
|---|---|---|
| Lv1 | createsuperuser でログイン動作 | ✅ 完了 |
| Lv2 | サインアップ画面（自己登録） | ✅ 完了 |
| Lv3 | データ個別化（PainRecord・ReminderSetting に user FK 追加・全ビュー絞り込み） | ✅ 完了（migration 0003・backfill・reminder.py対応済） |
| Lv4 | 天気痛リスク予報（痛み予報）＋見える化とのリスク整合 | ✅ 完了（詳細は上記セクション） |

### 既知の残タスク
- [ ] `signup.html` 最下部リンクの修正（URLが文字列で漏れる表示崩れ）
- [ ] charts に週間気温 max/min 表示
- [ ] Azure へのデプロイ
- [ ] `tracker_userlocation` の全員共有運用をユーザー個別化するか検討
- [ ] `tracker_medicationrecord`（デッドコード）の削除可否を判断
- [ ] 他ページのヘッダーも上部固定（sticky）に揃えるか検討（現状は痛み予報のみ固定）
- [ ] 予報後半（7〜10日）の低精度をUI上でどう伝えるか検討

### 完了済み（今回反映）
- [x] Lv3：PainRecord・ReminderSetting のユーザー個別化
- [x] ログイン状態の維持設定（SESSION_COOKIE_AGE=14日 / EXPIRE_AT_BROWSER_CLOSE=False）
- [x] ログアウト（POST＋CSRF）を home 左下に配置
- [x] **天気痛リスク予報（weather_risk）追加**：実測＋10日予報の気圧グラフ、Δ降下ベースのリスク判定、日次タイムライン、猫アドバイス
- [x] **`WeatherRecord.is_forecast` で実測/予報を分離**（予報 `forecast_days=11`／保存 `FORECAST_BUFFER_H=240`＝10日）
- [x] **見える化と痛み予報のリスク基準を統一**（`classify_pain_risk` を共有／絶対1010警戒帯→中立の参考線へ格下げ／記録痛み と 予測リスク を区別）
- [x] リスク閾値を高感度化（高 -4hPa／中 -2hPa）
- [x] 痛み予報グラフのY軸自動フィット（最低10hPa幅を確保）
- [x] 全ページのナビに「痛み予報」リンクを追加
- [x] 痛み予報ヘッダーを全幅・上部固定（sticky）に変更

---

## 📄 ライセンス

要確認（未設定）
