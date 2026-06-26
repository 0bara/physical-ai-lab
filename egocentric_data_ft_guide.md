# エゴセントリックデータのFT活用検討メモ

## 目的

VLA（Vision-Language-Action）モデルやロボット方策のファインチューニング（FT）に、エゴセントリックデータをどう活用できるかを整理する。

ここでの主眼は、エゴデータを単なる事前学習用動画として扱うのではなく、**FTに使えるデータ源としてどう設計・収録・変換・評価するか**である。

---

## 1. 基本的な考え方

通常のテレオペレーションによるFTデータ収録では、対象ロボットの観測とアクションが直接得られる。

```text

ロボット observation
+ ロボット action
+ 言語指示
→ そのままFTに利用

```

一方、エゴセントリックデータでは、人間の視点・手・身体運動が得られるが、それは対象ロボットの観測・アクションとは一致しない。

```text

人間の頭/首/胸カメラ
+ 手カメラ
+ 俯瞰/監視カメラ
→ 人間の意図・手元操作・環境状態は得られる
→ ただしロボットの action そのものではない

```

そのため、FTに使うには大きく2つの方針がある。

1. **対象ロボット固定で直接変換する**
    - まず1台のロボットに絞る。
    - エゴデータを対象ロボットの observation/action に近づける。
    - 通常テレオペFTよりデータ効率や汎化が改善するかを見る。

2. **中間表現に変換してからロボットごとに適応する**
    - 人間データをロボット非依存、または弱依存の表現に変換する。
    - 例: wrist trajectory, grasp state, object pose, contact event, subtask label, latent action token。
    - その後、各ロボットごとにIK、retargeting、adapter、LoRA、少量FTで合わせる。

初期検証では、いきなり中間表現を完成させるより、**対象ロボット固定で効果を確認し、効果が見えたら中間表現化する**方が現実的である。

---

## 2. 理想的なデータ収録構成

FT用途では、純粋なエゴ視点だけでは不十分になりやすい。特に、把持・接触・物体移動の瞬間は手や物体で遮蔽される。

そのため、実用的には **エゴ中心のマルチビュー人間デモデータ** として設計する。

```text

頭/首/胸カメラ:
  - 作業者が見ている対象
  - 意図、注視、作業文脈
  - サブタスクの流れ

手首/手元カメラ:
  - 接触直前の局所状態
  - 把持点
  - 位置合わせ
  - 細かい手元操作

俯瞰/監視カメラ:
  - 作業空間全体
  - 物体配置
  - 大域的な手/物体軌道
  - エゴ視点の遮蔽補完
  - 失敗、落下、衝突の検出

```

低解像度の監視カメラでも、役割を限定すれば有用である。

```text

低解像度俯瞰でも使える:
  - 対象物ID
  - 物体のおおまかな位置
  - 手がどの物体へ接近したか
  - サブタスク境界
  - 失敗/落下/衝突
  - エゴ視点で隠れた区間の補完

低解像度俯瞰では厳しい:
  - 指先の接触点
  - 精密な把持姿勢
  - 小物体の6DoF姿勢
  - 透明物体、ケーブル、薄い部品
  - 力、滑り、微小な回転

```

重要なのは解像度だけではなく、**固定視点、時刻同期、作業領域全体の可視性、簡易キャリブレーション**である。

---

## 3. FT向けの理想パイプライン

理想的には、以下のような流れになる。

```text

Step 1: 人間デモ収録
  - 頭/首/胸カメラ
  - 手首/手元カメラ
  - 俯瞰/監視カメラ
  - 言語指示またはタスクラベル
  - 成功/失敗ラベル

Step 2: 時刻同期とキャリブレーション
  - カメラ間の時刻同期
  - カメラ内部パラメータ
  - 外部カメラの作業台座標への対応
  - 必要に応じて手首/頭部IMUや深度を追加

Step 3: 状態・イベント抽出
  - 対象物ID
  - 手/手首軌道
  - 把持/open-close状態
  - 物体の粗い位置
  - 接触イベント
  - サブタスク境界
  - 成功/失敗

Step 4: 初期段階では対象ロボット用データへ変換
  - 対象ロボットの観測形式に合わせる
  - 対象ロボットのactionに近い疑似ラベルを作る
  - 既存テレオペデータと混ぜる

Step 5: VLA/ポリシーをFT
  - 通常テレオペのみをbaselineにする
  - エゴ/手/俯瞰を追加した条件と比較
  - 各視点のablationを行う

Step 6: 効果が見えたら中間表現へ移行
  - wrist/end-effector trajectory
  - grasp state
  - object state
  - contact event
  - subtask label
  - latent action token

Step 7: 複数ロボット対応
  - 共通中間表現
  - ロボット別adapter/LoRA
  - IK/retargeting
  - 少量ロボットデモでFT

```

