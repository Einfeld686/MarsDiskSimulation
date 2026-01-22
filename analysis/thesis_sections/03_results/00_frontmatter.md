<!-- TEX_EXCLUDE_START -->
> **文書種別**: 結果（Diátaxis: Explanation）
<!-- TEX_EXCLUDE_END -->

<!--
NOTE: このファイルは analysis/thesis_sections/03_results/*.md の結合で生成する．
編集は分割ファイル側で行い，統合は `python -m analysis.tools.merge_results_sections --write` を使う．
-->

# 結果

本章では，手法章で定義した軸対称 1D（リング分割）モデルに基づく数値結果を整理する．主な関心は，遷移期における放射圧による質量損失の累積量 $M_{\rm loss}$ と，それが温度や光学的厚さにどう依存するかである．粒径分布（PSD）の時間発展は，代表ケースのスナップショットと blow-out 近傍の定性的特徴（“wavy”）に限定し，定量評価は $\tau_{\rm los}(t)$ と $\dot{M}_{\rm out}(t)$，および $M_{\rm loss}$ の時系列・集計値に焦点を当てる．

## 構成

1. 実行条件とデータセット
2. 主要時系列と累積量
3. 粒径分布（PSD）の時間発展
4. 検証：質量保存と停止条件
5. 感度解析
6. 小結
