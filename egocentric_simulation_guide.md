# エゴ環境でのシミュレーション活用メモ

## 目的

エゴセントリックデータから生成したpseudo-actionや中間表現を、ロボットのFTに使う前にシミュレーションで検証・補正・フィルタする方法を整理する。

ここでの主眼は、エゴ環境そのものを完全に再現することではなく、**エゴ動画由来のactionが対象ロボットにとって実行可能かを確認すること**である。

---

## 1. 基本方針

エゴデータから得たpseudo-actionはノイズを含む。

```text

ノイズ要因:
  - 手や物体の遮蔽
  - カメラ同期ずれ
  - depth欠損
  - hand/object pose推定誤差
  - 人間とロボットの身体差
  - 手首軌道の急なジャンプ
  - グリッパ開閉タイミングの誤差

```

そのため、動画由来pseudo-actionをそのままFTに使うのではなく、シミュレーションで以下を確認する。

```text

確認すること:
  - IKが解けるか
  - ロボットの作業範囲内か
  - 関節制限を超えないか
  - 速度/加速度が現実的か
  - 衝突しないか
  - 対象物に届くか
  - pick/placeが成立しそうか
  - グリッパ開閉タイミングが妥当か

```

最初のシミュレーションの役割は、**学習環境**というより、**pseudo-actionの検証器・補正器・フィルタ**である。

---

## 2. エゴ環境をどこまで再現するか

エゴ環境を完全にデジタルツイン化するのは大変である。初期実験では、再現度を段階的に上げる。

### Level 1: 標準シミュレーション環境で検証

```text

再現するもの:
  - 対象ロボット
  - テーブル
  - 主要物体
  - おおまかな初期配置

目的:
  - pseudo-actionが実行可能か確認する
  - IK/衝突/到達可能性をチェックする
  - valid trajectoryだけFT候補に残す

```

最初はこれで十分である。テーブル上のpick and placeなら、既存のロボットシミュレーション環境で始められる。

### Level 2: エゴ収録環境を粗く再現

```text

追加で再現するもの:
  - テーブル高さ
  - 物体サイズ
  - 物体の初期配置
  - カメラ位置
  - ロボット作業範囲
  - 簡易的な照明・背景

目的:
  - エゴ動画から推定した座標とsim座標を対応させる
  - observation分布を少し近づける
  - pseudo-actionの空間スケールを確認する

```

この段階では、実環境を正確にスキャンしなくてもよい。実験台、物体、カメラ位置を近似できれば十分なことが多い。

### Level 3: 実環境のデジタルツイン

```text

再現するもの:
  - 3Dスキャン済み環境
  - 物体CAD/mesh
  - 正確なカメラpose
  - 物体pose
  - 照明
  - 摩擦・接触パラメータ

目的:
  - 実環境と近いobservationを生成する
  - sim-to-real gapを下げる
  - シミュレーション上でデータ拡張や方策学習を行う

```

これはコストが高い。最初から狙うより、Level 1/2でエゴ由来pseudo-actionの有効性が見えてから検討する。

---

## 3. 推奨パイプライン

```text

Step 1: エゴ/手元/depth動画を収録
  - 頭/首/胸depthカメラ
  - 腕/手元USBカメラ
  - 可能なら固定俯瞰カメラ
  - timestamp
  - 成功/失敗ラベル

Step 2: pseudo-actionを生成
  - hand/wrist trajectory
  - gripper open/close
  - target object ID
  - object coarse position
  - pick/place/release event
  - confidence/mask

Step 3: sim環境を準備
  - 対象ロボットURDF/MJCF
  - テーブル
  - 対象物
  - グリッパ
  - IK solver
  - collision checker

Step 4: pseudo-actionをsimで再生
  - end-effector target trajectoryを追従
  - gripper open/closeを再生
  - action chunk単位で評価
  - 失敗区間を記録

Step 5: 検証・補正・フィルタ
  - IK不能な軌道を除外
  - 関節制限違反を除外
  - 速度/加速度を平滑化
  - 衝突軌道を除外
  - 到達可能な軌道だけ残す
  - 必要なら軌道を補正する

Step 6: FT用データ化
  - observation
  - language instruction
  - validated pseudo-action
  - auxiliary labels
  - confidence/mask
  - sim validation result

Step 7: 少量実機データで確認
  - 通常テレオペFT baselineと比較
  - sim-filter済みpseudo-actionの効果を見る
  - 実機失敗モードを分析する

```

---

## 4. 既存シミュレーション環境・データ候補

### ManiSkill

- Link: https://arxiv.org/abs/2107.14483
- Project: https://maniskill.ai/

ロボット操作タスク向けのシミュレーションベンチマーク。pick and place、push、open/closeなどの操作タスク、RGB-D、点群、デモデータを扱える。

向いている用途:

```text

- テーブル上のpick/place
- RGB-D observationの検証
- ロボット手先actionの再生
- 既存タスク上でのFT/RL実験
- pseudo-actionのvalidity check

```

エゴ環境そのものではないが、最初の検証環境として使いやすい。

### RoboCasa / RoboCasa365

- Link: https://arxiv.org/abs/2603.04356
- Project: https://robocasa.ai/

家庭・キッチン系の大規模ロボット操作シミュレーション環境。RoboCasa365では多数のキッチン環境とタスク、デモデータを扱う。

向いている用途:

```text

- 家庭内/キッチン操作
- 長めの操作タスク
- 物体配置や環境バリエーションの検証
- エゴ由来タスクを家庭環境simへ写す実験

```

完全なエゴデジタルツインではないが、家庭内ロボットタスクの近似環境として使える。

### MimicGen

- Link: https://arxiv.org/abs/2310.17596
- Project: https://mimicgen.github.io/