---

## 4. 段階的な進め方

### Phase 1: 対象ロボット固定で実験する

最初は汎用中間表現を狙いすぎない。

```text

目的:
  エゴ由来データが、対象ロボットのFTに効くか確認する。

比較:
  A. 通常テレオペデータのみ
  B. テレオペ + 頭/首カメラ由来データ
  C. テレオペ + 手カメラ由来データ
  D. テレオペ + 俯瞰カメラ由来データ
  E. テレオペ + 全視点

評価:
  - 成功率
  - 必要デモ数
  - 未知配置への汎化
  - 未知物体への汎化
  - 長ホライズンタスクでの崩れ方
  - 失敗モード

```

ここで見るべき問いは、エゴデータが「単にノイズを増やす」のか、「データ効率・タスク意味理解・視点ロバスト性を改善する」のかである。

### Phase 2: 中間表現を導入する

対象ロボット固定で効果が出たら、中間表現を導入する。

```text

最初に狙う中間表現:
  - target object ID
  - wrist/end-effector trajectory
  - grasp open-close state
  - object coarse position
  - subtask boundary
  - success/failure label

余裕があれば狙う中間表現:
  - object 6DoF pose
  - contact event
  - grasp point
  - force/slip proxy
  - dense hand pose

```

初期段階では、精密な6DoFや接触点よりも、**粗いが安定して取れる表現**を優先する。

### Phase 3: 複数ロボットへ拡張する

中間表現が安定したら、複数ロボット対応を検討する。

```text

構成案:
  共通VLA backbone
  + 共通中間Action表現
  + ロボット別adapter/LoRA
  + ロボット別IK/retargeting
  + 少量ロボット固有FT

```

この段階で初めて、ACE-Ego-0のような camera-space action、morphology conditioning、time-aligned action chunking が重要になる。

---

## 5. 確立度の整理

現時点では、すべてが確立済みというより、部品技術と研究プロトタイプが組み合わさっている段階である。

| 項目 | 確立度 | コメント |
| :--- | :--- | :--- |
| 手・身体・物体検出 | 高め | 既存CVモデルや手トラッキングで実用可能。ただし遮蔽と小物体に弱い。 |
| カメラキャリブレーション/SLAM | 高め | 技術としては成熟。運用では同期・設置・照明が効く。 |
| 人間手軌道からロボットへのretargeting | 中 | 実装例は多いが、ロボット形状・タスク・把持方式に依存する。 |
| エゴ+手+俯瞰からFT用中間表現を自動抽出 | 低〜中 | 研究段階。標準パイプラインはまだない。 |
| 中間表現を用いた複数ロボット汎化 | 低〜中 | 有望だが、Action空間・時間スケール・身体差の扱いが難しい。 |

---

## 6. エゴデータをFT可能なデータへ変換する方法

エゴデータをFTに使うには、映像をそのまま投入するだけでは不十分である。多くの場合、以下のいずれかの形に変換する必要がある。

```text

変換後のデータ例:
  - ロボットactionに近い疑似action
  - wrist/end-effector trajectory
  - hand pose / grasp state
  - object pose / object state
  - contact event
  - subtask boundary
  - latent action token
  - morphology-agnostic state

```

現時点で使われている変換方法は、大きく次の6系統に分けられる。

### 6.1 手・手首軌道を推定してIK/retargetingする

最も分かりやすい方法は、人間の手・手首の3D軌道を推定し、それをロボットのエンドエフェクタや手指へ変換する方法である。

```text

エゴ/手元映像
→ 2D/3D hand landmarks
→ wrist pose / hand pose
→ ロボット座標系へ変換
→ IK / retargeting
→ ロボットactionまたは疑似action

```

利用できる部品:

```text

- 2D/3D hand landmark検出
- RGB-Dによる3D復元
- MANO hand model
- wrist pose推定
- IK
- gripper開閉への幾何変換
- human handからrobot handへのretargeting

```

この系統は、対象ロボットが単腕グリッパであれば比較的始めやすい。一方、dexterous handや接触リッチな操作では、人間手とロボット手の形状差が大きく、接触点・力・滑りの扱いが難しい。

