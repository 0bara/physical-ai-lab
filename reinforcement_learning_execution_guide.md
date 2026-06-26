# 強化学習（Eureka）実行・データエクスポート手順書 (Gemma 4 対応版)

本手順書は、**Ubuntu環境**上でローカルに **Gemma 4** をサービングし、Isaac Labの強化学習を実行してVLAモデルの微調整に必要な「動作データセット」をエクスポートする手順を解説します。

---

## 🛠️ ステップ 1: ローカルLLM (Gemma 4) の起動

Ubuntuサーバー上で、ローカルLLMをサービングする **Ollama (v0.20.0以上)** を使用して Gemma 4 を起動します。

### 1. Ollamaのインストールとアップデート (Ubuntu)
Gemma 4 のアーキテクチャをサポートするため、最新バージョンのOllamaをインストールします。
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 1.5 VRAM常駐解放の設定 (RTX 4090 1枚での共存対策)
OllamaはデフォルトでモデルをVRAMに常駐させます。シミュレータ起動時のVRAM OOMを防ぐため、回答後に即座にVRAMを解放する環境変数を設定した上で、Ollamaサービスを起動（または再起動）します。
```bash
# 環境変数を追加
export OLLAMA_KEEP_ALIVE=0

# Ollamaサービスの再起動 (systemd経由の場合)
sudo systemctl set-environment OLLAMA_KEEP_ALIVE=0
sudo systemctl restart ollama
```

### 2. Gemma 4 モデルの選択と取得 (Pull)
RTX 4090 (24GB VRAM) 1枚の環境で **「シミュレータ」と「ローカルLLM」を同時に動かす** 場合、VRAM容量の配分（VRAM予算）を意識する必要があります。

*   **VRAM予算の考え方 (RTX 4090 24GB内訳)**
    *   **Isaac Lab (シミュレータ)**: 並列環境数にもよりますが、通常 **4GB〜10GB** のVRAMを消費します。
    *   **残りのVRAM (14GB〜20GB)** をLLMの起動とコンテキストキャッシュに割り当てます。

マシンの負荷と目的に応じて、以下のいずれかのモデルをプルします。

```bash
# 推奨構成①: gemma4:26b (高速MoEモデル)
# VRAM消費: 約 14GB〜16GB (Q4量子化版)
# アクティブなパラメータ数が4Bのため、推論が非常に高速です。Isaac Lab用のVRAM (8-10GB) も十分に確保できます。
ollama pull gemma4:26b

# 推奨構成②: gemma4:12b (ワークステーション向け軽量モデル)
# VRAM消費: 約 8GB〜10GB
# 最も軽量かつVRAM消費が少ないため、シミュレータの並列数 (num_envs) を増やしてもVRAM OOM (メモリ不足) になりにくく、極めて安定します。
ollama pull gemma4:12b

# 特殊構成③: gemma4:31b (最強推論・コーディングモデル)
# VRAM消費: 約 18GB〜20GB
# 単体でVRAMの大部分を占有するため、1枚のRTX 4090で動かす場合は、シミュレータの環境数 (num_envs) を少なく設定する (例: 512以下) か、
# Ollamaに一部のレイヤーをCPUにオフロードさせる設定が必要です。
ollama pull gemma4:31b
```

### 3. APIサーバーの起動確認
Ollamaはデフォルトで OpenAI 互換のAPIエンドポイントを `http://localhost:11434/v1` で提供します。
```bash
curl http://localhost:11434/v1/models
# 取得した gemma4 モデル名が含まれるJSONが返ってくれば成功です
```

---

## ⚙️ ステップ 2: IsaacLabEureka のローカルLLM接続設定

`IsaacLabEureka` をローカルの Ollama に接続するために、環境変数を設定します。

### 1. 環境変数の設定 (接続先の偽装)
OpenAI APIクライアントに対し、ローカルのOllamaに向き先を変更させます。
```bash
export OPENAI_BASE_URL="http://localhost:11434/v1"
export OPENAI_API_KEY="ollama"  # 認証用ダミーキー
```

