## 5. 本論文の構成（各章で何をするか）

本節では、本研究の議論を追跡しやすくするために、以降の章構成と各章の役割を示す。遷移期損失 $\Delta M_{\rm in}$ の推定は、モデル化（第2章）と結果の整理（第3章）を経て、感度解析と長期形成モデルへの含意（第4章）へ接続される。

第2章では、遷移期モデルの仮定、状態変数、離散化、損失項の定義、および時間積分法をまとめ、$\Delta M_{\rm in}$ を計算する手順を定式化する。ここでは、SPH 出力から長期モデル入力を作る写像と、第3節で導入した「追加シンクとしての損失率 $\dot{M}_{\rm loss}(t)$」の具体化が中心となる。

第3章では、代表条件下の損失時系列と累積損失を提示し、$M_{\rm in,0}$ の更新量がどの程度になり得るかを示す。次いで第4章では、火星冷却史や遮蔽条件（光学的厚み）などの不確かさに対する感度を整理し、更新後の初期条件が長期衛星形成モデルの予測へ与える含意を議論する。第5章では、本研究で得られた更新指針をまとめ、残る課題と今後の検証可能性を述べる。

以上により、本論文は「遷移期の質量収支」という観点から、巨大衝突直後計算と長期形成モデルの間の接続を再構成する。

<!-- TEX_EXCLUDE_START -->
### 構成メモ

- 章としての導入は、背景→先行研究→ギャップ（遷移期）→研究目的（3点）→構成、の順で閉じる。
- 詳細な式（$a_{\rm eq}$ 写像、$\tau$ 計算、冷却の積分形、遷移期の時間幅の見積もり等）は第2章へ寄せる。
- 長期モデル入力（$M_{\rm in}$、$dM/da_{\rm eq}$、$a_{\rm eq,max}$、相・粒径分布）と、本研究で更新する量（$\Delta M_{\rm in}$、$M_{\rm in,0}$）の対応は、手法章冒頭で再掲する。

- コード: https://github.com/Einfeld686/MarsDiskSimulation  
- 数式と記号定義: `analysis/equations.md`  

### 参考：本節で言及した主要文献

- Canup, R. M., & Salmon, J. (2018), *Science Advances*, 4, eaar6887.
- Citron, R. I., Genda, H., & Ida, S. (2015), *Icarus*, 252, 334–338.
- Craddock, R. A. (2011), *Icarus*, 211, 1150–1161.  
  （加えて EPSC-DPS 2011 に同題の要旨がある）
- Hyodo, R., Rosenblatt, P., Genda, H., & Charnoz, S. (2017a), *ApJ*, 845, 125.
- Hyodo, R., Rosenblatt, P., Genda, H., & Charnoz, S. (2017b), *ApJ*, 851, 122.
- Ronnet, T., Vernazza, P., Mousis, O., et al. (2016), *ApJ*, 828, 109.
- Rosenblatt, P., & Charnoz, S. (2012), *Icarus*, 221, 806–815.
- Rosenblatt, P., Charnoz, S., Dunseath, K. M., et al. (2016), *Nature Geoscience*, 9, 581–583.
- Salmon, J., & Canup, R. M. (2012), *ApJ*, 760, 83.

#### 先行研究リンク（ローカル）

- [Canup & Salmon (2018)](../../paper/references/CanupSalmon2018_SciAdv4_eaar6887.pdf)
- [Citron et al. (2015)](../../paper/references/Citron2015_Icarus252_334.pdf)
- [Craddock (2011)](../../paper/references/Craddock2011_EPSCDPS1108.pdf)
- [Hyodo et al. (2017a)](../../paper/references/Hyodo2017a_ApJ845_125.pdf)
- [Hyodo et al. (2017b)](../../paper/references/Hyodo2017b_ApJ851_122.pdf)
- [Ronnet et al. (2016)](../../paper/references/Ronnet2016_ApJ828_109.pdf)
- [Rosenblatt & Charnoz (2012)](../../paper/references/Rosenblatt2012_Icarus221_806.pdf)
- [Rosenblatt et al. (2016)](../../paper/references/Rosenblatt2016_NatGeo9_8.pdf)
- [Salmon & Canup (2012)](../../paper/references/SalmonCanup2012_ApJ760_83.pdf)

<!-- TEX_EXCLUDE_END -->