参考になる研究:

```text

EgoVLA:
  human wrist and hand actionsを予測し、IK/retargetingでロボットactionに変換する。

Vision-Based Hand Shadowing:
  エゴRGB-DカメラからMediaPipe Handsで21点ランドマークを取り、深度で3D化し、IKでSO-ARM101の関節指令へ変換する。

DexCap:
  SLAMと電磁トラッキングで手首・指を高精度に取得し、IKと点群ベース模倣学習でロボット手へ移す。

```

実験初期では、この方法で以下を作るのが現実的である。

```text

最小ラベル:
  - wrist trajectory
  - approach direction
  - grasp open/close
  - target object ID

```

### 6.2 物体状態・物体軌道を推定する

ロボットにとって重要なのは、人間の手の形そのものではなく、対象物がどう動いたかである場合が多い。

そのため、object-centricな中間表現を作る方法も有力である。

```text

エゴ/俯瞰映像
→ 対象物検出
→ object pose / object trajectory
→ object state transition
→ サブゴールまたはaction条件

```

この方法は、以下のようなタスクで特に有効である。

```text

- pick and place
- 物体を容器へ入れる
- 道具を所定位置へ移動する
- 引き出しや扉の状態変化を扱う
- 人間手の細かい形より、物体の結果状態が重要なタスク

```

参考になる研究:

```text

ROHIT:
  エゴ動画中の手-物体インタラクション期間を使い、安定把持中の制約から物体姿勢を伝播・復元する。

Diffusion-Guided Reconstruction:
  エゴ動画や第三者視点動画から、手と物体の3D形状・運動を復元する。

HumanEgo:
  人間エゴ動画をentity-levelな手-物体インタラクション表現へ持ち上げ、ロボット方策へ接続する。

```

この系統は、低解像度の俯瞰カメラとも相性が良い。ただし、精密な6DoF姿勢を低解像度映像だけで取るのは難しいため、初期段階では coarse object position や状態遷移に留めるのが現実的である。

### 6.3 接触・把持・サブタスク境界を抽出する

FTで意外に効くのは、連続的な精密actionよりも、サブタスク境界や接触イベントである。

```text

抽出したいイベント:
  - 手が対象物に接近
  - 接触開始
  - 把持成立
  - 持ち上げ
  - 移動
  - 設置
  - リリース
  - 失敗/落下

```

これらは、以下の用途に使える。

```text

- 長ホライズンタスクの分割
- VLM/LLMプランナー用のサブタスクラベル
- VLAのaction chunk境界
- 成功/失敗フィルタリング
- データ品質検査
- rewardや補助loss

```

手カメラは接触直前に強く、俯瞰カメラは持ち上げ・移動・落下の検出に強い。頭/首カメラは、対象物選択や作業文脈の推定に使いやすい。

この系統は、完全自動化しなくても、半自動アノテーションやVLMによる初期ラベル付けと人手確認で始めやすい。

### 6.4 pseudo-action trajectoryを作る

VLAのFTに近づけるには、人間デモをロボットデータに似た形式へ変換する必要がある。そのために、実際のロボットactionではないが、ロボットaction風の疑似軌道を作る方法がある。

```text

人間エゴ動画
→ hand/wrist/object/contact推定
→ camera-space action
→ action chunk
→ robot-format pseudo-action trajectory
→ VLAのFTデータ

```

参考になる研究:

```text

ACE-Ego-0:
  raw human egocentric videosをrobot-format pseudo-action trajectoriesへ変換する。
  camera-space actions、morphology conditioning、time-aligned action chunkingを使う。

EgoZero:
  スマートグラス映像からrobot-executable actionsとmorphology-agnostic stateを抽出する。

ARMimic:
  XRヘッドセットと固定カメラを使い、ARロボットオーバーレイで実行可能な仮想ロボット軌道を作る。

```

この方法はFTに直接使いやすい一方、pseudo-actionの品質が低いと性能を落とす。したがって、信頼度スコアやフィルタリングが重要になる。

```text

必要な品質管理:
  - 手/物体検出のconfidence
  - 遮蔽区間の除外
  - IKが解けない軌道の除外
  - 物理的に不可能な軌道の除外
  - 成功/失敗ラベルによる重み付け
  - ロボットデータとの混合比率調整

```

### 6.5 latent action tokenへ変換する

明示的なwrist poseやobject poseを作るのではなく、ロボット実行可能な潜在Action空間を学習し、人間動画をその空間へ写す方法もある。

