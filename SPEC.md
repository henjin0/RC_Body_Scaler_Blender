# RC_Body_Scaler_Blender - SPEC.md

## 概要

Meshyで生成した車の3DモデルからラジコンRCカー用ボディを作成するデスクトップGUIツール。
**PySide6** でUIを提供し、**vispy（OpenGL）** で3Dモデルをリアルタイム表示する。
Blender（bpy）をサブプロセスとして呼び出してSTLを出力する。

---

## 実装状況（2026-03-13時点）

| 機能 | 状態 | 備考 |
|------|------|------|
| PySide6 UI（ダーク/ライトテーマ） | ✅ 実装済み | |
| vispy OpenGL 3Dビューポート | ✅ 実装済み | PySide6バックエンド |
| ソリッド/透過/ワイヤーフレーム表示切替 | ✅ 実装済み | |
| モデルファイル読み込み（GLB/OBJ/STL/FBX） | ✅ 実装済み | |
| タイヤ位置・カット高さのビジュアライズ | ✅ 実装済み | 円柱+カット平面 |
| Blender自動検出 | ✅ 実装済み | macOS/Windows/Linux |
| Blender CLIによるSTL生成 | ✅ 実装済み | 動作未テスト |
| ▶ ピックボタン（3D面クリックで座標取得） | ✅ 実装済み | カメラ行列ベースのレイキャスト |
| モデル向き調整（初期回転） | ✅ 実装済み | Section 00 |
| ゆるやかなステップガイドUI | ❌ 未実装 | 全パネル常時表示 |

---

## 利用対象者

### ユーザー像

- ITの知識はない。PC操作はクリックと簡単なキーボード入力のみ
- CADや3Dモデリングの知識はない
- 高齢の方も利用する

### UIデザイン方針

- **ステップ番号を明示する**: 「00 / 01 / 02 / 03...」の形式で、今何をすべきかを常に明確にする
- **次に何をすべきか迷わせない**: 各ステップで操作すべきボタン・入力欄を強調し、関係ない操作はグレーアウト
- **フォントは大きめ**: 最小14px以上。重要なラベルは16px以上
- **エラーは平易な日本語で表示**: 「ブーリアン演算に失敗しました」ではなく「タイヤ位置の設定を見直してください」のように案内する
- **数値入力には単位を明記**: 入力欄の横に必ず「mm」を表示する
- **デフォルト値を必ず設定する**: 入力欄は空欄でなく、典型的な値をあらかじめ入れておく
- **確認ダイアログを適切に使う**: 「実行」「削除」など取り消しにくい操作の前に確認を挟む
- **処理中は待機状態を明示する**: プログレスバーと「処理中です。しばらくお待ちください。」のメッセージを表示する

---

## ライセンス方針

| コンポーネント | ライセンス | 商用利用 |
|--------------|-----------|---------|
| Python | PSF License | ✅ |
| PySide6 | LGPL v3 | ✅ |
| vispy | BSD | ✅ |
| PyOpenGL | BSD | ✅ |
| Blender | GPL v3 | ✅ ※注意事項あり |
| trimesh | MIT | ✅ |
| numpy | BSD | ✅ |
| scipy | BSD | ✅ |
| PyInstaller | MIT | ✅ |

> **注意**: Blenderバイナリを同梱・配布するとGPL v3の開示義務が生じる。
> Blenderを**別途インストール済み前提**とし、bpyスクリプトのみ配布する構成を推奨。
> この場合、アプリ本体のライセンスは自由に設定できる。

---

## インストール手順（人手で実施）

### 1. Blender

- 公式サイト: https://www.blender.org/download/
- バージョン: **3.6 LTS** または **4.x** 推奨
- インストール後、実行ファイルのパスを控えておく
  - Windows: `C:\Program Files\Blender Foundation\Blender 4.x\blender.exe`
  - macOS: `/Applications/Blender.app/Contents/MacOS/Blender`
  - Linux: `/usr/bin/blender` など
- アプリ起動時に標準インストール先を自動検出するため、通常はパス入力不要

### 2. Python

