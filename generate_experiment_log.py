#!/usr/bin/env python3
import os
import json
import csv
import urllib.request
from datetime import datetime

# ==========================================
# 設定パラメータ
# ==========================================
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gemma4:26b" # または gemma4:12b
GEMINI_INPUT_RATE_1M = 1.25   # Gemini 1.5 Pro 入力単価 ($/100万トークン)
GEMINI_OUTPUT_RATE_1M = 5.00  # Gemini 1.5 Pro 出力単価 ($/100万トークン)

def load_token_usage(output_dir):
    """CSVからトークン使用履歴を読み込む"""
    csv_path = os.path.join(output_dir, "token_usage_log.csv")
    if not os.path.exists(csv_path):
        return None, 0, 0, 0
    
    records = []
    total_in, total_out, total_tokens = 0, 0, 0
    try:
        with open(csv_path, mode='r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
                total_in += int(row.get("Input_Tokens", 0))
                total_out += int(row.get("Output_Tokens", 0))
                total_tokens += int(row.get("Total_Tokens", 0))
    except Exception as e:
        print(f"[警告] CSV読み込み失敗: {e}")
    return records, total_in, total_out, total_tokens

def load_run_stats(output_dir):
    """Eurekaの各世代のパフォーマンス統計（JSON等）があれば読み込む"""
    stats_path = os.path.join(output_dir, "stats.json")
    if os.path.exists(stats_path):
        try:
            with open(stats_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[警告] 統計JSON読み込み失敗: {e}")
    return {}

def call_local_llm(prompt, model):
    """Ollamaを呼び出してレポートを生成させる"""
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    req = urllib.request.Request(
        OLLAMA_URL, 
        data=json.dumps(data).encode('utf-8'), 
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            return res.get("response", "")
    except Exception as e:
        print(f"[エラー] Ollamaとの通信に失敗しました: {e}")
        return None

def main():
    # 実行パスの設定 (必要に応じて引数等で変更可能にしてください)
    output_dir = "outputs"
    task_name = "Isaac-Reach-Franka-v0" # 対象タスク名
    
    print("🤖 実験ログ自動生成スクリプトを起動します...")
    
    # 1. データの読み込み
    token_records, total_in, total_out, total_all = load_token_usage(output_dir)
    run_stats = load_run_stats(output_dir)
    
    # クラウドコストの計算
    cost_in = (total_in / 1_000_000) * GEMINI_INPUT_RATE_1M
    cost_out = (total_out / 1_000_000) * GEMINI_OUTPUT_RATE_1M
    total_cost = cost_in + cost_out
    
    # 2. LLMへのプロンプト（指示）の組み立て
    raw_data_summary = f"""
=== 実行生データ ===
- タスク名: {task_name}
- 実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 総入力トークン: {total_in:,}
- 総出力トークン: {total_out:,}
- 合計トークン: {total_all:,}
- 想定クラウド移行コスト（Gemini 1.5 Proベース）: ${total_cost:.4f} (約{int(total_cost * 150)}円)

- 世代別トークン詳細:
{json.dumps(token_records, indent=2)}

- 世代別シミュレーションスコア（成功率/トルク等）:
{json.dumps(run_stats, indent=2)}
"""

    prompt = f"""
あなたは強化学習（Eureka）の実験サマリーを作成する優秀なAIアシスタントです。
以下の実行生データ（タスク、世代別スコア、トークン数など）を読み解き、整理されたMarkdown形式の実験ログ報告書を作成してください。

必要に応じて、どの世代（Iteration）が最も成功率とエネルギー効率のバランスが良いか、およびクラウド移行時のコスト所感を「考察」として文章で補足してください。

{raw_data_summary}

出力フォーマットは、以下の見出し構造に沿って日本語で記述してください：
# 実験ログ / 実行サマリー [タスク名] - [実行ID]
## 📅 1. 実験基本情報 (日時、タスク概要、ハードウェア等)
## ⚙️ 2. 実行規模 (LLMモデル、世代数、所要時間等)
## 🏆 3. 学習結果と最終成果物 (世代ごとの成功率・トルク比較表、ベストポリシーのファイル名など)
## 🪙 4. トークン消費量とクラウドコスト見積もり (Gemini換算)
## 📝 5. 考察と次のステップ (LLMとしての動作分析や課題)
"""

    print("🧠 ローカルLLM (Ollama) にレポート作成を指示しています...")
    report = call_local_llm(prompt, DEFAULT_MODEL)
    
    if not report:
        print("❌ レポート生成に失敗しました。Ollamaが起動しているか確認してください。")
        return
    
    # 3. ファイルへの保存
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"experiment_log_{task_name}_{timestamp}.md"
    log_path = os.path.join(output_dir, log_filename)
    
    os.makedirs(output_dir, exist_ok=True)
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(report)
        
    print(f"🎉 自動生成された実験ログを保存しました: {log_path}")

if __name__ == "__main__":
    main()