```text

ロボット軌道
→ action codebook / latent action spaceを学習

人間動画
→ 遷移をlatent actionへ対応づけ
→ pseudo-labeled human video
→ VLAのFT/継続学習に利用

```

参考になる研究:

```text

CLAP:
  ロボット軌道から実行可能なaction vocabularyを作り、人間動画の遷移をlatent actionへ対応づける。
  FT時の忘却を抑えるため、Knowledge Matching regularizationも使う。

```

この方法は、手・物体の明示的な3D復元が難しい場合にも使える可能性がある。ただし、latent actionが何を意味しているかの解釈性は下がる。

### 6.6 XR/深度/IMU/マーカーで変換を補助する

純粋なRGB映像だけで中間表現を高精度に作るのは難しい。実務では、以下の補助情報を使うと変換品質が大きく上がる。

```text

補助センサ:
  - RGB-D
  - depth camera
  - hand tracking付きXR headset
  - IMU
  - SLAM
  - electromagnetic tracking
  - fiducial marker / AprilTag
  - AR robot overlay

```

参考になる研究:

```text

ARMimic:
  XR headset、depth、固定カメラ、AR robot overlayを使い、収録時点で実行可能性を高める。

DexCap:
  SLAMと電磁トラッキングを使い、遮蔽に強い手首・指軌道を取得する。

Vision-Based Hand Shadowing:
  エゴRGB-DとIKで、比較的低コストなロボットaction変換を行う。

```

最初はRGBカメラだけで始めてもよいが、変換ラベルのノイズが大きい場合は、深度や簡易マーカーを足す方が、モデル側で無理に吸収させるより安定する。

### 6.7 実装上の推奨変換パイプライン

初期実験では、以下のような現実的なパイプラインがよい。

```text

Input:
  - 頭/首/胸カメラ
  - 手首/手元カメラ
  - 俯瞰/監視カメラ
  - 言語指示
  - 成功/失敗

Stage A: 同期・整備
  - timestamp同期
  - フレーム欠落チェック
  - カメラごとの簡易キャリブレーション
  - 作業区間の切り出し

Stage B: 視覚ラベル抽出
  - target object ID
  - hand/wrist landmarks
  - object bounding box / coarse position
  - grasp open/close
  - contact候補
  - subtask boundary

Stage C: 疑似action化
  - wrist/end-effector delta
  - gripper open/close
  - approach/retreat direction
  - pick/place/releaseイベント
  - action chunk

Stage D: 品質管理
  - confidenceが低い区間を除外
  - 遮蔽区間を補間または除外
  - IK不能な軌道を除外
  - 成功/失敗で重み付け
  - 人手で少量サンプルを検査

Stage E: FTデータ化
  - observation
  - language instruction
  - pseudo-action / intermediate action
  - auxiliary labels
  - confidence / mask

```

保存形式としては、後から再変換できるように、最終actionだけでなく中間ラベルも残す。

```text

保存すべきもの:
  - raw video path
  - timestamps
  - camera calibration
  - target object labels
  - hand/wrist trajectories
  - object states
  - event labels
  - generated pseudo-actions
  - confidence scores
  - human correction flags

```

この形で保存しておくと、対象ロボット固定FT、中間表現FT、複数ロボット対応のいずれにも再利用しやすい。

### 6.8 動画からpseudo-action生成するための具体的な参考情報

現時点では、同期マルチビュー動画を入力するとFT用のobservation/actionペアを自動生成する汎用OSSはない。実際には、以下のように複数の公開実装・既存ライブラリを組み合わせる。

```text

動画
→ 手/物体/カメラ姿勢を推定
→ 時系列で追跡・平滑化
→ ロボット手先目標へ変換
→ IK/retargetingでaction化
→ confidence付きFTデータとして保存

```

#### A. Franka系・単腕グリッパで最初に参考にする実装

```text

EgoZero:
  Repository: https://github.com/vliu15/egozero
  Project: https://egozero-robot.github.io/

```

特徴:

```text

- Project Ariaのスマートグラス映像を使う。
- Aria MPSのカメラ軌道・hand pose系の情報を利用する。
- object pointsを複数視点/カメラ軌道からtriangulationする。
- action pointsをhand pose推定から作る。
- 最終的にFranka向けのポリシー学習へ接続する。

```

参考になる点:

```text

- エゴ動画から直接ロボットactionを作るのではなく、object/action pointsを経由する。
- 動画、カメラ軌道、hand pose、点ラベルを組み合わせてpseudo-actionを作る。
- 対象ロボット固定で最初に試す場合の構成に近い。

```