- 公式サイト: https://www.python.org/downloads/
- バージョン: **3.10 以上**（3.13推奨）
- Windows の場合、インストール時に「Add Python to PATH」にチェックを入れる
- macOS の場合、python.org からインストール推奨
- 仮想環境（venv）での実行を推奨

### 3. アプリのセットアップ

```bash
# リポジトリをクローン or ZIPを展開後
cd RC_Body_Scaler_Blender
python -m venv rcb
source rcb/bin/activate      # Windows: rcb\Scripts\activate
pip install -r requirements.txt
python main.py
```

### requirements.txt

```
trimesh>=4.0.0
numpy>=1.24.0
scipy>=1.10.0
vispy>=0.14.0
PyOpenGL>=3.1.0
PySide6>=6.5.0
```

---

## システム構成

```
[PySide6 GUI + vispy OpenGL 3D Viewer]
     ↓ params.json
[Blender CLI (blender --background --python)]
     ↓
[STL出力]
```

サーバー不要。ローカルで完結する。

---

## ディレクトリ構成

```
RC_Body_Scaler_Blender/
├── main.py                  # エントリポイント・PySide6 GUI
├── renderer.py              # vispy OpenGL 3Dレンダラー（Mesh表示・レイキャスト）
├── viewer.py                # 旧matplotlib 2Dビューア（廃止済み・参考用）
├── config.json              # Blenderパスなど設定（初回起動時に生成）
├── requirements.txt
├── SPEC.md
├── blender_scripts/
│   ├── process_body.py      # メインのbpyスクリプト（全処理を担当）
│   └── params.json          # GUIからbpyスクリプトへのパラメータ受け渡し
├── preview/                 # 処理中間モデルの一時保存（result.stl, loose_parts.json）
└── outputs/                 # 最終STL出力先
```

---

## GUIレイアウト（PySide6）

```
┌─────────────────────────────────────────────────────────────┐
│ RC Car Body Creator      [SOLID] [TRANSP] [WIRE]       [☀] │ ← ヘッダー 48px
├──────────────────────────────────┬──────────────────────────┤
│                                  │ 00  ORIENTATION          │
│                                  │   Rot X [ ] Rot Y [ ]   │
│                                  │   Rot Z [ ]              │
│                                  │   [Z↑] [Y↑] [Flip] [✓] │
│                                  ├──────────────────────────┤
│                                  │ 01  MODEL                │
│   vispy 3D Viewport              │   ファイルパス           │
│   （OpenGL / TurntableCamera）   │   [Open Model File…]     │
│   ドラッグで回転                 │   X:xxx Y:xxx Z:xxx mm   │
│   スクロールでズーム             │   Blender: xxx           │
│                                  │   [Set Blender Path…]    │
│                                  ├──────────────────────────┤
│                                  │ 02  TIRES                │
│                                  │   Front X [-85]  mm      │
│                                  │   Rear X  [ 85]  mm      │
│                                  │   Y Offset[ 45]  mm      │
│                                  │   Front Diam/Width       │
│                                  │   Rear  Diam/Width       │
│                                  │   [▶ FRONT X][▶ REAR X] │
│                                  ├──────────────────────────┤
│                                  │ 03  BODY                 │
│                                  │   Target WB [170] mm     │
│                                  │   Thickness [ 1.5] mm    │
│                                  │   Cut Z     [ 10] mm     │
│                                  │   [▶ PICK CUT Z]         │
│                                  ├──────────────────────────┤
│                                  │ 04  EXECUTE              │
│                                  │   [Run Blender Process]  │
│                                  │   ████░░ 処理中...       │
│                                  ├──────────────────────────┤
│                                  │ 05  CLEANUP              │
│                                  │   Part_001  vol: 0.12mm³ │
│                                  │   [Delete Selected Parts]│
│                                  ├──────────────────────────┤
│                                  │ 06  EXPORT STL           │
│                                  │   [Export STL…]          │
└──────────────────────────────────┴──────────────────────────┘
          ← ストレッチ →             ← 300px 固定・スクロール可 →
```

---

## 機能仕様

### 00. モデル向き調整（Section 00 ORIENTATION）

