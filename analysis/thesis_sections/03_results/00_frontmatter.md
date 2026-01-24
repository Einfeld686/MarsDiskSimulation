<!-- TEX_EXCLUDE_START -->
> **文書種別**: 結果（Diátaxis: Explanation）
<!-- TEX_EXCLUDE_END -->

# 結果

本章では，手法章で定義した軸対称 1D（リング分割）モデルに基づく数値結果を整理する．主な関心は，遷移期における放射圧による不可逆損失の累積量 $M_{\rm loss}$（序論の $\Delta M_{\rm in}$；式\ref{eq:delta_min_def}）と，それが温度や光学的厚さにどう依存するかである．この $M_{\rm loss}(t_{\rm end})$ は，長期モデルへ渡す内側円盤質量の更新量（式\ref{eq:min0_update}）に直接入る．本章では，全円盤の $\dot{M}_{\rm out}(t)$（式\ref{eq:mdot_out_definition}）と $M_{\rm loss}(t)$（式\ref{eq:mass_loss_update}），および半径依存を含む $\dot{M}_{\rm out}(r,t)$ と $\tau_{\rm eff}(r,t)$（式\ref{eq:tau_eff_definition}）に焦点を当て，併せて質量保存と停止条件の内訳を検証する．

## 構成

1. 実行条件とデータセット
2. 全円盤の流出率 $\dot{M}_{\rm out}(t)$ と累積損失 $M_{\rm loss}(t)$
3. 半径依存：半径×時間の流出構造
4. 検証：質量保存と停止条件
5. 感度解析（温度・$\tau_0$・$\epsilon_{\rm mix}$）
6. 小結