想定される流用:

```text

入力:
  - エゴ動画
  - カメラ軌道またはSLAM結果
  - hand pose
  - object point annotation

出力:
  - object-centric state
  - action points
  - Franka向けpolicy training data

```

制約:

```text

- Project Aria前提の処理が多い。
- 任意の頭/首カメラや監視カメラ構成へそのまま移植できるとは限らない。
- ただし、データ設計とpreprocessの流れはかなり参考になる。

```

#### B. VLA/FT寄りの参考実装

```text

EgoVLA Release:
  Repository: https://github.com/RchalYang/EgoVLA_Release
  Project: https://rchalyang.github.io/EgoVLA/

```

特徴:

```text

- egocentric human videoをVLA学習に使うための実装。
- hand/head/camera pose、language label、MANO系の表現を扱う。
- human wrist/hand actionを予測し、IK/retargetingでロボットへ接続する。
- robot fine-tuning scriptも含む。

```

参考になる点:

```text

- 「動画 → wrist/hand action → robot fine-tuning」の構成を確認できる。
- 中間表現としてMANOやwrist poseを使う設計の参考になる。
- VLA側のデータ形式、学習スクリプト、robot FTの流れを確認できる。

```

想定される流用:

```text

入力:
  - egocentric RGB video
  - hand/head/camera pose
  - language label

出力:
  - wrist/hand action representation
  - VLA training data
  - robot fine-tuning data

```

制約:

```text

- 実験設定やロボットが限定されている可能性がある。
- 自前カメラ構成へ使うには、hand/head/camera poseをどう作るかを別途実装する必要がある。

```

#### C. 精密な手指・dexterous handで参考にする実装

```text

DexCap:
  Repository: https://github.com/j96w/DexCap
  Project: https://dex-cap.github.io/

```

特徴:

```text

- chest camera RGB/depth、camera pose、左右手pose、hand jointなどを保存する。
- SLAMや電磁トラッキングを併用し、遮蔽に強く手首・指軌道を取得する。
- IKとretargetingでロボット手へ移す。
- 点群ベースの模倣学習と接続する。

```

参考になる点:

```text

- 映像だけで精密な手指actionを作るのが難しい場合の現実解。
- どの中間データを保存すべきかの参考になる。
- dexterous manipulationでは、RGBだけではなく追加センサを使う設計が重要。

```

制約:

```text

- センサ構成が重い。
- 単純な2指グリッパの初期検証には過剰な場合がある。

```

#### D. 手・物体・マスク・姿勢推定の部品

動画からpseudo-actionを作る場合、以下の部品を組み合わせる。

```text

MediaPipe Hands:
  https://github.com/google-ai-edge/mediapipe
  用途:
    - 2D/3D hand landmarks
    - 親指-人差し指距離からgripper open/close推定
    - 低コストな初期プロトタイプ

HaMeR:
  https://geopavlakos.github.io/hamer/
  用途:
    - 単眼画像から3D hand mesh/MANO系表現を推定
    - wrist/hand pose中間表現

SAM 2:
  https://github.com/facebookresearch/sam2
  用途:
    - 動画中の対象物セグメンテーション
    - object mask tracking
    - 遮蔽区間や対象物追跡

FoundationPose:
  https://nvlabs.github.io/FoundationPose/
  用途:
    - 物体の6D pose estimation/tracking
    - CADモデルや参照画像がある対象物の姿勢推定

AprilTag / fiducial marker:
  用途:
    - カメラキャリブレーション
    - 物体姿勢の簡易ground truth
    - 初期実験でpseudo-action品質を上げる

PyBullet / Pinocchio / MuJoCo / IKFast:
  用途:
    - end-effector targetからjoint targetへ変換
    - IK可否チェック
    - 速度/加速度/関節制限チェック

```

#### E. 最初に作るべきpseudo-action形式

初期実験では、完全な関節指令ではなく、ロボットの制御方式に近い低次元actionから始める。

```text

推奨:
  action_t =
    delta_ee_position: [dx, dy, dz]
    delta_ee_rotation: [droll, dpitch, dyaw] または quaternion delta
    gripper: open/close または連続値
    confidence: 0.0-1.0
    mask: valid/invalid

```

動画から作る対応:

```text

hand/wrist 3D trajectory:
  → delta_ee_position

wrist/hand orientation:
  → delta_ee_rotation

thumb-index distance or grasp state:
  → gripper open/close

object trajectory:
  → target-relative motion

contact/pick/place event:
  → action chunk boundary

tracking confidence / occlusion:
  → confidence and mask

```

この形式なら、対象ロボット固定のFTにも、中間表現化にも流用しやすい。

#### F. 変換時の品質チェック

動画由来pseudo-actionはノイズが大きいため、actionだけでなく信頼度と除外マスクを持つ。

```text

必須チェック:
  - hand detection confidence
  - object tracking confidence
  - カメラ同期ずれ
  - occlusion率
  - IK可解性
  - joint limit
  - velocity / acceleration limit
  - gripper開閉タイミング
  - 物体が実際に動いたか
  - 成功/失敗ラベル

```

除外または低重み化すべき区間:

```text

- 手が画面外に出た
- 対象物が完全に遮蔽された
- 複数物体が混同された
- IKが不安定
- 手首軌道が急にジャンプした
- 接触/把持が映像から判断できない
- 失敗デモだが成功として扱われている

```

#### G. 実験用の最小構成

最初に作るなら、以下の構成が現実的である。

```text

収録:
  - 頭/胸カメラ
  - 手元または手首カメラ
  - 固定俯瞰カメラ
  - 粗いtimestamp同期
  - 言語指示
  - 成功/失敗

処理:
  - MediaPipe HandsまたはHaMeRでhand/wrist推定
  - SAM 2などで対象物追跡
  - 俯瞰で対象物の粗い移動と失敗を確認
  - hand/wrist trajectoryを平滑化
  - gripper open/closeを推定
  - end-effector delta actionへ変換
  - IK可否をチェック
  - confidence/mask付きで保存

出力:
  - observation画像または動画クリップ
  - language instruction
  - pseudo-action
  - target object ID
  - event labels
  - confidence/mask

```

この最小構成で通常テレオペFT baselineと比較し、効果が見えたら、EgoZero/EgoVLA/DexCapのような本格的な変換へ進む。

---

## 7. 参考論文・取り組み

### Ego-Pi: VLA Fine-Tuning for Ego-Centric Human and Robot Data

- Link: https://arxiv.org/abs/2606.08107
- Project: https://egopipaper.github.io/

VLAのFTにエゴセントリックな人間データとロボットデータを組み合わせる、非常に直接的な研究。

`π0.5`を基盤として、人間データが新しいタスク意味の獲得や既存スキルの合成に効くかを調べている。FTにこだわる場合、最優先で確認すべき論文。

示唆:

```text

- エゴ人間データは、対応するロボットデータがないタスク意味の獲得に使える可能性がある。
- ただし、対象embodimentや手の形状との相性が重要。
- ロボットデータを完全に置き換えるというより、少量ロボットFTを補強する位置づけが現実的。

```

### EgoVLA: Learning Vision-Language-Action Models from Egocentric Human Videos

- Link: https://arxiv.org/abs/2507.12440
- Project: https://rchalyang.github.io/EgoVLA/

人間エゴ動画からVLAを学習し、少量のロボット操作デモでFTしてロボットポリシー化する研究。

特徴は、エゴ動画から **human wrist and hand actions** を予測し、IKとretargetingでロボットActionへ変換する点。

示唆:

```text

- エゴ動画を直接ロボットactionにするのではなく、wrist/hand actionを中間表現として扱う。
- 少量ロボットデモでFTする設計が現実的。
- humanoidやdexterous handとの相性が特に高い。

```

### ACE-Ego-0: Unifying Egocentric Human and Robotic Data for VLA Pretraining

- Link: https://arxiv.org/abs/2606.17200

エゴ人間動画とロボットデモを統一的に扱うためのVLAフレームワーク。

raw human egocentric videosを **robot-format pseudo-action trajectories** に変換し、ロボットデータと比較可能にする。中間表現として、camera-space actions、morphology conditioning、time-aligned action chunkingを使う。

示唆:

```text

- 複数ロボット対応を狙うなら、ロボット固有actionではなくcamera-space actionのような共通表現が有望。
- 身体差は隠すのではなく、morphology conditioningとして明示的にモデルへ渡す。
- 人間エゴ由来のpseudo-actionはノイズがあるため、信頼度に応じた学習が必要。

```

### CLAP: Contrastive Latent Action Pretraining for Learning VLA Models from Human Videos

- Link: https://arxiv.org/abs/2601.04061
- Project: https://lin-shan.com/CLAP/