Meshyで生成したモデルは座標軸の向きが統一されていない場合がある。
タイヤ位置などを正しく設定するため、モデル読み込み後に向きを合わせる。

#### ユーザー操作

| 操作 | 説明 |
|------|------|
| Rot X / Rot Y / Rot Z 入力 | 各軸の回転角度（degree） |
| [Z↑] ボタン | Blender系モデル向け（Z軸=高さ）。X軸に-90°回転 |
| [Y↑] ボタン | vispy/OpenGLデフォルト（Y軸=高さ）。回転リセット |
| [Flip] ボタン | 上下反転（X軸に180°回転） |
| [✓ Apply] ボタン | 回転を頂点座標に適用して再描画 |

#### 内部処理（renderer.py）

```python
def apply_rotation(self, rx_deg, ry_deg, rz_deg):
    # 回転行列をnumpyで構築し、_orig_vertsに適用
    # _verts, _trimesh, _refresh_mesh()を更新
```

#### params.jsonへの追加

```json
"orientation": { "rx": 0.0, "ry": 0.0, "rz": 0.0 }
```

#### process_body.py での処理

```python
# モデル読み込み後、向き調整の回転を適用（ラジアン変換）
obj.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
bpy.ops.object.transform_apply(rotation=True)
```

---

### 01. 初回設定 / モデル読み込み

- 起動時にBlenderの実行ファイルパスを確認（自動検出→なければダイアログ）
- `config.json` に保存・次回から自動読み込み
- 「Open Model File…」ボタンでファイル選択ダイアログ
- 対応フォーマット: GLB / OBJ / STL / FBX
- 選択後、trimeshでバウンディングボックスを取得しUIに表示（サイズ参考値として）
- vispy 3Dビューポートに即時レンダリング

---

### 02. タイヤ除去

タイヤ部分を前後左右4本の円筒（Cylinder）でブーリアン差分をとって除去する。

#### ユーザー入力パラメータ

| パラメータ | 説明 | 単位 |
|-----------|------|------|
| 前輪 X位置 | 車体中心からの前後位置 | mm |
| 後輪 X位置 | 車体中心からの前後位置 | mm |
| 左右オフセット Y | タイヤ中心の左右位置（左右対称前提） | mm |
| 前輪 直径 | | mm |
| 前輪 幅 | | mm |
| 後輪 直径 | | mm |
| 後輪 幅 | | mm |

#### ▶ ピックボタン

3Dビューポートをクリックして座標を直接取得する。
- `[▶ FRONT X]` → 3D面クリックでX座標を前輪Xに設定
- `[▶ REAR X]`  → 3D面クリックでX座標を後輪Xに設定

技術メモ:
- ボタンクリック → `renderer.start_pick(callback)` で `_pick_active = True`
- vispy `canvas.events.mouse_press` → `_on_mouse` → カメラパラメータから射線計算 → `trimesh.ray.intersects_location`

---

### 03. ホイールベース調整 / ボディ設定

前後輪の位置情報を基に、車体を前後方向（X軸）にスケーリングする。

#### ユーザー入力パラメータ

| パラメータ | 説明 | 単位 |
|-----------|------|------|
| 目標ホイールベース | 実際のRCカーのホイールベース | mm |
| 肉厚 | シェルの厚み | mm |
| カット高さ | 地面からの高さ（0=自動） | mm |

---

### 04. 実行（Blender CLIサブプロセス）

- `params.json` にパラメータを書き出してBlender CLIを起動
- バックグラウンド処理中はプログレスバーを表示
- 完了後、`preview/result.stl` をビューポートに再読み込み
- エラー時はstderrをダイアログ表示

---

### 05. ゴミ（孤立メッシュ）の手動除去

- `loose_parts.json` から体積でソートした部品リストを表示
- ユーザーがリストで削除対象を選択して「Delete Selected Parts」ボタンを押す
- 削除後、再度Blenderプロセスを実行

---

### 06. STL書き出し

- 「Export STL…」ボタンで保存ダイアログを表示
- `preview/result.stl` を指定パスにコピー

---

## ユーザー動線