少数の人間デモから、シミュレーション上で多様なロボットデモを生成する仕組み。

向いている用途:

```text

- 少数のvalid trajectoryを増やす
- sim上で軌道を再合成する
- エゴ由来pseudo-actionをseed trajectoryとして扱う
- デモの多様性を増やす

```

エゴ動画から直接データを作るものではないが、sim検証後のデータ拡張に使える。

### RoboSuite

- Link: https://robosuite.ai/
- Repository: https://github.com/ARISE-Initiative/robosuite

MuJoCoベースのロボット操作シミュレーション環境。Franka、Sawyer、Pandaなどの操作環境を扱いやすい。

向いている用途:

```text

- 対象ロボット固定の初期検証
- pick/place, lift, stackなどの基本タスク
- end-effector actionの再生
- IK/制御器/観測設計の検証

```

テーブル上タスクの簡易検証には扱いやすい。

### RLBench

- Link: https://arxiv.org/abs/1909.12271
- Repository: https://github.com/stepjam/RLBench

CoppeliaSimベースのロボット学習ベンチマーク。多数の操作タスクとデモを含む。

向いている用途:

```text

- 多様なタスクでの検証
- 言語指示付き操作
- タスク分解やサブタスク評価
- 観測視点の違いによる性能比較

```

エゴ環境再現というより、タスク多様性を使った検証に向く。

### Aria Digital Twin

- Link: https://arxiv.org/abs/2306.06362

Project Ariaで収録されたエゴセントリック3D知覚向けデータセット。6DoFデバイスpose、object 6DoF pose、depth、segmentation、synthetic renderingなどが含まれる。

向いている用途:

```text

- エゴ視点の3D知覚
- カメラposeとobject poseの扱い
- エゴ環境のデジタルツイン設計の参考
- synthetic renderingを含むデータ構成の参考

```

ロボット操作シミュレーターではないため、直接FT用action検証に使うには追加実装が必要。

### Ego-Exo4D

- Link: https://arxiv.org/abs/2311.18259
- Project: https://ego-exo4d-data.org/

一人称・三人称の同期動画、カメラpose、点群、IMU、視線、言語記述などを含む大規模データセット。

向いている用途:

```text

- エゴ/外部視点の同期データ設計
- マルチビュー収録の参考
- 人間動作と環境理解
- サブタスク・言語・視線の活用検討

```

ロボット操作sim環境ではないが、エゴ収録設計や同期データの扱いを考える上で参考になる。

### RoboTwin

- Link: https://arxiv.org/abs/2504.13059

実環境や画像からデジタルツイン的なロボット操作環境を作る方向の研究。双腕操作や複雑タスクに重点がある。

向いている用途:

```text

- 実環境に近いsim構築
- 複雑な操作環境のデジタルツイン化
- 画像/生成モデルを使った環境構築の参考

```

初期検証には重いが、将来的に実環境をsim化する際の参考になる。

---

## 5. 初期タスク選定

最初は、シミュレーションと実機の差が比較的小さいタスクを選ぶ。

```text

向いている:
  - pick and place
  - 物体を所定エリアに移動
  - ブロックを置く
  - 箱やカップなど大きめ物体
  - 2指グリッパで掴みやすい物体
  - 接触が単純なタスク

避けたい:
  - ケーブル操作
  - 布、袋、柔らかい物体
  - 透明/反射物体
  - 狭い差し込み
  - 力制御が必要な操作
  - 滑りや摩擦が支配的な操作

```

---

## 6. シミュレーションでの評価項目

pseudo-actionをsimで再生したら、以下を記録する。

```text

軌道レベル:
  - IK success rate
  - joint limit violation
  - velocity / acceleration violation
  - collision count
  - trajectory smoothness
  - end-effector tracking error

タスクレベル:
  - reach success
  - grasp success
  - lift success
  - place success
  - object displacement error
  - final state success

データレベル:
  - valid trajectory ratio
  - invalid reason distribution
  - confidenceと成功率の相関
  - 視点別ablation
  - sim-filter前後のFT性能差

```

このログは、エゴ動画からpseudo-actionを作る変換器の改善にも使える。

---

## 7. 現実的な最初の実験案

```text

対象:
  - 机上のpick and place
  - 2指グリッパの対象ロボット
  - 大きめで把持しやすい物体

収録:
  - 腕/手元USBカメラ
  - 頭/首depthカメラ
  - 可能なら固定俯瞰カメラ
  - timestamp同期
  - 成功/失敗ラベル

pseudo-action:
  - delta end-effector position
  - delta end-effector rotation
  - gripper open/close
  - confidence/mask
  - pick/place/release event

sim:
  - RoboSuite, ManiSkill, MuJoCo, PyBulletのいずれか
  - 対象ロボットモデル
  - テーブル
  - 対象物
  - IK/collision check

評価:
  - pseudo-actionのvalid率
  - invalid理由
  - sim-filter済みデータでFTしたときの成功率
  - 通常テレオペFT baselineとの比較

```

---

## 8. 結論

エゴ環境を完全にシミュレーション化するのは大変である。ただし、最初から完全なデジタルツインを狙う必要はない。

現実的な進め方は以下である。

```text

1. 標準的な机上操作simを用意する
2. エゴ動画由来pseudo-actionを再生する
3. IK、衝突、到達可能性、速度制限をチェックする
4. valid trajectoryだけFT候補に残す
5. 効果が見えたら収録環境を粗くsimへ近づける
6. 必要になってからデジタルツイン化を検討する

```

シミュレーションは、初期段階では**エゴ環境再現の場**ではなく、**動画由来actionの品質管理と安全な検証の場**として使うのがよい。