人間動画をロボット実行可能なlatent actionへ対応づける研究。

ロボット軌道から実行可能なaction codebookを作り、人間動画の遷移をその潜在Action空間に写す。FT時の破滅的忘却を抑えるため、Knowledge Matching regularizationも導入している。

示唆:

```text

- 中間表現は必ずしも明示的なwrist poseである必要はない。
- latent action tokenとして学習する方向もある。
- 人間動画由来データをFTに混ぜる場合、忘却対策が重要。

```

### EgoZero: Robot Learning from Smart Glasses

- Link: https://arxiv.org/abs/2505.20290
- Project: https://egozero-robot.github.io/

Project Ariaのようなスマートグラスで収録した人間エゴデモから、ロボット実行可能なActionとmorphology-agnostic stateを抽出し、ロボット方策を学習する研究。

VLAそのものというより、エゴデータからロボット学習へつなぐ実装方針として参考になる。

示唆:

```text

- 頭部/眼鏡型デバイスだけでも、限定条件下ではロボット学習へ接続できる。
- morphology-agnostic state representationが重要。
- ただし、対象ロボットやタスク設計をかなり意識した変換が必要。

```

### ARMimic: Learning Robotic Manipulation from Passive Human Demonstrations in Augmented Reality

- Link: https://arxiv.org/abs/2509.22914

XRヘッドセットと固定ワークプレイスカメラを使い、人間デモをロボット学習へ接続する研究。

ARロボットオーバーレイ、エゴ手トラッキング、深度を活用し、人間と仮想ロボット軌道を交換可能なものとして扱う。

示唆:

```text

- 頭/首カメラ + 固定外部カメラという構成は現実的。
- ただし、単なる映像だけでなく、AR/深度/手トラッキングを併用すると実用性が上がる。
- ロボットにとって実行可能な軌道かどうかを収録時点で制約する発想が重要。

```

### DexCap: Scalable and Portable Mocap Data Collection System for Dexterous Manipulation

- Link: https://arxiv.org/abs/2403.07788
- Project: https://dex-cap.github.io/

カメラ映像だけではなく、SLAMや電磁トラッキングを使って、手首・指の動きをオクルージョンに強く取得するシステム。

特にdexterous manipulationでは、映像だけで細かい手指・接触を安定推定するのが難しいため、追加センサを使う現実解として参考になる。

示唆:

```text

- 精密な手指・接触・把持を扱うなら、映像だけにこだわらない方がよい。
- wrist/finger motionを高品質に取るほど、retargetingとFTの品質が上がる。
- 初期実験では不要でも、精密操作へ進むなら検討価値が高い。

```

### EgoMI: Learning Active Vision and Whole-Body Manipulation from Egocentric Human Demonstrations

- Link: https://arxiv.org/abs/2511.00153
- Project: https://egocentric-manipulation-interface.github.io/

人間の頭部視点と手/エンドエフェクタ軌道を同期して収録し、semi-humanoid robotへretargetする研究。

人間は作業中に頭と手を協調して動かすため、単なる手先操作だけでなく、active visionを学習対象にする点が特徴。

示唆:

```text

- 頭/首カメラは単なる観測ではなく、視線・探索・注視の行動データでもある。
- 頭部カメラが動くことはノイズである一方、active perceptionの情報でもある。
- humanoidや可動カメラ付きロボットでは、頭部運動も中間表現に入れる価値がある。

```

### Vision-Based Hand Shadowing for Robotic Manipulation via Inverse Kinematics

- Link: https://arxiv.org/abs/2603.11383

単一のエゴRGB-Dカメラから人間の手を検出し、3Dランドマークへ変換し、IKで低コストロボットアームの関節指令へretargetする研究。

MediaPipe Handsで片手21点ランドマークを取り、深度で3D化し、ロボット座標系へ変換した上で、PyBullet上のIKでSO-ARM101の関節指令を生成する。親指と人差し指の幾何からグリッパ開閉も推定する。

示唆:

```text

- エゴRGB-Dからロボットaction風データへ変換する最小構成として参考になる。
- マーカーなし・低コストで始められる一方、遮蔽や複雑環境では成功率が大きく落ちる。
- FT用疑似action生成の初期プロトタイプとして使いやすい発想。

```

### ROHIT: Reconstructing Objects along Hand Interaction Timelines in Egocentric Video

- Link: https://arxiv.org/abs/2512.07394

