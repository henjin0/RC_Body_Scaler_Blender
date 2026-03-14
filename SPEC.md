# RC_Body_Scaler_Blender - SPEC.md

## 概要

Meshyで生成した車の3DモデルからラジコンRCカー用ボディを作成するデスクトップGUIツール。
**PySide6** でUIを提供し、**vispy（OpenGL）** で3Dモデルをリアルタイム表示する。
Blender（bpy）をサブプロセスとして呼び出してSTLを出力する。

---

## 実装状況（2026-03-14時点）

| 機能 | 状態 | 備考 |
|------|------|------|
| PySide6 UI（ダーク/ライトテーマ） | ✅ 実装済み | |
| vispy OpenGL 3Dビューポート | ✅ 実装済み | PySide6バックエンド |
| ソリッド/透過/ワイヤーフレーム表示切替 | ✅ 実装済み | |
| モデルファイル読み込み（GLB/OBJ/STL/FBX） | ✅ 実装済み | |
| タイヤ位置・カット高さのビジュアライズ | ✅ 実装済み | 円柱+カット平面 |
| Blender自動検出 | ✅ 実装済み | macOS/Windows/Linux |
| Blender CLIによるSTL生成（フルパイプライン） | ✅ 実装済み | タイヤ除去→WBスケール→幅高さスケール→Solidify→底面カット |
| タイヤカットのみモード（テスト用） | ✅ 実装済み | mode="tire_cut_only" |
| ▶ ピックボタン（3D面クリックで座標取得） | ✅ 実装済み | カメラ行列ベースのレイキャスト |
| モデル向き調整（初期回転） | ✅ 実装済み | Section 00 |
| 結果モデルのテールオーバーレイ表示 | ✅ 実装済み | 結果ロード時は元モデルを非表示 |
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
│                                  │   [Reset][FlipX][→X]    │
│                                  │   [✓ Apply Rotation]    │
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
│                                  │   カット径 前 [52] mm     │
│                                  │   Front Width [26] mm    │
│                                  │   カット径 後 [52] mm     │
│                                  │   Rear Width [26] mm     │
│                                  │   RC径 前 [52] mm        │
│                                  │   RC径 後 [52] mm        │
│                                  │   [▶ FRONT X][▶ REAR X] │
│                                  │   現在のWB: xxx mm       │
│                                  ├──────────────────────────┤
│                                  │ 03  BODY                 │
│                                  │   Target WB [170] mm     │
│                                  │   Body Width [190] mm    │
│                                  │   Body Height [100] mm   │
│                                  │   Thickness [ 1.5] mm    │
│                                  │   Cut Z     [ 10] mm     │
│                                  │   [▶ PICK CUT Z]         │
│                                  ├──────────────────────────┤
│                                  │ 04  EXECUTE              │
│                                  │   [▶ Blender で処理を実行]│
│                                  │   [🔧 タイヤカットのみ]  │
│                                  │   ████░░ 処理中...       │
│                                  │   [✕ 結果オーバーレイをクリア] │
│                                  ├──────────────────────────┤
│                                  │ 05  CLEANUP              │
│                                  │   Part_001  vol: 1234mm³ │
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
| [+90 X/Y/Z] ボタン | 対応軸に90°追加して即適用 |
| [Reset] ボタン | 回転をリセット（0,0,0） |
| [Flip X] ボタン | 上下反転（X軸に180°） |
| [→X] ボタン | Y軸に90°（横倒しモデル起こし） |
| [✓ Apply Rotation] ボタン | 回転を頂点座標に適用して再描画 |

#### 内部処理