### 2. コンテキスト長 (Context Window) の拡張設定
Eurekaはシミュレータ環境のコード全体や学習の履歴をLLMに渡すため、大きなコンテキスト窓が必要です。Gemma 4 (12B/26B/31B) は最大 **256K** トークンに対応しているため、Ollamaのパラメータを拡張します。

Ollamaにカスタムパラメータを設定するため、プロジェクトフォルダ内に `Modelfile` を作成します（ここでは推奨の 26b を例にします）：
```dockerfile
# Modelfile
FROM gemma4:26b # または gemma4:12b / gemma4:31b
PARAMETER num_ctx 131072 # 128Kトークンに設定（必要に応じて262144まで拡張可能）
```

上記ファイルを保存し、新しいタグとして登録します：
```bash
ollama create gemma4:26b-128k -f Modelfile
```

---

## 🚀 ステップ 3: Eurekaによる強化学習の実行

アームタスクを指定し、ローカルの Gemma 4 モデルを使って報酬関数の進化探索を実行します。

```bash
# 26b-128k モデルを指定し、5世代の最適化を実行
python eureka.py \
  --task Isaac-Reach-Franka-v0 \
  --model gemma4:26b-128k \
  --num_iterations 5
```

### 🧠 Gemma 4 採用によるメリット
*   **思考モード (`<|think|>`)**: 
    学習結果（成功率やトルク）をフィードバックした際、Gemma 4は自動的に「推論ステップ（思考）」を挟んでからプログラムを書き換えます。これにより、「なぜその報酬設計にしたか」の論理的破綻が大幅に減少します。
*   **128K/265K コンテキスト**:
    長い環境コードを省略することなく丸ごと入力できるため、LLMが変数名やAPIを見失うことによる文法エラー（Syntax Error）がほぼ発生しません。

---

## 📊 ステップ 4: 成果物（ポリシー）の確認と選定

すべてのイテレーションが完了すると、`outputs/` ディレクトリ内に以下のデータが保存されます。

*   **`outputs/eureka/`**: Gemma 4が書いた各世代の報酬関数コード (`reward_v1.py` など) と、LLMの思考プロセス (`response_iter_N.txt`)。
*   **`logs/rl_training/`**: 強化学習のウェイト（チェックポイント `.pt` ファイル）や TensorBoard のログ。

**TensorBoardでログを確認する**:
```bash
tensorboard --logdir logs/rl_training/
# ブラウザから http://localhost:6006 にアクセスして成功率や報酬の推移グラフを確認します
```
最も成功率が高く、かつ関節トルク（エネルギー消費）が低い世代のモデルチェックポイント（例: `model_best.pt`）を特定します。

---

## 📥 ステップ 5: VLA微調整用「動作データセット」のエクスポート

選定した最高のポリシーをシミュレータ内で動作させ、VLAモデルの模倣学習（FT）に必要な「お手本データ」としてエクスポートします。

```bash
# 選択した最高ポリシーを「デモ記録モード」で実行し、HDF5形式のデータを保存します
python play.py \
  --task Isaac-Reach-Franka-v0 \
  --checkpoint logs/rl_training/iter_3/model_best.pt \
  --num_episodes 1000 \
  --record_dataset
```
生成された `demo_dataset.hdf5` ファイル（画像・関節アクション・言語指示のペア）を、OpenVLAなどのVLAモデルの微調整に入力します。

---

## 📊 トークン使用量の記録とクラウド移行コストの見積もり方法

クラウド（Gemini や GPT-4 など）への移行コストを正確に見積もるために、ローカル（Ollama）実行時のトークン消費数を自動記録する仕組みを用意しておくと便利です。

### 1. Ollama のシステムログから集計する（最も手軽な方法）
コードを変更したくない場合、UbuntuのシステムログからOllamaの実行ログを抽出してトークン数を集計できます。
```bash
# Ollamaのログからトークン評価数（入力・出力）を抽出して表示
journalctl -u ollama --since "today" | grep -E "prompt_eval_count|eval_count"
```
これにより、過去に実行した各APIコールのトークン数を回収できます。