```
[1] python main.py で起動
      ↓
[2] 初回のみ: Blenderパスを自動検出 or 手動設定
      ↓
[3] Section 01: 「Open Model File…」でMeshyのモデルを選択
      → 3Dビューポートにモデル表示
      ↓
[4] Section 00: モデルの向きを確認
      → 必要なら [Z↑] [Flip] ボタンや手動回転で調整 → [✓ Apply]
      ↓
[5] Section 02: タイヤ位置・サイズを入力
      → ▶ ピックボタンで3Dモデルをクリックして座標を直接取得（推奨）
      → または数値直接入力
      ↓
[6] Section 03: 目標ホイールベース・肉厚・カット高さを入力
      ↓
[7] Section 04: 「Run Blender Process」ボタン → バックグラウンド処理（プログレス表示）
      ↓
[8] 処理完了 → ビューポートに結果プレビュー
      → Section 05: ゴミリストが表示 → 不要なものを選択して削除
      ↓
[9] Section 06: 「Export STL…」ボタンで保存
```

---

## パラメータ受け渡し（params.json）

```json
{
  "input_file": "/path/to/model.glb",
  "orientation": { "rx": 0.0, "ry": 0.0, "rz": 0.0 },
  "wheels": {
    "front_x": 85.0,
    "rear_x": -85.0,
    "offset_y": 45.0,
    "front_diameter": 52.0,
    "front_width": 26.0,
    "rear_diameter": 52.0,
    "rear_width": 26.0
  },
  "wheelbase_target": 170.0,
  "solidify": {
    "thickness": 1.5,
    "direction": "inner"
  },
  "cut_z": 10.0,
  "output_stl": "/path/to/preview/result.stl",
  "loose_json": "/path/to/preview/loose_parts.json",
  "remove_parts": []
}
```

---

## Blender CLI呼び出し

```python
import subprocess, json

def run_blender(blender_path: str, params: dict):
    with open("blender_scripts/params.json", "w") as f:
        json.dump(params, f)

    result = subprocess.run([
        blender_path,
        "--background",
        "--python", "blender_scripts/process_body.py"
    ], capture_output=True, text=True, timeout=300)

    return result.returncode, result.stdout, result.stderr
```

---

## 配布・実行ファイル化の方針

### 現在フェーズ（Python起動）

```bash
pip install -r requirements.txt
python main.py
```

### 将来フェーズ（実行ファイル化）

- **PyInstaller** でexe（Windows）/ app（macOS）化
- Blenderは同梱せず、初回起動時にパス指定（GPL回避）

```bash
pyinstaller --onefile --windowed main.py
```

---

## 制約・注意事項

- Meshyの生成モデルは品質にばらつきがあるため、ブーリアン演算が失敗する場合がある
  - 前処理として `bmesh.ops.remove_doubles` でメッシュ修復を自動実行する
- ポリゴン数が多い場合（>50K）は処理が重くなる
  - デシメーションモディファイア（比率50%程度）を前処理オプションとして提供する
- Blender 3.x と 4.x でbpy APIの差異があるためバージョンチェックを入れる
- 座標系: Blenderはメートル単位。UIはmm入力し、bpyスクリプト内で /1000 変換する

---

## 技術メモ

### vispy バックエンド

macOS では `pyopengltk`（tkinterバックエンド）がPython 3.13で動作しない（darwin実装なし）。
PySide6バックエンドを使用する。**QApplication 作成後に renderer.py をインポートすること**。

```python
# main.py 冒頭の順序が重要
_qapp = QApplication.instance() or QApplication(sys.argv)
from renderer import Renderer3D, HAS_VISPY   # この行が後
```

### レイキャスト（ピック機能）

`_screen_to_ray` はカメラパラメータ（azimuth, elevation, distance, fov, center）から
射線の原点とベクトルをnumpyで直接計算し、`trimesh.ray.intersects_location` に渡す。

### Blender 3.x / 4.x 対応

STL出力オペレーターが異なるため try/except でフォールバック。

```python
try:
    bpy.ops.wm.stl_export(filepath=output_path)      # Blender 4.x
except:
    bpy.ops.export_mesh.stl(filepath=output_path)    # Blender 3.x
```
