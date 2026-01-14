## 5. 本論文の構成（各章で何をするか）

本論文の構成は次のようになる。第2章ではモデルの仮定、状態変数、離散化、損失項と時間積分法を示し、遷移期損失を計算する手順を定式化する。第3章で代表条件下の損失時系列と累積損失を提示し、第4章で温度履歴や光学的厚みなどの感度と、長期形成モデルの初期条件更新への含意を議論する。第5章では本研究で得られた更新指針をまとめ、今後の課題を述べる。

<!-- TEX_EXCLUDE_START -->
### 構成メモ

- 章としての導入は、背景→先行研究→ギャップ（遷移期）→研究目的（3点）→構成、の順で閉じる。
- 詳細な式（\(a_{\rm eq}\) 写像、\(\tau\) 計算、冷却の積分形、遷移期の時間幅の見積もり等）は第2章へ寄せる。
- 長期モデル入力（\(M_{\rm in}\)、\(dM/da_{\rm eq}\)、\(a_{\rm eq,max}\)、相・粒径分布）と、本研究で更新する量（\(\Delta M_{\rm in}\)、\(M_{\rm in,0}\)）の対応は、手法章冒頭で再掲する。

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
---