```python
def apply_rotation(self, rx_deg, ry_deg, rz_deg):
    # 回転行列をnumpyで構築し、_orig_vertsに適用
    # _verts, _trimesh, _refresh_mesh()を更新
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

#### パラメータ概念

| パラメータ | 説明 | 単位 |
|-----------|------|------|
| Front X | 前輪中心のX位置（ピックまたは手入力） | mm |
| Rear X | 後輪中心のX位置 | mm |
| Y Offset | タイヤ中心の左右位置（モデルZ中心からのオフセット） | mm |
| カット径（前/後） | Blenderブーリアンで使うシリンダー直径（実際の切り抜きサイズ） | mm |
| Front/Rear Width | シリンダーの奥行き（車体を貫通する深さ。自動設定） | mm |
| RC径（前/後） | 3Dビューポート表示用の参照円（Blender処理には使わない） | mm |

> **注意**: Y Offset が車幅の35%未満の場合、自動的に `車幅×0.35` に補正される。
> タイヤ中心Y（高さ）は ▶FRONT X / ▶REAR X ピック時に自動取得される。未設定時は自動推定。

#### ▶ ピックボタン

3Dビューポートをクリックして座標を直接取得する。
- `[▶ FRONT X]` → SIDEビューでクリック → X座標=前輪X、Y座標=タイヤ中心高さ
- `[▶ REAR X]`  → SIDEビューでクリック → X座標=後輪X、Y座標=タイヤ中心高さ

---

### 03. ボディ設定

#### ユーザー入力パラメータ

| パラメータ | 説明 | 単位 |
|-----------|------|------|
| Target WB | 目標ホイールベース（RCカーの実寸） | mm |
| Body Width | 目標ボディ幅（RCカーの規格幅） | mm |
| Body Height | 目標ボディ高さ | mm |
| Thickness | シェルの壁厚（Solidifyモディファイア） | mm |
| Cut Z | 底面カット高さ（モデルY座標。0=自動=下10%カット） | mm |

---

### 04. 実行（Blender CLIサブプロセス）

#### フルパイプライン（mode="full"）

1. モデルインポート + 向き調整
2. メッシュ修復（remove_doubles）
3. デシメーション（ポリゴン数 > 50K の場合、ratio=0.5）
4. **タイヤ除去**（前後左右4本のシリンダーブーリアン差分、EXACTソルバー）
5. **ホイールベーススケール**（X軸方向: `scale_x = target_wb / current_wb`）
6. **ボディ幅スケール**（Z軸方向: `scale_z = target_width / cur_width`）
7. **ボディ高さスケール**（Y軸方向: `scale_y = target_height / cur_height`）
8. **Solidify**（内側方向に `thickness` mm の壁を生成、モデルを中空にする）
9. **底面カット**（`cut_z` 以下をボックスブーリアン差分で切り落とす）
10. loose parts分離 → `loose_parts.json` 出力
11. 最大体積オブジェクトを `preview/result.stl` として出力

#### タイヤカットのみ（mode="tire_cut_only"）

ステップ1〜4のみ実行して出力。スケール・Solidify・底面カットはスキップ。
パラメータ調整のテストに使う。

#### 処理完了後の表示

- result.stl をビューポートにロード → **テール色（緑がかった青）のオーバーレイ**で表示
- 元モデルは非表示（結果のみ表示）
- **カット径の黄色い円**のみ表示（RC径は非表示）
- 「✕ 結果オーバーレイをクリア」ボタンが出現

---

### 05. ゴミ（孤立メッシュ）の手動除去

- `loose_parts.json` から体積でソートした部品リストを表示（単位: mm³）
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
      → 必要なら [+90X] [Flip X] ボタンや手動回転で調整 → [✓ Apply Rotation]
      ↓
[5] Section 02: タイヤ位置・サイズを入力
      → ▶ FRONT X / ▶ REAR X ピックでタイヤ軸座標を取得
      → カット径（前/後）を実物タイヤサイズに合わせて設定
      → [🔧 タイヤカットのみ] でプレビュー確認（推奨）
      ↓
[6] Section 03: 目標WB・ボディ幅高さ・肉厚・カット高さを入力
      → ▶ PICK CUT Z でボディ底面の高さをクリック指定
      ↓
[7] Section 04: 「▶ Blender で処理を実行」→ バックグラウンド処理（プログレス表示）
      ↓
[8] 処理完了 → ビューポートにテール色の結果モデル表示
      → Section 05: ゴミリストが表示 → 不要なものを選択して削除
      ↓
[9] Section 06: 「Export STL…」ボタンで保存
```

---

## パラメータ受け渡し（params.json）

```json
{
  "input_file": "/path/to/model.glb",
  "mode": "full",
  "orientation": { "rx": 0.0, "ry": 0.0, "rz": 0.0 },
  "wheels": {
    "front_x": 85.0,
    "rear_x": -85.0,
    "offset_y": 45.0,
    "front_diameter": 52.0,
    "front_width": 26.0,
    "rear_diameter": 52.0,
    "rear_width": 26.0,
    "front_cy": null,
    "rear_cy": null
  },
  "wheelbase_target": 170.0,
  "body_target": {
    "width_mm": 190.0,
    "height_mm": 100.0
  },
  "solidify": {
    "thickness": 1.5,
    "direction": "inner"
  },
  "cut_z": 10.0,
  "remove_parts": []
}
```

> **`front_cy` / `rear_cy`**: タイヤ中心のY座標（高さ）。null の場合はバウンディングボックスから自動推定。
> ▶ FRONT X / ▶ REAR X ピック時に自動設定される。

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
  - デシメーションモディファイア（比率50%程度）を前処理として自動適用する
- Blender 3.x と 4.x でbpy APIの差異があるためバージョンチェックを入れる
- ブーリアン演算は EXACT ソルバーを優先し、失敗時に FAST ソルバーへフォールバック

---

## 技術メモ

### 座標系・単位

**重要**: STLファイルはmm値のままBlenderにインポートされる。
例: 車体X幅 549mm のモデルは、Blender内でX座標 0〜549 として扱われる。

- vispy内座標 = mm値
- Blender内座標 = mm値（同一の数値）
- `/1000` 変換は**不要**（過去バージョンの誤り）
- `global_scale=1.0` で STL エクスポート（`global_scale=1000` は誤り）

座標軸の対応（向き調整適用後の標準状態）:
| 軸 | 意味 |
|----|------|
| X | 前後方向（前が正） |
| Y | 上下方向（上が正） |
| Z | 左右方向（幅） |

タイヤシリンダーはZ軸方向（左右）に向けて配置する。

### タイヤZ位置の自動補正

`offset_y` が車体Z幅の35%未満の場合、タイヤ位置として不合理と判断し自動補正:
```python
min_reasonable = car_z_extent * 0.35
if offset_z < min_reasonable:
    offset_z = min_reasonable
```

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
    bpy.ops.wm.stl_export(filepath=output_path, global_scale=1.0)  # Blender 4.x
except:
    bpy.ops.export_mesh.stl(filepath=output_path, global_scale=1.0)  # Blender 3.x
```

### 結果表示（renderer.py）

- 結果ロード時: 元モデルを非表示、テール色（teal: `#00e1b8`）の結果メッシュを表示
- `update_viz()` で結果ロード中はカット径（黄色）のみ表示。RC径は非表示。
- カット径はスケーリング前の入力値で描画（Blender処理と同じパラメータ）