エゴ動画中の手-物体インタラクションを、物体が静止している区間、手で保持される区間、再び静止する区間というtimelineとして捉え、物体姿勢を復元・伝播する研究。

安定把持中は、手と物体の相対関係が大きく崩れにくいという制約を使い、物体の姿勢推定を改善する。

示唆:

```text

- hand-centricではなくobject-centricな中間表現を作る上で参考になる。
- pick/placeや道具操作では、手の形より物体状態遷移を取る方がFTに効く可能性がある。
- 安定把持という制約があるタスクでは、低ノイズなobject trajectoryを作りやすい。

```

### Diffusion-Guided Reconstruction of Everyday Hand-Object Interaction Clips

- Link: https://arxiv.org/abs/2309.05663

短い手-物体インタラクション動画から、物体形状、物体運動、手の関節姿勢を復元する研究。

エゴ動画では視点変化や遮蔽が大きいため、通常のマルチビュー情報だけでは3D復元が不安定になる。そこで、手の構成や物体カテゴリに条件づけた拡散モデルを事前分布として使い、3D復元を補助する。

示唆:

```text

- エゴ動画からobject poseやhand poseを直接取る場合、視覚幾何だけでなく学習済みpriorが重要。
- 透明物体や細かい接触までは難しいが、手-物体軌道の中間表現化に参考になる。
- FTデータ生成では、復元confidenceを保持して低信頼区間をmaskする設計が必要。

```

### HumanEgo: Zero-Shot Robot Learning from Minutes of Human Egocentric Videos

- Link: https://arxiv.org/abs/2605.24934

人間のエゴ動画を、手と物体のインタラクションを中心にしたentity-level representationへ変換し、ロボット方策へ接続する研究。

ロボットデータなし、かつ少量の人間エゴ動画から、複数タスク・複数ロボットへzero-shot転移することを狙っている。

示唆:

```text

- 中間表現を、手首軌道だけでなく手-物体-状態のentity-level表現として設計する方向がある。
- 複数ロボットへの汎化を狙う場合、ロボット固有actionよりも、手・物体・関係性を抽象化した表現が有望。
- ただし実験条件や対象タスクを確認し、対象ロボット固定FTのbaselineと比較する必要がある。

```

---

## 8. 初期実験での推奨設計

最初の実験では、以下の構成が現実的である。

```text

収録:
  - 対象ロボットの通常テレオペデータ
  - 人間の頭/首/胸カメラ
  - 人間の手首/手元カメラ
  - 固定俯瞰/監視カメラ
  - 言語指示
  - 成功/失敗ラベル

学習:
  - baseline: 通常テレオペのみ
  - variant 1: テレオペ + 頭/首視点
  - variant 2: テレオペ + 手視点
  - variant 3: テレオペ + 俯瞰視点
  - variant 4: テレオペ + 全視点

評価:
  - 成功率
  - 少量データ時の性能
  - 配置変更への耐性
  - タスク意味の汎化
  - 長ホライズンでの安定性
  - 失敗パターン

```

この段階では、中間表現は最小限でよい。

```text

最低限:
  - target object ID
  - coarse object position
  - hand/wrist trajectory
  - grasp open/close
  - subtask boundary
  - success/failure

```

---

## 9. 判断基準

エゴデータ活用を続けるべきかは、次の結果で判断する。

```text

続ける価値が高い:
  - 同じロボットデモ数で成功率が上がる
  - 少量デモ時の立ち上がりが速い
  - 未知配置や未知物体への汎化が改善する
  - 長ホライズンタスクのサブタスク分解が安定する
  - 失敗検出や復帰が改善する

見直しが必要:
  - エゴデータを混ぜると性能が落ちる
  - 変換ラベルのノイズが大きい
  - 視点差で実行時分布が崩れる
  - 収録/同期/変換コストがテレオペより高くなる
  - ablationで特定視点の効果が見えない

```

---

## 10. 結論

エゴセントリックデータをFTに使う方向性は有望だが、現時点では標準化された完成パイプラインがあるわけではない。

現実的な進め方は以下である。

```text

1. まず対象ロボット固定で試す
2. 通常テレオペFTをbaselineにする
3. 頭/首、手、俯瞰視点を追加してablationする
4. 効果が出る視点とタスクを見極める
5. その後、中間表現へ抽象化する
6. 複数ロボット対応へ拡張する

```

最初から汎用中間表現を完成させるより、**対象ロボットでFT効果を確認し、その後に中間表現を設計する**方が、研究としても実装としてもリスクが低い。