### 2. Eurekaのソースコードに記録処理を組み込む方法
`eureka.py` などのLLMを呼び出している部分に数行のコードを追加し、実行フォルダ内に `token_usage_log.csv` を自動出力・蓄積させます。

**追加コードのイメージ (OpenAI API呼出部周辺):**
```python
import csv
import os

# APIのレスポンスを取得
response = client.chat.completions.create(...)

# --- トークン数記録用のコード（ここを追加） ---
token_log_file = os.path.join(output_dir, "token_usage_log.csv")
file_exists = os.path.isfile(token_log_file)

with open(token_log_file, mode="a", newline="") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(["Iteration", "Input_Tokens", "Output_Tokens", "Total_Tokens"])
    writer.writerow([
        iteration, 
        response.usage.prompt_tokens, 
        response.usage.completion_tokens, 
        response.usage.total_tokens
    ])
# ---------------------------------------------
```
これを組み込むことで、強化学習のイテレーションごとに消費されたトークン数がCSV形式で自動保存されます。

### 3. クラウド移行コストの計算例
蓄積したCSVの合計値を用いて、クラウドAPIの想定コストを算出します。

*   **計算式**:
    $$\text{合計コスト} = \left( \frac{\text{合計入力トークン}}{1,000,000} \times \text{入力単価} \right) + \left( \frac{\text{合計出力トークン}}{1,000,000} \times \text{出力単価} \right)$$

*   **Gemini 1.5 Pro（128Kコンテキスト未満）での見積もり例**:
    *   入力単価: \$1.25 / 100万トークン
    *   出力単価: \$5.00 / 100万トークン
    *   *(例: 1世代あたり入力 8万トークン、出力 2千トークンで 5世代（計25回試行）した場合)*
        *   総入力: 2,000,000 トークン ➡️ \$2.50
        *   総出力: 50,000 トークン ➡️ \$0.25
        *   **想定合計コスト: 約 \$2.75 / 1回あたり（約400円）**

このように、事前にローカルで回すことでコスト感を高精度に把握し、予算設計を行うことができます。

---

## 💡 補足: 1枚のGPU (RTX 4090 24GB) におけるVRAM常駐と実行時間のトレードオフ


1台のGPUでローカルLLMとシミュレータを動かす場合、VRAMの管理方法によって以下のような実行時間と推論精度のトレードオフが発生します。

### 1. ロード・アンロード方式（推奨・デフォルト設定）
Ollamaの `OLLAMA_KEEP_ALIVE=0` を設定し、LLMの呼び出し完了直後にVRAMを解放する方式です。
*   **メリット**: `gemma4:26b` (MoE) や `gemma4:31b` のような高機能なLLMを動かしつつ、シミュレータ側でも十分な数の並列アーム (例: 1024〜4096台) を走らせることができます。
*   **時間への影響**: LLMのロード時に数秒 (RTX 4090 + 高速NVMe SSD環境で約3〜5秒) のオーバーヘッドが発生しますが、1世代の強化学習 (10〜20分) に対して無視できるほど小さいため、全体の開発時間は最も短縮されます。

### 2. LLM常駐方式（モデルサイズ制限）
Ollamaの `OLLAMA_KEEP_ALIVE=-1` を設定し、LLMを常にVRAMにロードしたままにする方式です。
*   **メリット**: ロード時間が一切発生せず、シミュレータ実行中でもLLMへのAPIアクセスが即座に行えます。
*   **必要となる調整**: `gemma4:12b` (約8GB) のような比較的軽量なモデルを使用するか、シミュレータ側の並列環境数 (`num_envs`) を減らしてVRAMの競合を回避する必要があります。
*   **時間への影響**: 軽量なモデルを採用することでLLMの推論（報酬の自動改善力）が若干低下するか、またはシミュレータの並列数を減らすことで強化学習の収束が遅くなり（例: 学習時間が10分から30分に伸びる）、結果として全体の作業時間が増加する可能性があります。

プロジェクトの進行ステージやタスクの難易度に応じて、これらを切り替えて最適な構成を見つけてください。
